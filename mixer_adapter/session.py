"""Isolated, disk-backed session detection and per-song rendering.

This module is also the child-process entry point. Vendor globals never live in
the web server. Only a selected song is decoded for the browser's mixer.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def save(path, value):
    path = Path(path)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, allow_nan=False))
    temporary.replace(path)


def read(work):
    return json.loads((Path(work) / 'session.json').read_text())


def validate_songs(songs, duration):
    if not isinstance(songs, list) or not 1 <= len(songs) <= 500:
        raise ValueError('Choose between 1 and 500 songs.')
    result, previous = [], 0.0
    for index, item in enumerate(songs, 1):
        if not isinstance(item, dict):
            raise ValueError('Invalid song.')
        start, end = item.get('start'), item.get('end')
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (start, end)):
            raise ValueError('Song boundaries must be finite seconds.')
        if start < previous or end > duration + .001 or end - start < .5:
            raise ValueError('Songs must be in order, without overlap, and at least half a second long.')
        if not isinstance(item.get('selected', True), bool):
            raise ValueError('Invalid song selection.')
        result.append(dict(id=index, name=str(item.get('name') or f'Song {index:02d}')[:80],
                           start=float(start), end=float(end), selected=item.get('selected', True)))
        previous = end
    if not any(s['selected'] for s in result):
        raise ValueError('Select at least one song.')
    return result


MARGIN = 0.5  # seconds of original kept around each song range


def track_window(track, song):
    """(source_start, overlap) of a song inside one track file, in that file's own seconds."""
    offset = float(track['offset'])
    return max(0, song['start'] - offset), min(song['end'], offset + track['duration']) - max(song['start'], offset)


def original_windows(data):
    """Ranges of the originals a preview-based session needs before it can export.

    One entry per selected song and preview track that plays in that song. 'start' and
    'duration' are in the original file's own seconds, with a small margin.
    """
    previews = data.get('previews') or {}
    if not previews or not data.get('tracks'):
        return []
    received = data.get('originals') or {}
    result = []
    for song in data.get('songs') or []:
        if not song.get('selected'):
            continue
        for track in data['tracks']:
            original = previews.get(track['file'])
            source_start, overlap = track_window(track, song)
            if not original or overlap <= 0:
                continue
            start = max(0.0, source_start - MARGIN)
            window = [round(song['start'], 6), round(song['end'], 6)]
            got = received.get(f"{song['id']}/{track['file']}")
            result.append(dict(song=song['id'], song_name=song['name'], file=track['file'], original=original,
                               start=round(start, 6), duration=round(source_start - start + overlap + MARGIN, 6), window=window,
                               received=bool(got and got.get('window') == window and Path(got['path']).is_file())))
    return result


WAVE_STEP = 0.25  # seconds per waveform column
WAVE_RATE = 2000  # Hz; enough for an overview, cheap to decode


def session_waveform(work):
    """Peak overview of the whole session (all tracks, offsets honoured), cached as JSON.

    One value 0..255 per WAVE_STEP seconds. Drawn under each song so the person can
    see and drag its start and end."""
    import numpy as np
    work = Path(work)
    cached = work / 'waveform.json'
    if cached.is_file():
        return json.loads(cached.read_text())
    data = read(work)
    columns = int(math.ceil(float(data['duration']) / WAVE_STEP))
    peaks = np.zeros(columns, dtype='float32')
    per = int(WAVE_RATE * WAVE_STEP)
    for track in data['tracks']:
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', track['path'], '-vn', '-ac', '1', '-ar', str(WAVE_RATE),
                              '-f', 'f32le', '-'], capture_output=True, check=True, timeout=900).stdout
        audio = np.abs(np.frombuffer(raw, dtype='<f4'))
        usable = len(audio) // per * per
        if not usable:
            continue
        column = audio[:usable].reshape(-1, per).max(axis=1)
        first = int(round(float(track['offset']) / WAVE_STEP))
        end = min(columns, first + len(column))
        if end > first:
            peaks[first:end] = np.maximum(peaks[first:end], column[:end - first])
    top = float(np.percentile(peaks[peaks > 0], 99.5)) if (peaks > 0).any() else 1.0
    result = dict(step=WAVE_STEP, duration=float(data['duration']),
                  peaks=np.clip(peaks / max(top, 1e-6) * 255, 0, 255).astype(int).tolist())
    save(cached, result)
    return result


