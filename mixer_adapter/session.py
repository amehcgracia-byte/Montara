"""Isolated, disk-backed session detection and per-song rendering.

This module is also the child-process entry point. Vendor globals never live in
the web server. Only a selected song is decoded for the browser's mixer.
"""
from __future__ import annotations

import hashlib
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
ORIGINALS_WAIT_SECONDS = 15 * 60  # an export waiting for ranges gives up after this long without one


def track_window(track, song):
    """(source_start, overlap) of a song inside one track file, in that file's own seconds."""
    offset = float(track['offset'])
    return max(0, song['start'] - offset), min(song['end'], offset + track['duration']) - max(song['start'], offset)


def original_key(file, window):
    """Identity of one received range: the track and the song window it was cut for.

    Not the song number (splits renumber songs) and not session.json (ranges arrive while
    a render is writing it): one small file per range under originals/."""
    return hashlib.sha1(f"{file}@{float(window[0]):.3f}-{float(window[1]):.3f}".encode()).hexdigest()[:20]


def received_originals(work):
    folder = Path(work) / 'originals'
    result = {}
    for path in folder.glob('*.json') if folder.is_dir() else []:
        try:
            result[path.stem] = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
    return result


def register_original(work, window, path):
    (Path(work) / 'originals').mkdir(exist_ok=True)
    save(Path(work) / 'originals' / f"{original_key(window['file'], window['window'])}.json",
         dict(file=window['file'], window=window['window'], start=window['start'], path=str(path)))


EMPTY_LEVEL_DBFS = -45.0   # a track counts as sounding only above this level
EMPTY_MAX_SECONDS = 5.0    # ...for at least this long over the whole session


def empty_tracks(stems, timelines, frame_seconds):
    """File names of tracks that never really sound (detection envelopes, linear amplitude)."""
    import numpy as np
    floor = 10 ** (EMPTY_LEVEL_DBFS / 20)
    result = []
    for stem in stems:
        env = timelines.get(stem.path.name)
        if env is None or not len(env):
            continue
        if float(np.count_nonzero(np.asarray(env) > floor)) * frame_seconds < EMPTY_MAX_SECONDS:
            result.append(stem.path.stem + '.wav')
    return result if len(result) < len(stems) else []   # never leave a session without tracks


def used_tracks(data):
    """The session's tracks minus the empty ones the page has not brought back."""
    empty = set(data.get('empty_tracks') or [])
    return [t for t in data.get('tracks') or [] if t['file'] not in empty]


def song_windows(data, song, received=None):
    """Original ranges one song window needs: one per preview track that plays in it.

    'start' and 'duration' are in the original file's own seconds, with a small margin.
    The key is the track and the window, so a range stays valid however songs are renumbered."""
    previews = data.get('previews') or {}
    received = received or {}
    result = []
    for track in used_tracks(data):
        original = previews.get(track['file'])
        source_start, overlap = track_window(track, song)
        if not original or overlap <= 0:
            continue
        start = max(0.0, source_start - MARGIN)
        window = [round(song['start'], 6), round(song['end'], 6)]
        got = received.get(original_key(track['file'], window))
        result.append(dict(song=song.get('id'), song_name=song.get('name') or '', file=track['file'], original=original,
                           start=round(start, 6), duration=round(source_start - start + overlap + MARGIN, 6), window=window,
                           received=bool(got and Path(got['path']).is_file())))
    return result


def window_song(data, window, song_id=None, name=''):
    """A song made from a [start, end] window the page sends (validated against the session)."""
    if not isinstance(window, (list, tuple)) or len(window) != 2:
        raise ValueError('Invalid song window.')
    start, end = window
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (start, end)):
        raise ValueError('Invalid song window.')
    if start < 0 or end > float(data.get('duration') or 0) + .001 or end - start < .5:
        raise ValueError('Invalid song window.')
    return dict(id=song_id, name=str(name)[:80], start=float(start), end=float(end))


def local_plan(data, song):
    """What the companion needs to mix this song window on the person's computer.

    One entry per used track: the original to find on that computer (name, size, fingerprint),
    and the cut in that file's own seconds (the same numbers prepare_tracks uses). None when a
    track has no original there (it was uploaded whole): that song is mixed on the server."""
    previews = data.get('previews') or {}
    duration = song['end'] - song['start']
    tracks = []
    for track in used_tracks(data):
        original = previews.get(track['file'])
        if not original:
            return None
        source_start, overlap = track_window(track, song)
        tracks.append(dict(file=track['file'], original=original, source_start=round(source_start, 6), overlap=round(overlap, 6),
                           delay_ms=round(max(0, float(track['offset']) - song['start']) * 1000),
                           samplerate=int(track['samplerate']), channels=int(track['channels'])))
    return dict(window=[round(song['start'], 6), round(song['end'], 6)], duration=round(duration, 6), tracks=tracks,
                track_types=data.get('track_types') or {})


