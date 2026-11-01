"""HTTP boundary for full musical sessions. No vendor state in Flask threads."""
from __future__ import annotations

import fcntl
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

from flask import jsonify, request, send_file
from mixer_adapter.session import (listen_range, original_windows, read, received_originals, register_original, save, session_listen,
                                   session_waveform, song_windows, validate_songs, window_song, original_key,
                                   local_plan, window_key)
from resumable_upload import preview_original

ROOT = Path(__file__).resolve().parent
BUSY = {'detecting', 'preparing', 'rendering'}


def launch(work, action):
    with (work / 'worker.log').open('ab') as log:
        subprocess.Popen([sys.executable, '-m', 'mixer_adapter.session', str(work), action],
                         cwd=ROOT, stdout=log, stderr=log, start_new_session=True)


def public(data):
    result = {k: data[k] for k in ('id', 'status', 'duration', 'songs', 'progress', 'error', 'preview_tracks', 'detection', 'ai_review') if k in data}
    result['results'] = [{k: v for k, v in r.items() if k != 'path'} for r in data.get('results', [])]
    result['uses_previews'] = bool(data.get('previews'))
    result['track_files'] = [t['file'] for t in data.get('tracks') or []]
    result['empty_tracks'] = list(data.get('empty_tracks') or [])
    return result


def extras_running(work):
    """The background listening-copy step started and has not finished."""
    return (work / 'extras.log').is_file() and not (work / 'extras.done').is_file()


def mix_settings(body, names):
    """Fader offsets, mutes and effects the person changed for one mix (validated)."""
    settings = {}
    for key in ('faders', 'mutes'):
        values = body.get(key, {})
        if not isinstance(values, dict) or set(values) - names:
            raise ValueError('Unknown track settings.')
        for value in values.values():
            if key == 'mutes':
                if not isinstance(value, bool):
                    raise ValueError('Mute must be on or off.')
            elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not -100 <= value <= 100:
                raise ValueError('Invalid fader level.')
        settings[key] = values
    from mixer_adapter.single_song import validate_effects, validate_eq
    if 'effects' in body:
        settings['effects'] = validate_effects(body['effects'], names)
    if body.get('eq'):
        settings['eq'] = validate_eq(body['eq'], names)
    return settings