def session_listen(work):
    """One light listening copy of the whole session (all tracks, offsets honoured).

    Made once; the page seeks inside it, so moving a cut or jumping to a point never
    waits for the server. Rough equal-level mix for checking cuts, not the export."""
    work = Path(work)
    target = work / 'listen-all.webm'
    if target.is_file():
        return target
    data = read(work)
    inputs, labels = [], []
    for track in data['tracks']:
        delay = round(float(track['offset']) * 1000)
        inputs += ['-i', track['path']]
        labels.append(f'[{len(labels)}:a]aformat=channel_layouts=mono,adelay={delay}:all=1[a{len(labels)}]')
    mixed = ''.join(f'[a{i}]' for i in range(len(labels)))
    graph = ';'.join(labels) + f';{mixed}amix=inputs={len(labels)}:normalize=0:duration=longest,dynaudnorm=f=500:g=31,alimiter=limit=0.9[out]'
    pending = target.with_suffix('.part.webm')  # WebM keeps a seek index: jumps are instant in the browser
    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', *inputs, '-filter_complex', graph, '-map', '[out]', '-ac', '1',
                    '-c:a', 'libopus', '-b:a', '48k', '-application', 'audio', '-f', 'webm', str(pending)],
                   check=True, capture_output=True, timeout=3600)
    pending.replace(target)
    return target


def listen_range(work, start, end):
    """A quick, rough mix of every track for one range, for listening while reviewing cuts.

    Equal levels, a limiter, Opus. Not the automatic mix: that happens per song at export."""
    work = Path(work)
    data = read(work)
    start, end = max(0.0, float(start)), min(float(data['duration']), float(end))
    if end - start < .5 or end - start > 3600:
        raise ValueError('Choose a range between half a second and one hour.')
    folder = work / 'listen'
    folder.mkdir(exist_ok=True)
    target = folder / f'{start:.2f}-{end:.2f}.ogg'
    if target.is_file():
        return target
    inputs, labels = [], []
    for track in data['tracks']:
        source_start, overlap = track_window(track, dict(start=start, end=end))
        if overlap <= 0:
            continue
        delay = round(max(0, float(track['offset']) - start) * 1000)
        inputs += ['-ss', f'{source_start:.3f}', '-t', f'{overlap:.3f}', '-i', track['path']]
        labels.append(f'[{len(labels)}:a]aformat=channel_layouts=mono,adelay={delay}:all=1[a{len(labels)}]')
    if not inputs:
        raise ValueError('No audio in this range.')
    mixed = ''.join(f'[a{i}]' for i in range(len(labels)))
    graph = ';'.join(labels) + f';{mixed}amix=inputs={len(labels)}:normalize=0,dynaudnorm=f=250:g=15,alimiter=limit=0.9[out]'
    pending = target.with_suffix('.part.ogg')
    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', *inputs, '-filter_complex', graph, '-map', '[out]', '-t', f'{end - start:.3f}',
                    '-c:a', 'libopus', '-b:a', '96k', '-f', 'ogg', str(pending)], check=True, capture_output=True, timeout=900)
    pending.replace(target)
    return target


