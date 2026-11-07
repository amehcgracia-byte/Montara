"""Standalone finishing of one already-mixed track; no stem rebalance or EQ."""
from __future__ import annotations
import json
from contextlib import suppress
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import uuid


def register_mastering(app, data_root: Path, fixtures: Path):
    from flask import jsonify, request, send_file
    from mixer_adapter.source_access import resolve_mix_sources
    jobs = {}
    slot = threading.Lock()
    app.extensions['montara_mastering_jobs'] = jobs

    def persist(folder, value):
        pending = folder / 'job.tmp'
        pending.write_text(json.dumps(value))
        pending.replace(folder / 'job.json')

    # A server restart interrupts an in-memory worker; never advertise it as live.
    for record in (data_root / 'Mastering').glob('*/job.json'):
        try:
            previous = json.loads(record.read_text())
            if previous.get('status') in {'queued', 'running'}:
                previous.update(status='failed', error='Mastering was interrupted. Add your finished mix again to retry.')
                persist(record.parent, previous)
        except (OSError, ValueError):
            continue

    def public(job):
        return {k: job.get(k) for k in ('id', 'status', 'phase', 'error', 'before', 'after')}

    def run(job, args):
        if job.get('cancelled'):
            raise RuntimeError('Cancelled')
        executable = shutil.which(os.environ.get('FFMPEG_BINARY', 'ffmpeg'))
        if not executable:
            raise RuntimeError('FFmpeg is unavailable')
        process = subprocess.Popen([executable, '-hide_banner', '-nostdin', '-y', *args],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        job['process'] = process
        if job.get('cancelled'):
            with suppress(ProcessLookupError):
                process.terminate()
        _, stderr = process.communicate()
        job.pop('process', None)
        if job.get('cancelled'):
            raise RuntimeError('Cancelled')
        if process.returncode:
            raise RuntimeError('Audio processing failed; the source may be damaged or unsupported.')
        return stderr

    def measure(job, source):
        text = run(job, ['-i', str(source), '-map', '0:a:0', '-vn', '-af',
                         'loudnorm=I=-15:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'])
        matches = re.findall(r'\{\s*"input_i".*?\}', text, re.S)
        if not matches:
            raise RuntimeError('Could not measure this audio')
        result = json.loads(matches[-1])
        if not all(math.isfinite(float(result[k])) for k in ('input_i', 'input_tp', 'input_lra', 'input_thresh', 'target_offset')):
            raise RuntimeError('No measurable audio. Choose a track containing sound.')
        return result

    def worker(job, source, folder):
        with slot:
            try:
                job.update(status='running', phase='Measuring your finished mix…')
                before = measure(job, source)
                job['before'] = {'lufs': float(before['input_i']), 'true_peak_db': float(before['input_tp'])}
                job['phase'] = 'Mastering without changing the instrument balance…'
                settings = ':'.join(f'{key}={before[value]}' for key, value in (
                    ('measured_I', 'input_i'), ('measured_TP', 'input_tp'),
                    ('measured_LRA', 'input_lra'), ('measured_thresh', 'input_thresh'), ('offset', 'target_offset')))
                pcm = folder / 'master.wav'
                result = folder / 'master.mp3'
                run(job, ['-i', str(source), '-map', '0:a:0', '-vn', '-map_metadata', '-1', '-map_chapters', '-1',
                          '-af', f'loudnorm=I=-15:TP=-1.5:LRA=11:{settings}:linear=true',
                          '-ar', '48000', '-c:a', 'pcm_f32le', str(pcm)])
                attenuation = 0.0
                for _ in range(3):
                    job['phase'] = 'Checking the peaks in the final MP3…'
                    run(job, ['-i', str(pcm), '-map', '0:a:0', '-vn', '-map_metadata', '-1', '-map_chapters', '-1',
                              '-af', f'volume={attenuation:.4f}dB', '-c:a', 'libmp3lame', '-b:a', '320k', str(result)])
                    after = measure(job, result)
                    peak = float(after['input_tp'])
                    if peak <= -1.0:
                        break
                    attenuation -= peak + 1.25
                else:
                    raise RuntimeError('The final peak check failed. No master was released.')
                job['after'] = {'lufs': float(after['input_i']), 'true_peak_db': peak}
                job.update(status='done', phase='Your master is ready.', result=result)
            except Exception as exc:
                job.update(status='cancelled' if job.get('cancelled') else 'failed', error=str(exc))
            finally:
                (folder / 'master.wav').unlink(missing_ok=True)
                if job['status'] != 'done':
                    (folder / 'master.mp3').unlink(missing_ok=True)
                # Save only the outcome; server-owned original upload stays intact.
                persist(folder, public(job))

    @app.post('/montara/master')
    def start():
        body = request.get_json(silent=True) or {}
        try:
            sources = resolve_mix_sources(body.get('tracks'), data_root, fixtures,
                                          remote=bool(os.environ.get('MONTARA_SESSION_TOKEN')))
            if len(sources) != 1:
                raise ValueError('Mastering needs one finished mix, not separate instrument tracks.')
            from resumable_upload import preview_original
            if preview_original(sources[0]):
                raise ValueError('Use the full-quality finished mix for mastering, not a session preview.')
        except ValueError as exc:
            return jsonify(error={'message': str(exc)}), 400
        if sum(j['status'] in {'queued', 'running'} for j in jobs.values()) >= 4:
            return jsonify(error={'message': 'Mastering is busy. Try again when the current jobs finish.'}), 429
        key = uuid.uuid4().hex[:12]
        folder = data_root / 'Mastering' / key
        folder.mkdir(parents=True)
        job = jobs[key] = {'id': key, 'status': 'queued', 'phase': 'Waiting to master…'}
        persist(folder, public(job))
        threading.Thread(target=worker, args=(job, sources[0], folder), daemon=True).start()
        return jsonify(public(job)), 202

    @app.get('/montara/master/<key>')
    def status(key):
        job = jobs.get(key)
        if job is None and re.fullmatch('[a-f0-9]{12}', key):
            record = data_root / 'Mastering' / key / 'job.json'
            if record.is_file():
                job = json.loads(record.read_text())
        return (jsonify(public(job)), 200) if job else (jsonify(error={'message': 'Unknown master'}), 404)

    @app.delete('/montara/master/<key>')
    def cancel(key):
        job = jobs.get(key)
        if not job:
            return jsonify(error={'message': 'Unknown master'}), 404
        if job['status'] not in {'done', 'failed', 'cancelled'}:
            job['cancelled'] = True
            process = job.get('process')
            if process and process.poll() is None:
                with suppress(ProcessLookupError):
                    process.terminate()
        return jsonify(public(job))

    @app.get('/montara/master/<key>/result')
    def result(key):
        if not re.fullmatch('[a-f0-9]{12}', key):
            return jsonify(error={'message': 'Unknown master'}), 404
        folder = data_root / 'Mastering' / key
        record = folder / 'job.json'
        ready = jobs.get(key, {}).get('status') == 'done' or (record.is_file() and json.loads(record.read_text()).get('status') == 'done')
        if not ready:
            return jsonify(error={'message': 'The master is not ready'}), 409
        return send_file(folder / 'master.mp3', mimetype='audio/mpeg', conditional=True)