def window_key(window):
    return f"{float(window[0]):.3f}-{float(window[1]):.3f}"


def local_results(work):
    """Songs mixed on the person's computer, by window: {window key: {path, window}}."""
    result = {}
    for path in (Path(work) / 'local_results').glob('*.json'):
        try:
            item = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if Path(item.get('path', '')).is_file():
            result[window_key(item['window'])] = item
    return result


def original_windows(data, work=None, only_song=None):
    """Ranges of the originals a preview-based session needs before it can export:
    every selected song (or just `only_song`, a song id)."""
    if not data.get('previews') or not data.get('tracks'):
        return []
    received = received_originals(work) if work else {}
    result = []
    for song in data.get('songs') or []:
        if only_song is not None and song['id'] != only_song:
            continue
        if only_song is None and not song.get('selected'):
            continue
        result += song_windows(data, song, received)
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

    def track_peaks(track):  # decoding is the slow part: all tracks at once, one per core
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', track['path'], '-vn', '-ac', '1', '-ar', str(WAVE_RATE),
                              '-f', 'f32le', '-'], capture_output=True, check=True, timeout=900).stdout
        audio = np.abs(np.frombuffer(raw, dtype='<f4'))
        usable = len(audio) // per * per
        return audio[:usable].reshape(-1, per).max(axis=1) if usable else None

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max(1, min(len(data['tracks']), os.cpu_count() or 2))) as pool:
        columns_by_track = list(pool.map(track_peaks, data['tracks']))
    for track, column in zip(data['tracks'], columns_by_track):
        if column is None:
            continue
        first = int(round(float(track['offset']) / WAVE_STEP))
        end = min(columns, first + len(column))
        if end > first:
            peaks[first:end] = np.maximum(peaks[first:end], column[:end - first])
    top = float(np.percentile(peaks[peaks > 0], 99.5)) if (peaks > 0).any() else 1.0
    result = dict(step=WAVE_STEP, duration=float(data['duration']),
                  peaks=np.clip(peaks / max(top, 1e-6) * 255, 0, 255).astype(int).tolist())
    save(cached, result)
    return result


def waveform_from_timelines(work, timelines, duration, frame_seconds):
    """waveform.json from the detection envelopes (one level per track and frame, already on the session clock)."""
    import numpy as np
    columns = int(math.ceil(float(duration) / WAVE_STEP))
    peaks = np.zeros(columns, dtype='float32')
    for env in timelines.values():
        env = np.asarray(env, dtype='float32')
        if not len(env):
            continue
        index = (np.arange(len(env)) * float(frame_seconds) / WAVE_STEP).astype(int)
        keep = index < columns
        np.maximum.at(peaks, index[keep], env[keep])
    if not (peaks > 0).any():
        raise ValueError('empty envelopes')
    top = float(np.percentile(peaks[peaks > 0], 99.5))
    save(Path(work) / 'waveform.json', dict(step=WAVE_STEP, duration=float(duration), source='detection',
                                             peaks=np.clip(peaks / max(top, 1e-9) * 255, 0, 255).astype(int).tolist()))


LISTEN_RATE = 24000


def listen_percent(work):
    """How much of the listening copy is made, 0-100."""
    work = Path(work)
    if (work / 'listen-all.webm').is_file():
        return 100
    try:
        return min(100, int((work / 'listen.progress').read_text()))
    except (OSError, ValueError):
        return 0