def silence_candidates(stems, timelines, duration, frame_seconds):
    """Reviewable fallback for sessions with clear collective instrument rests.

    Uses the vendor's cached RMS grid, never full-length decoded PCM. Speech on
    a room/mic track must not conceal a rest between songs.
    """
    import numpy as np
    count = int(math.ceil(duration / frame_seconds))
    active = np.zeros(count, dtype=bool)
    for stem in stems:
        if stem.role in {'vocal', 'room'}:
            continue
        env = timelines.get(stem.path.name)
        if env is None or not len(env):
            continue
        above_floor = env[env > 10 ** (-60 / 20)]
        if not len(above_floor):
            continue
        threshold = max(10 ** (-55 / 20), float(np.percentile(above_floor, 75)) * .05)
        active[:min(count, len(env))] |= env[:count] > threshold
    changes = np.diff(np.r_[True, active, True].astype('int8'))
    rests = zip(np.where(changes == -1)[0], np.where(changes == 1)[0])
    cuts = [0.0]
    for start, end in rests:
        middle = (start + end) * frame_seconds / 2
        if (end - start) * frame_seconds >= 8 and middle - cuts[-1] >= 60 and duration - middle >= 60:
            cuts.append(middle)
    cuts.append(duration)
    return [dict(start=a, end=b, name=f'Song {i:02d}') for i, (a, b) in enumerate(zip(cuts, cuts[1:]), 1)]