def register_full_session(app, data_root, fixtures):
    root = Path(data_root).resolve() / 'Sessions'
    allowed = (Path(data_root).resolve(), Path(fixtures).resolve())

    def folder(job_id):
        if not re.fullmatch('[a-f0-9]{12}', job_id):
            raise ValueError('Unknown session.')
        work = root / job_id
        if not (work / 'session.json').is_file():
            raise ValueError('Unknown session.')
        return work

    def error(exc, status=400):
        return jsonify(error={'message': str(exc)}), status

    @app.post('/montara/session')
    def session_start():
        body = request.get_json(silent=True) or {}
        paths = body.get('tracks')
        if not isinstance(paths, list) or not 1 <= len(paths) <= 128:
            return error('Add between 1 and 128 audio tracks.')
        files = []
        for raw in paths:
            if not isinstance(raw, str):
                return error('Invalid audio track.')
            path = Path(raw).resolve()
            if not any(path.is_relative_to(a) for a in allowed) or not path.is_file() or path.suffix.lower() not in {'.wav', '.mp3', '.flac', '.aif', '.aiff', '.m4a', '.ogg'}:
                return error('Choose audio from your own session.')
            files.append(path)
        if len(set(files)) != len(files) or len({p.stem.casefold() for p in files}) != len(files):
            return error('Use a different name for each audio track.')
        job_id = uuid.uuid4().hex[:12]
        work = root / job_id
        (work / 'tracks').mkdir(parents=True)
        try:
            for path in files:
                # Never duplicate multi-GB source tracks just to register a folder.
                (work / 'tracks' / path.name).symlink_to(path)
            data = dict(id=job_id, ai_data_root=str(Path(data_root).resolve()), status='detecting', started_at=time.time(), progress={'current_stage': 'Inspecting session', 'progress': 0})
            # Light previews from the companion: the export asks for the original song ranges.
            previews = {p.stem + '.wav': o for p in files if (o := preview_original(p))}
            if previews:
                data['previews'] = previews
            import track_types
            if types := track_types.validate(body.get('track_types')):
                data['track_types'] = types
            save(work / 'session.json', data)
            launch(work, 'detect')
        except Exception:
            shutil.rmtree(work)
            raise
        return jsonify(public(data)), 202

    @app.get('/montara/session/<job_id>')
    def session_status(job_id):
        try:
            work = folder(job_id)
            with (work / 'request.lock').open('a') as control:
                fcntl.flock(control, fcntl.LOCK_EX)
                data = read(work)
                if data['status'] in BUSY and time.time() - data.get('started_at', 0) > 10:
                    with (work / 'worker.lock').open('a') as lock:
                        try:
                            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        except BlockingIOError:
                            pass  # Child process still owns the job, even after a web restart.
                        else:
                            data.update(status='failed', error='The session worker stopped. Your originals and reviewed cuts are preserved.')
                            save(work / 'session.json', data)
                return jsonify(public(data))
        except ValueError as exc:
            return error(exc, 404)

    @app.post('/montara/session/<job_id>/<action>')
    def session_action(job_id, action):
        try:
            work = folder(job_id)
            with (work / 'request.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                data = read(work)
                if action == 'cancel':
                    if data['status'] in BUSY:
                        (work / 'cancel').touch()
                    return jsonify(public(data)), 202
                if data['status'] in BUSY:
                    return error('Wait for this session to finish or cancel it.', 409)
                body = request.get_json(silent=True) or {}
                if action == 'include':  # the person brings back a track detection found empty
                    if body.get('file') not in (data.get('empty_tracks') or []):
                        raise ValueError('This track is already used.')
                    data['empty_tracks'] = [f for f in data['empty_tracks'] if f != body['file']]
                    shutil.rmtree(work / 'songs', ignore_errors=True)
                    shutil.rmtree(work / 'preview', ignore_errors=True)
                    data.pop('preview_tracks', None)
                    save(work / 'session.json', data)
                    return jsonify(public(data))
                if action in ('prepare', 'render', 'songs') and body.get('songs') is not None:
                    songs = validate_songs(body.get('songs'), data['duration'])
                    key = lambda items: [(s.get('id'), s.get('start'), s.get('end'), s.get('selected', True)) for s in items]
                    if [(s['start'], s['end']) for s in songs] != [(s['start'], s['end']) for s in data.get('songs', [])]:
                        data['previous_ai_review'] = data.get('ai_review')
                        data['ai_review'] = {'status': 'manual_revision'}
                    if key(songs) != key(data.get('songs', [])):
                        # Changed boundaries invalidate extracted PCM and mixes. Received original
                        # ranges stay: each one belongs to the exact window it was cut for.
                        shutil.rmtree(work / 'songs', ignore_errors=True)
                    data['songs'] = songs
                elif action in ('prepare', 'songs'):
                    raise ValueError('Send the songs.')
                if action == 'songs':  # boundaries saved; nothing to run
                    save(work / 'session.json', data)
                    return jsonify(public(data))
                if action == 'prepare':
                    data['preview_song'] = body.get('song') if isinstance(body.get('song'), int) else None
                    shutil.rmtree(work / 'preview', ignore_errors=True)
                    data.pop('preview_tracks', None)
                    data.pop('results', None)
                    data['status'] = 'preparing'
                elif action == 'render':
                    if not data.get('songs') or not data.get('tracks'):
                        return error('Review the song boundaries first.', 409)
                    names = {t['file'] for t in data['tracks']}
                    settings = mix_settings(body, names)
                    per_song = body.get('per_song') or {}
                    ids = {str(s['id']) for s in data['songs']}
                    if not isinstance(per_song, dict) or set(per_song) - ids:
                        raise ValueError('Unknown song mix.')
                    settings['per_song'] = {key: mix_settings(value, names) for key, value in per_song.items() if isinstance(value, dict)}
                    if body.get('reference'):
                        reference = Path(str(body['reference'])).resolve()
                        if not any(reference.is_relative_to(a) for a in allowed) or not reference.is_file():
                            raise ValueError('Choose a reference from this session.')
                        settings['reference'] = str(reference)
                    data['settings'] = settings
                    data['status'] = 'rendering'
                else:
                    return error('Unknown session action.', 404)
                (work / 'cancel').unlink(missing_ok=True)
                data.pop('error', None)
                data['progress'] = {'current_stage': data['status'], 'progress': 0}
                data['started_at'] = time.time()
                save(work / 'session.json', data)
                try:
                    launch(work, action)
                except Exception:
                    data.update(status='failed', error='Could not start the session worker. Please retry.')
                    save(work / 'session.json', data)
                    raise
                return jsonify(public(data)), 202
        except ValueError as exc:
            return error(exc)

    @app.get('/montara/session/<job_id>/waveform')
    def session_wave_route(job_id):
        try:
            work = folder(job_id)
            data = read(work)
            if data['status'] in BUSY or not data.get('tracks'):
                return error('Not ready yet.', 409)
            if not (work / 'waveform.json').is_file() and extras_running(work):
                return jsonify(pending=True), 202  # being drawn in the background; the page asks again
            return jsonify(session_waveform(work))
        except ValueError as exc:
            return error(exc, 404)

    @app.get('/montara/session/<job_id>/listen')
    def session_listen_route(job_id):
        try:
            work = folder(job_id)
            if not read(work).get('tracks'):
                return error('Not ready yet.', 409)
            if 'start' not in request.args:  # the whole session, seekable (HTTP ranges)
                if not (work / 'listen-all.webm').is_file():
                    if extras_running(work):
                        return error('The listening copy is being prepared. Try again in a minute.', 409)
                    if read(work)['status'] in BUSY:
                        return error('Not ready yet.', 409)
                return send_file(session_listen(work), mimetype='audio/webm', conditional=True, max_age=3600)
            start, end = float(request.args.get('start', 'nan')), float(request.args.get('end', 'nan'))
            if not (math.isfinite(start) and math.isfinite(end)):
                raise ValueError('Invalid range.')
            return send_file(listen_range(work, start, end), mimetype='audio/ogg', conditional=True)
        except (ValueError, subprocess.CalledProcessError) as exc:
            return error(exc if isinstance(exc, ValueError) else 'Could not prepare this range.')

    @app.get('/montara/session/<job_id>/originals')
    def session_originals(job_id):
        """Song ranges of the originals the export still needs (only when the tracks are previews)."""
        try:
            work = folder(job_id)
            song = request.args.get('song', type=int)
            data = read(work)
            if request.args.get('start') is not None:  # a window the page has not saved yet (Confirm)
                target = window_song(data, [request.args.get('start', type=float), request.args.get('end', type=float)], song,
                                     request.args.get('name', ''))
                return jsonify(originals=song_windows(data, target, received_originals(work)))
            return jsonify(originals=original_windows(data, work, song))
        except ValueError as exc:
            return error(exc, 404)

    def mixer_commit():
        """The mixer the server renders with; the companion mixes locally only with the same one."""
        import subprocess as sp
        out = sp.run(['git', '-C', str(ROOT / 'mixer'), 'rev-parse', 'HEAD'], capture_output=True, text=True)
        return out.stdout.strip() if out.returncode == 0 else ''

    @app.get('/montara/session/<job_id>/local-plan')
    def session_local_plan(job_id):
        """One song window, as the companion mixes it on the person's computer (same cuts, same mixer)."""
        try:
            work = folder(job_id)
            data = read(work)
            song = window_song(data, [request.args.get('start', type=float), request.args.get('end', type=float)],
                               request.args.get('song', type=int), request.args.get('name', ''))
            plan = local_plan(data, song)
            if plan is None:
                return error('These tracks were uploaded whole: this song is mixed on the server.', 409)
            return jsonify({**plan, 'mixer': mixer_commit()})
        except ValueError as exc:
            return error(exc)

    @app.post('/montara/session/<job_id>/local-result')
    def session_local_result(job_id):
        """The MP3 of a song the companion mixed: kept for that window; the export then skips it."""
        try:
            work = folder(job_id)
            data = read(work)
            body = request.get_json(silent=True) or {}
            song = window_song(data, body.get('window'), body.get('song'))
            uploads = (Path(data_root).resolve() / 'Uploads').resolve()
            upload_id = str(body.get('upload_id') or '')
            if not re.fullmatch('[a-f0-9]{32}', upload_id):
                raise ValueError('Unknown upload.')
            record = json.loads((uploads / upload_id / 'upload.json').read_text()) if (uploads / upload_id / 'upload.json').is_file() else {}
            if not record.get('complete'):
                raise ValueError('Finish this upload first.')
            source = (uploads / upload_id / record.get('restored', record['name'])).resolve()
            if not source.is_relative_to(uploads) or not source.is_file() or source.suffix.lower() != '.mp3':
                raise ValueError('Send the song as MP3.')
            key = window_key([song['start'], song['end']])
            target = work / 'exports' / f'local-{key}.mp3'
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), target)
            (work / 'local_results').mkdir(exist_ok=True)
            save(work / 'local_results' / f'{key}.json', dict(window=[song['start'], song['end']], path=str(target),
                                                               mixer=str(body.get('mixer') or '')[:40], seconds=body.get('seconds')))
            shutil.rmtree(uploads / upload_id, ignore_errors=True)
            return jsonify(ok=True, window=[song['start'], song['end']])
        except ValueError as exc:
            return error(exc)

    @app.post('/montara/session/<job_id>/originals')
    def session_original_received(job_id):
        try:
            work = folder(job_id)
            body = request.get_json(silent=True) or {}
            uploads = (Path(data_root).resolve() / 'Uploads').resolve()
            upload_id = str(body.get('upload_id') or '')
            if not re.fullmatch('[a-f0-9]{32}', upload_id):
                raise ValueError('Unknown upload.')
            record = json.loads((uploads / upload_id / 'upload.json').read_text()) if (uploads / upload_id / 'upload.json').is_file() else {}
            if not record.get('complete'):
                raise ValueError('Finish this upload first.')
            path = (uploads / upload_id / record.get('restored', record['name'])).resolve()
            if not path.is_relative_to(uploads) or not path.is_file() or path.suffix.lower() != '.wav':
                raise ValueError('Send the original as lossless audio.')
            # Accepted while an export runs: ranges are separate files, not session.json.
            data = read(work)
            # The range belongs to the window it was cut for, not to a song number: songs may
            # have been split, removed or renumbered since it was queued.
            if body.get('window') is not None:
                needed = song_windows(data, window_song(data, body['window'], body.get('song')))
            else:
                needed = original_windows(data, work, body.get('song'))
            window = next((w for w in needed if w['file'] == body.get('file')), None)
            if not window:
                raise ValueError('This song range is not needed.')
            # Server-side window (never the browser's numbers) decides where the range starts.
            register_original(work, window, path)
            received = received_originals(work)
            return jsonify(originals=[dict(w, received=bool(received.get(original_key(w['file'], w['window'])))) for w in needed])
        except ValueError as exc:
            return error(exc)

    @app.get('/montara/session/<job_id>/results.zip')
    def session_results_zip(job_id):
        """Every exported song in one download (MP3s are already compressed: stored, not deflated)."""
        import zipfile
        try:
            work = folder(job_id)
            data = read(work)
            results = [r for r in data.get('results', []) if Path(r['path']).resolve().is_relative_to(work.resolve()) and Path(r['path']).is_file()]
            if not results:
                return error('No exported songs yet.', 404)
            target = work / 'exports' / 'songs.zip'
            pending = target.with_suffix('.part')
            used = set()
            with zipfile.ZipFile(pending, 'w', zipfile.ZIP_STORED) as archive:
                for index, result in enumerate(results, 1):
                    title = re.sub(r'[^\w .-]', '_', result['name']).strip() or 'Song'  # no backslash inside f-strings (Python 3.11)
                    name = f'{index:02d} - {title}.mp3'
                    while name in used:
                        name = name[:-4] + ' (2).mp3'
                    used.add(name)
                    archive.write(result['path'], name)
            pending.replace(target)
            return send_file(target, mimetype='application/zip', as_attachment=True, download_name='Montara session.zip')
        except ValueError as exc:
            return error(exc, 404)

    @app.get('/montara/session/<job_id>/result/<int:song_id>')
    def session_result(job_id, song_id):
        try:
            work = folder(job_id)
            data = read(work)
            result = next((r for r in data.get('results', []) if r['id'] == song_id), None)
            if not result:
                return error('This song has not been exported yet.', 404)
            path = Path(result['path']).resolve()
            if not path.is_relative_to(work.resolve()) or not path.is_file():
                return error('This export is unavailable.', 404)
            return send_file(path, mimetype='audio/mpeg', as_attachment=request.args.get('download') == '1',
                             download_name=re.sub(r'[^\w .-]', '_', result['name']) + '.mp3')
        except ValueError as exc:
            return error(exc, 404)