def session_listen(work):
    """One light listening copy of the whole session (all tracks, offsets honoured).

    Made once; the page seeks inside it, so moving a cut or jumping to a point never
    waits for the server. Rough equal-level mix for checking cuts, not the export.
    One decoder per track, summed here and resampled once: a single ffmpeg with amix does it
    all on one core (a 9-track jam of 1h56 took 7 minutes, against 79 s for finding its songs)."""
    import threading
    import numpy as np
    from concurrent.futures import ThreadPoolExecutor
    work = Path(work)
    target = work / 'listen-all.webm'
    if target.is_file():
        return target
    data = read(work)
    duration = float(data.get('duration') or 0)
    rate = max(int(track['samplerate']) for track in data['tracks'])
    samples_at_once = rate * 10
    # WebM keeps a seek index: jumps are instant in the browser. Own name: two requests never share a file.
    pending = target.with_name(f'listen-all.{os.getpid()}-{threading.get_ident()}.part.webm')
    decoders = [(round(float(track['offset']) * rate),
                 subprocess.Popen(['ffmpeg', '-v', 'error', '-nostdin', '-i', track['path'], '-map', '0:a:0', '-ac', '1', '-ar', str(rate),
                                   '-f', 'f32le', '-'], stdout=subprocess.PIPE)) for track in data['tracks']]
    encoder = subprocess.Popen(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-f', 'f32le', '-ar', str(rate), '-ac', '1', '-i', '-',
                                '-af', f'aresample={LISTEN_RATE},dynaudnorm=f=500:g=31,alimiter=limit=0.9', '-c:a', 'libopus', '-b:a', '40k', '-compression_level', '5',
                                '-application', 'audio', '-f', 'webm', str(pending)], stdin=subprocess.PIPE)
    processes = [encoder, *(process for _, process in decoders)]

    def stop():
        for process in processes:
            process.kill()

    def track_block(decoder, start):
        delay, process = decoder
        silence = min(samples_at_once, max(0, delay - start))
        raw = process.stdout.read((samples_at_once - silence) * 4) if silence < samples_at_once else b''
        return silence, np.frombuffer(raw, 'float32', len(raw) // 4)

    def mixed_block(pool, start):
        mix = np.zeros(samples_at_once, 'float32')
        used = 0
        for silence, samples in pool.map(lambda decoder: track_block(decoder, start), decoders):
            mix[silence:silence + len(samples)] += samples
            used = max(used, silence + len(samples))
        return mix[:used]

    watchdog = threading.Timer(3600, stop)
    watchdog.start()
    try:
        made = 0
        with ThreadPoolExecutor(max_workers=len(decoders)) as pool, ThreadPoolExecutor(max_workers=1) as reader:
            ahead = reader.submit(mixed_block, pool, 0)  # the next block is decoded while this one is encoded
            while True:
                block = ahead.result()
                if not len(block):
                    break
                made += len(block)
                ahead = reader.submit(mixed_block, pool, made)
                encoder.stdin.write(block.tobytes())
                if duration:
                    (work / 'listen.progress').write_text(str(int(made / rate / duration * 100)))
        encoder.stdin.close()
        for process in processes:
            if process.wait() != 0:
                raise subprocess.CalledProcessError(process.returncode, process.args)
        pending.replace(target)
        return target
    except BrokenPipeError as exc:  # the encoder stopped early
        raise subprocess.CalledProcessError(encoder.wait(), encoder.args) from exc
    finally:
        watchdog.cancel()
        stop()
        for _, process in decoders:
            process.stdout.close()
        pending.unlink(missing_ok=True)
        (work / 'listen.progress').unlink(missing_ok=True)


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
    needed = sum(int(duration * t['samplerate'] * min(t['channels'], 2) * 4) for t in used_tracks(data))
    if shutil.disk_usage(work).free < needed * (1 if preview else 4) + 128 * 1024**2:
        raise ValueError('Not enough working space for this song. Free space or choose a shorter interval.')
    for track in used_tracks(data):
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
        original = None if preview else received_originals(work).get(original_key(track['file'], [round(song['start'], 6), round(song['end'], 6)]))
        if original and Path(original['path']).is_file():
            source, source_start = original['path'], source_start - float(original['start'])
        elif not preview and track['file'] in (data.get('previews') or {}) and overlap > 0:
            raise ValueError(f"The original of {track['file']} for {song['name']} has not arrived. Keep the companion open and export again.")
        temporary = target.with_suffix('.partial.wav')
        from mixer_adapter.extract import window_command  # the companion's local mixer uses the same command
        subprocess.run(window_command('ffmpeg', source, source_start, overlap, delay_ms, duration,
                                      track['channels'], track['samplerate'], str(temporary)), check=True)
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
    present = {p.name for p in folder.glob('*.wav')}
    only = lambda values: None if values is None else {k: v for k, v in values.items() if k in present}  # empty tracks are not mixed
    mine = {k: only(v) if k in ('faders', 'mutes', 'effects', 'eq') and isinstance(v, dict) else v for k, v in mine.items()}
    settings = {k: only(v) if k in ('faders', 'mutes', 'effects') and isinstance(v, dict) else v for k, v in settings.items()}
    mixer = SingleSongMix(folder, work / 'songs' / str(song_id) / 'mix', reference=mine.get('reference') or settings.get('reference'),
                          track_types=data.get('track_types'))
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
        if action == 'detect' and 'progress' in data['progress']:  # one bar for both: the songs and the listening copy
            data['progress']['progress'] = min(data['progress']['progress'], listen_percent(work))
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
        import track_types  # the person's track types: detection weighs instruments and voices by role
        stems = track_types.apply(pipeline, stems, track_types.for_files(data.get('track_types'), [s.path.name for s in stems]))
        origin = min(s.offset_seconds for s in stems)
        from dataclasses import replace
        stems = [replace(s, offset_seconds=s.offset_seconds - origin) for s in stems]
        data['duration'] = max(s.offset_seconds + s.duration for s in stems)
        data['tracks'] = [dict(file=s.path.stem + '.wav', path=str(s.path), samplerate=s.samplerate,
                               channels=s.channels, offset=s.offset_seconds, duration=s.duration) for s in stems]
        # The listening copy only needs the tracks and their offsets: make it in the
        # background now, while the songs are being found; the review waits for it.
        save(work / 'session.json', data)
        with (work / 'extras.log').open('ab') as log:
            extras = subprocess.Popen([sys.executable, '-m', 'mixer_adapter.session', str(work), 'extras'], cwd=Path(__file__).resolve().parents[1],
                                      stdout=log, stderr=log, start_new_session=True)
        timelines = pipeline.ensure_detection_cache(stems)
        # Tracks with no sound in the whole session (a channel left open for another band):
        # never uploaded as originals, never mixed. The page shows them and can bring one back.
        data['empty_tracks'] = empty_tracks(stems, timelines, pipeline.DETECTION_FRAME_SECONDS)
        save(work / 'session.json', data)
        try:  # the waveform comes from the envelopes detection just computed: no second decode
            waveform_from_timelines(work, timelines, data['duration'], pipeline.DETECTION_FRAME_SECONDS)
        except Exception as exc:
            print('waveform from envelopes failed:', exc, flush=True)
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
        # The review opens with the play buttons ready: the same bar waits for the listening copy.
        while extras.poll() is None:
            progress(dict(current_stage='Preparing the listening copy', stage_detail='getting the songs ready to play', progress=100))
            time.sleep(1)
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
        # Songs already mixed on the person's computer (companion) are taken as they are.
        local = local_results(work)
        for song in selected:
            done = local.get(window_key([song['start'], song['end']]))
            if done:
                data['results'].append(dict(id=song['id'], name=song['name'], start=song['start'], end=song['end'], path=done['path'], local=True))
        local_ids = {r['id'] for r in data['results']}
        save(work / 'session.json', data)
        pending, running, finished = [s for s in selected if s['id'] not in local_ids], {}, len(local_ids)
        slots = max(1, min(len(pending), parallel_songs()))
        root = Path(__file__).resolve().parents[1]
        # With previews, a song starts as soon as its original ranges have arrived from the
        # person's computer: mixing song 1 overlaps with uploading song 2.
        def ready(song):
            return all(w['received'] for w in original_windows(data, work, song['id']))
        last_arrival, last_count = time.time(), -1
        with (work / 'worker.log').open('ab') as log:
            try:
                while pending or running:
                    while len(running) < slots and (song := next((s for s in pending if ready(s)), None)):
                        pending.remove(song)
                        running[song['id']] = (song, subprocess.Popen([sys.executable, '-m', 'mixer_adapter.session', str(work), 'render-song', str(song['id'])],
                                                                      cwd=root, stdout=log, stderr=log))
                    count = len(received_originals(work))
                    if count != last_count:
                        last_arrival, last_count = time.time(), count
                    if pending and not running and time.time() - last_arrival > ORIGINALS_WAIT_SECONDS:
                        raise RuntimeError('The original audio stopped arriving from your computer. Keep Montara and the companion open, then export again: songs already mixed are kept.')
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
                    waiting = '' if running or not pending else ' · waiting for the original audio of the next song'
                    progress(dict(current_stage='mixing songs', stage_detail=f'{finished} of {len(selected)} done' + (f' · now: {names}' if names else '') + waiting,
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
    # Durations for docs/lab/RUNS.md (deploy/vm/run_history.py reads them).
    data.setdefault('timings', {})[action] = round(time.time() - float(data.get('started_at') or time.time()), 1)
    save(work / 'session.json', data)


if __name__ == '__main__':
    work, action = Path(sys.argv[1]), sys.argv[2]
    if action == 'render-song':  # child of a render; the parent holds the locks and handles cancel
        render_song(work, int(sys.argv[3]))
        sys.exit(0)
    if action == 'extras':  # during detection: the listening copy; no locks
        try:
            session_listen(work)
        except Exception as exc:
            print('session_listen failed:', exc, flush=True)
        (work / 'extras.done').touch()
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