def busiest_window(work, start, end, seconds):
    """The part of a song where most is playing (from the waveform), else its middle.

    The mixer preview is judged on this excerpt: an intro often lacks voice or drums."""
    if end - start <= seconds:
        return start, end
    middle = (start + end) / 2
    best = max(start, min(middle - seconds / 2, end - seconds))
    try:
        wave = json.loads((Path(work) / 'waveform.json').read_text())
        step, peaks = float(wave['step']), wave['peaks']
        first, last, width = int(start / step), int((end - seconds) / step), max(1, int(seconds / step))
        if last > first:
            sums = [sum(peaks[i:i + width]) for i in range(first, last + 1, max(1, width // 8))]
            index = max(range(len(sums)), key=sums.__getitem__)
            best = (first + index * max(1, width // 8)) * step
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return best, best + seconds


def prepare_tracks(work, song, preview=False):
    """Extract just this window; honor recorder offsets and pad missing regions."""
    work = Path(work)
    data = read(work)
    song = dict(song)
    if preview:
        bytes_per_second = sum(t['samplerate'] * min(t['channels'], 2) * 4 for t in data['tracks'])
        # decodeAudioData expands compressed sources to PCM in the browser.
        seconds = min(60, 96 * 1024**2 / max(1, bytes_per_second))
        song['start'], song['end'] = busiest_window(work, song['start'], song['end'], seconds)
    destination = work / ('preview' if preview else 'songs') / str(song['id']) / 'tracks'
    destination.mkdir(parents=True, exist_ok=True)
    duration = song['end'] - song['start']
    needed = sum(int(duration * t['samplerate'] * min(t['channels'], 2) * 4) for t in data['tracks'])
    if shutil.disk_usage(work).free < needed * (1 if preview else 4) + 128 * 1024**2:
        raise ValueError('Not enough working space for this song. Free space or choose a shorter interval.')
    for track in data['tracks']:
        if (work / 'cancel').exists():
            raise InterruptedError('Session cancelled. Your originals are unchanged.')
        target = destination / track['file']
        if target.is_file():
            continue
        offset = float(track['offset'])
        source_start, overlap = track_window(track, song)
        delay_ms = round(max(0, offset - song['start']) * 1000)
        source = track['path']
        # Export of a preview-based session: read the received original range, never the preview.
        original = None if preview else (data.get('originals') or {}).get(f"{song['id']}/{track['file']}")
        if original and original.get('window') == [round(song['start'], 6), round(song['end'], 6)]:
            source, source_start = original['path'], source_start - float(original['start'])
        elif not preview and track['file'] in (data.get('previews') or {}) and overlap > 0:
            raise ValueError(f"The original of {track['file']} for {song['name']} has not arrived. Keep the companion open and export again.")
        temporary = target.with_suffix('.partial.wav')
        if overlap <= 0:
            command = ['ffmpeg', '-v', 'error', '-nostdin', '-y', '-f', 'lavfi', '-i',
                       f'anullsrc=r={track["samplerate"]}:cl={"mono" if track["channels"] == 1 else "stereo"}']
            filters = 'anull'
        else:
            command = ['ffmpeg', '-v', 'error', '-nostdin', '-y', '-ss', str(source_start),
                       '-t', str(overlap), '-i', source]
            filters = f'adelay={delay_ms}:all=1,apad'
        subprocess.run(command + ['-vn', '-af', filters, '-t', str(duration), '-ac', str(min(track['channels'], 2)),
                                  '-ar', str(track['samplerate']), '-c:a', 'pcm_f32le', str(temporary)], check=True)
        temporary.replace(target)
    return destination


def parallel_songs():
    """How many songs to mix at once: about one per three cores, at most four."""
    try:
        return max(1, int(os.environ['MONTARA_PARALLEL_SONGS']))
    except (KeyError, ValueError):
        return max(1, min(4, (os.cpu_count() or 2) // 3))


def render_song(work, song_id):
    """Child process: mix and master one song; the parent collects results/<id>.json."""
    work = Path(work).resolve()
    data = read(work)
    os.environ['ZUCKER_MIXER_STATE_ROOT'] = str(work / 'vendor-state' / f'song-{song_id}')
    from mixer_adapter.single_song import SingleSongMix
    song = next(s for s in data['songs'] if s['id'] == song_id)
    settings = data['settings']
    # A song mixed in the mixer keeps its own changes; the rest use the automatic mix.
    mine = (settings.get('per_song') or {}).get(str(song_id)) or {}
    folder = prepare_tracks(work, song)
    mixer = SingleSongMix(folder, work / 'songs' / str(song_id) / 'mix', reference=mine.get('reference') or settings.get('reference'))
    out = mixer.render(mine.get('faders', settings.get('faders', {})), work / 'exports' / f'song-{song_id:03d}.mp3',
                       mine.get('mutes', settings.get('mutes', {})), mine.get('effects', settings.get('effects')),
                       eq=mine.get('eq'))  # per-song automatic mix; faders are offsets
    save(work / 'results' / f'{song_id}.json', dict(id=song_id, name=song['name'], start=song['start'], end=song['end'], path=str(out)))


def execute(work, action):
    work = Path(work).resolve()
    data = read(work)
    # Set before importing the vendor; one independent state root per process/job.
    os.environ['ZUCKER_MIXER_STATE_ROOT'] = str(work / 'vendor-state')
    from mixer_adapter.single_song import SingleSongMix, _load_mixer
    _, pipeline = _load_mixer(work)

    def progress(update):
        if (work / 'cancel').exists():
            raise InterruptedError('Session cancelled. Your originals are unchanged.')
        data['progress'] = {k: update[k] for k in ('current_stage', 'stage_detail', 'progress') if k in update}
        save(work / 'session.json', data)

    pipeline.PROGRESS_HOOK = progress
    if action == 'detect':
        pipeline.SOURCE_DIR = work / 'tracks'
        pipeline.configure_detection_cache(work / 'tracks', work / 'cache')
        pipeline.configure_detection_profile({'min_song_seconds': 60, 'max_song_seconds': 3600,
                                              'suspicious_short_song_seconds': 30})
        # Acoustic detection works offline; cloud AI is not a prerequisite.
        pipeline.WHISPER_ALLOWED = False
        stems = pipeline.inspect_stems(work / 'tracks')
        if not stems:
            raise ValueError('No readable audio tracks.')
        if len(stems) != len(list((work / 'tracks').iterdir())):
            raise ValueError('Some audio tracks could not be read. Convert those tracks to WAV or FLAC before continuing.')
        origin = min(s.offset_seconds for s in stems)
        from dataclasses import replace
        stems = [replace(s, offset_seconds=s.offset_seconds - origin) for s in stems]
        data['duration'] = max(s.offset_seconds + s.duration for s in stems)
        data['tracks'] = [dict(file=s.path.stem + '.wav', path=str(s.path), samplerate=s.samplerate,
                               channels=s.channels, offset=s.offset_seconds, duration=s.duration) for s in stems]
        timelines = pipeline.ensure_detection_cache(stems)
        segments, _ = pipeline.detect_segments(stems)
        proposals = [dict(start=max(0, s.start), end=min(data['duration'], s.end), name=f'Song {i:02d}')
                     for i, s in enumerate(segments, 1) if s.end - s.start >= .5]
        if pipeline.DETECTION_STRATEGY.get('needs_review') or pipeline.DETECTION_STRATEGY.get('candidate_only'):
            fallback = silence_candidates(stems, timelines, data['duration'], pipeline.DETECTION_FRAME_SECONDS)
            if len(fallback) > len(proposals):
                proposals = fallback
                pipeline.DETECTION_STRATEGY = dict(id='collective-rest-candidates', needs_review=True,
                                                  label='Instrument rests — review these suggested song boundaries')
        # No confident boundaries is reviewable, not an invented successful detection.
        if not proposals:
            proposals = [dict(start=0, end=data['duration'], name='Review this session')]
        proposals.sort(key=lambda s: s['start'])
        for current, following in zip(proposals, proposals[1:]):
            current['end'] = min(current['end'], following['start'])
        proposals = [s for s in proposals if s['end'] - s['start'] >= .5]
        data['songs'] = validate_songs(proposals, data['duration'])
        data['detection'] = pipeline.DETECTION_STRATEGY
        from montara_ai import AIService
        from ai_tasks import SESSION_BOUNDARIES
        service = AIService(data.get('ai_data_root', work))
        cuts = []
        for previous, following in zip(data['songs'], data['songs'][1:]):
            boundary = (previous['end'] + following['start']) / 2
            bins = []
            for shift in (-30, -20, -10, 0, 10, 20):
                a = max(0, int((boundary + shift) / pipeline.DETECTION_FRAME_SECONDS))
                b = max(a + 1, int((boundary + shift + 10) / pipeline.DETECTION_FRAME_SECONDS))
                levels = []
                for stem in stems:
                    if stem.role in {'vocal', 'room'}:
                        continue
                    env = timelines.get(stem.path.name)
                    if env is not None and len(env[a:b]):
                        import numpy as np
                        levels.append(float(np.mean(env[a:b])))
                bins.append(round(max(levels, default=0), 5))
            cuts.append(dict(id=previous['id'], before_seconds=previous['end']-previous['start'],
                             after_seconds=following['end']-following['start'], instrument_rms_10s_bins=bins))
        evidence = dict(cuts=cuts, duration_seconds=data['duration'], transcript_available=False)
        if cuts and service.configured:
            progress(dict(current_stage='Reviewing proposed song boundaries', progress=94))
        # A bounded review targets the shortest/doubtful neighboring sections;
        # do not send hundreds of cuts and wait through a chain of model calls.
        evidence['cuts'] = sorted(cuts, key=lambda cut: min(cut['before_seconds'], cut['after_seconds']))[:12]
        data['ai_review'] = service.review(SESSION_BOUNDARIES, evidence) if cuts else {'status': 'not_needed'}
        data['ai_review'].update(total_cuts=len(cuts), submitted_cuts=len(evidence['cuts']))
        # AI advice annotates proposals; only the person accepts/changes actual cuts.
        if data['ai_review']['status'] == 'reviewed':
            for cut in data['ai_review']['value']['cuts']:
                data['songs'][cut['id']-1]['review_note'] = cut['reason']
                data['songs'][cut['id']-1]['needs_review'] = cut['decision'] == 'review'
        progress(dict(current_stage='Drawing the waveform', progress=97))
        save(work / 'session.json', data)  # tracks and duration are needed by the drawing
        try:
            session_waveform(work)
        except Exception as exc:  # the review still works without the drawing
            print('waveform failed:', exc, flush=True)
        progress(dict(current_stage='Preparing a listening copy', progress=98))
        try:
            session_listen(work)
        except Exception as exc:  # listening falls back to short ranges
            print('listening copy failed:', exc, flush=True)
        data['status'] = 'review'
    elif action == 'prepare':
        song = next((s for s in data['songs'] if s['id'] == data.get('preview_song')), None) or next(s for s in data['songs'] if s['selected'])
        folder = prepare_tracks(work, song, preview=True)
        data['preview_tracks'] = [str(p) for p in sorted(folder.glob('*.wav'))]
        data['status'] = 'ready'
    elif action == 'render':
        # Songs are independent: several are mixed at once, each in its own process
        # (the mixer keeps state in module globals), so an 8-core server is not idle.
        data['results'] = []
        selected = [s for s in data['songs'] if s['selected']]
        results = work / 'results'
        shutil.rmtree(results, ignore_errors=True)
        results.mkdir()
        save(work / 'session.json', data)
        pending, running, finished = list(selected), {}, 0
        slots = min(len(selected), parallel_songs())
        root = Path(__file__).resolve().parents[1]
        with (work / 'worker.log').open('ab') as log:
            try:
                while pending or running:
                    while pending and len(running) < slots:
                        song = pending.pop(0)
                        running[song['id']] = (song, subprocess.Popen([sys.executable, '-m', 'mixer_adapter.session', str(work), 'render-song', str(song['id'])],
                                                                      cwd=root, stdout=log, stderr=log))
                    for song_id, (song, process) in list(running.items()):
                        code = process.poll()
                        if code is None:
                            continue
                        del running[song_id]
                        if code != 0:
                            raise RuntimeError(f"{song['name']} could not be mixed. Your originals are unchanged; retry the export.")
                        data['results'].append(json.loads((results / f'{song_id}.json').read_text()))
                        finished += 1
                        if song is not selected[0]:  # keep the first song's PCM for the browser; release the rest
                            shutil.rmtree(work / 'songs' / str(song_id), ignore_errors=True)
                    names = ', '.join(song['name'] for song, _ in running.values())
                    progress(dict(current_stage='mixing songs', stage_detail=f'{finished} of {len(selected)} done' + (f' · now: {names}' if names else ''),
                                  progress=100 * finished / len(selected)))
                    time.sleep(.5)
            finally:
                for _, process in running.values():
                    process.kill()
        data['results'].sort(key=lambda r: r['id'])
        data['status'] = 'done'
    else:
        raise ValueError('Unknown session action.')
    data['progress'] = dict(progress=100, current_stage=data['status'])
    data.pop('error', None)
    save(work / 'session.json', data)


if __name__ == '__main__':
    work, action = Path(sys.argv[1]), sys.argv[2]
    if action == 'render-song':  # child of a render; the parent holds the locks and handles cancel
        render_song(work, int(sys.argv[3]))
        sys.exit(0)
    import fcntl
    import signal
    import threading
    lock = (work / 'worker.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def interrupted(*_):
        raise InterruptedError('Session cancelled. Your originals are unchanged.')

    signal.signal(signal.SIGTERM, interrupted)

    def watch_cancel():
        while True:
            time.sleep(.3)
            if (work / 'cancel').exists():
                # Also terminate FFmpeg descendants. This worker has its own group.
                os.killpg(os.getpgrp(), signal.SIGTERM)
                return

    threading.Thread(target=watch_cancel, daemon=True).start()
    try:
        # One compute task per workspace; queued jobs remain cancellable.
        with (work.parent / 'compute.lock').open('a') as compute:
            fcntl.flock(compute, fcntl.LOCK_EX)
            execute(work, action)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        data = read(work)
        data.update(status='cancelled' if isinstance(exc, InterruptedError) else 'failed', error=str(exc) or type(exc).__name__)
        save(work / 'session.json', data)
        sys.exit(1)
