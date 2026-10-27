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
from mixer_adapter.session import read, save, validate_songs

ROOT = Path(__file__).resolve().parent
BUSY = {'detecting', 'preparing', 'rendering'}


def launch(work, action):
    with (work / 'worker.log').open('ab') as log:
        subprocess.Popen([sys.executable, '-m', 'mixer_adapter.session', str(work), action],
                         cwd=ROOT, stdout=log, stderr=log, start_new_session=True)


def public(data):
    result = {k: data[k] for k in ('id', 'status', 'duration', 'songs', 'progress', 'error', 'preview_tracks', 'detection', 'ai_review') if k in data}
    result['results'] = [{k: v for k, v in r.items() if k != 'path'} for r in data.get('results', [])]
    return result


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
                if action == 'prepare':
                    songs = validate_songs(body.get('songs'), data['duration'])
                    if [(s['start'],s['end']) for s in songs] != [(s['start'],s['end']) for s in data.get('songs', [])]:
                        data['previous_ai_review'] = data.get('ai_review')
                        data['ai_review'] = {'status': 'manual_revision'}
                    # Changed boundaries invalidate extracted PCM and mixes.
                    shutil.rmtree(work / 'songs', ignore_errors=True)
                    shutil.rmtree(work / 'preview', ignore_errors=True)
                    data['songs'] = songs
                    data.pop('preview_tracks', None)
                    data.pop('results', None)
                    data['status'] = 'preparing'
                elif action == 'render':
                    if not data.get('preview_tracks'):
                        return error('Review the song boundaries first.', 409)
                    names = {Path(p).name for p in data['preview_tracks']}
                    settings = {}
                    for key in ('faders', 'mutes', 'base_gains'):
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
                    if 'effects' in body:
                        from mixer_adapter.single_song import validate_effects
                        settings['effects'] = validate_effects(body['effects'], names)
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
