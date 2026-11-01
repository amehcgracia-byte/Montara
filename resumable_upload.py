"""Bounded, resumable local/server uploads; originals stay on disk.

The small public preview keeps its existing 256 MiB per-file ceiling. A server
without that preview token may accept 30 GiB, subject to actual free space.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from flask import jsonify, request
from mixer_adapter.session import save

CHUNK = 4 * 1024**2
RESERVE = 128 * 1024**2
LOSSLESS = ('.wav.flac', '.aif.flac', '.aiff.flac', '.wav.wv', '.aif.wv', '.aiff.wv')  # the companion's lossless copy of a WAV/AIFF original
PREVIEW = ('.wav.opus', '.aif.opus', '.aiff.opus')  # the companion's light preview of a full-session track
RANGE = ('.wav.hq.opus', '.aif.hq.opus', '.aiff.hq.opus')  # Fast export: one song range of an original, high-bitrate Opus
PCM = {'8': 'pcm_u8', '16': 'pcm_s16le', '24': 'pcm_s24le', '32': 'pcm_s32le'}
MEDIA = {'.mp4', '.mov', '.mkv', '.webm', '.mts', '.m2ts', '.wav', '.mp3', '.flac', '.aif', '.aiff', '.m4a', '.ogg', '.opus', '.wv'}


def ffmpeg_tool(name):
    return os.environ.get('MONTARA_' + name.upper()) or shutil.which(name) or name


def restore_lossless(path: Path) -> Path:
    """Turn the companion's FLAC back into the WAV the person recorded: same samples, same bit depth,
    same BWF time reference (the mixer aligns tracks with it). The mixer never sees the FLAC."""
    target = path.with_name(path.name[:-len(path.suffix)].rsplit('.', 1)[0] + '.wav')
    if target.is_file():
        return target
    info = subprocess.run([ffmpeg_tool('ffprobe'), '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=sample_fmt,bits_per_raw_sample',
                           '-of', 'default=nw=1:nk=1', str(path)], capture_output=True, text=True, timeout=60).stdout.split()
    fmt, bits = (info + ['', ''])[:2]
    codec = 'pcm_f64le' if fmt.startswith('dbl') else 'pcm_f32le' if fmt.startswith('flt') else PCM.get(bits)
    if not codec:
        raise ValueError(f'Unsupported lossless audio ({bits or "unknown"} bit). Upload the original WAV.')
    pending = target.with_name(target.stem + '.partial.wav')
    done = subprocess.run([ffmpeg_tool('ffmpeg'), '-v', 'error', '-nostdin', '-y', '-i', str(path), '-map', '0:a:0', '-c:a', codec,
                           '-write_bext', '1', '-rf64', 'auto', str(pending)], capture_output=True, text=True, timeout=3600)
    if done.returncode != 0:
        pending.unlink(missing_ok=True)
        raise ValueError('Could not restore the WAV from its lossless copy: ' + (done.stderr.strip().splitlines() or ['FFmpeg failed'])[-1])
    pending.replace(target)
    path.unlink()
    return target


def restore_preview(path: Path) -> Path:
    """Decode the companion's Opus preview to a WAV at the original rate, keeping the BWF time
    reference, so song detection and the browser mixer work as with the original. Never exported:
    the session asks for the original song ranges before it renders."""
    target = path.with_name(path.name[:-len('.opus')].rsplit('.', 1)[0] + '.wav')
    if target.is_file():
        return target
    tags = subprocess.run([ffmpeg_tool('ffprobe'), '-v', 'error', '-select_streams', 'a:0', '-show_entries',
                           'stream_tags=montara_sample_rate', '-of', 'default=nw=1:nk=1', str(path)],
                          capture_output=True, text=True, timeout=60).stdout.split()
    rate = tags[0] if tags and tags[0].isdigit() and 8000 <= int(tags[0]) <= 384000 else '48000'
    pending = target.with_name(target.stem + '.partial.wav')
    done = subprocess.run([ffmpeg_tool('ffmpeg'), '-v', 'error', '-nostdin', '-y', '-i', str(path), '-map', '0:a:0', '-map_metadata', '0:s:a:0',
                           '-ar', rate, '-c:a', 'pcm_s24le', '-write_bext', '1', '-rf64', 'auto', str(pending)],
                          capture_output=True, text=True, timeout=3600)
    if done.returncode != 0:
        pending.unlink(missing_ok=True)
        raise ValueError('Could not read the audio preview: ' + (done.stderr.strip().splitlines() or ['FFmpeg failed'])[-1])
    pending.replace(target)
    path.unlink()
    return target


def restore_range(path: Path) -> Path:
    """Decode a Fast song range (high-bitrate Opus) to a WAV at the original rate for the mixer."""
    target = path.with_name(path.name[:-len('.hq.opus')].rsplit('.', 1)[0] + '.wav')
    if target.is_file():
        return target
    tags = subprocess.run([ffmpeg_tool('ffprobe'), '-v', 'error', '-select_streams', 'a:0', '-show_entries',
                           'stream_tags=montara_sample_rate:format_tags=montara_sample_rate', '-of', 'default=nw=1:nk=1', str(path)],
                          capture_output=True, text=True, timeout=60).stdout.split()
    rate = next((t for t in tags if t.isdigit() and 8000 <= int(t) <= 384000), '48000')
    pending = target.with_name(target.stem + '.partial.wav')
    done = subprocess.run([ffmpeg_tool('ffmpeg'), '-v', 'error', '-nostdin', '-y', '-i', str(path), '-map', '0:a:0',
                           '-ar', rate, '-c:a', 'pcm_f32le', '-rf64', 'auto', str(pending)], capture_output=True, text=True, timeout=3600)
    if done.returncode != 0:
        pending.unlink(missing_ok=True)
        raise ValueError('Could not read this song range: ' + (done.stderr.strip().splitlines() or ['FFmpeg failed'])[-1])
    pending.replace(target)
    path.unlink()
    return target


def preview_original(path) -> dict | None:
    """The original a decoded preview stands for ({name, size, fingerprint}), or None for a real file."""
    try:
        data = json.loads((Path(path).parent / 'upload.json').read_text())
    except (OSError, ValueError):
        return None
    return data.get('preview_of') if data.get('restored') == Path(path).name else None


def register_resumable_upload(app, data_root, classify):
    root = Path(data_root).resolve() / 'Uploads'
    limit = 256 * 1024**2 if os.environ.get('MONTARA_SESSION_TOKEN') else 30 * 1024**3

    def failure(message, code=400):
        return jsonify(error={'message': message}), code

    def lookup(upload_id):
        if not re.fullmatch('[a-f0-9]{32}', upload_id):
            raise ValueError('Unknown upload.')
        work = root / upload_id
        if not (work / 'upload.json').is_file():
            raise ValueError('Unknown upload.')
        return work

    def load(work):
        return json.loads((work / 'upload.json').read_text())

    def public(work, data):
        received = (work / 'source.part').stat().st_size if (work / 'source.part').exists() else data['size'] if data.get('complete') else 0
        return dict(id=work.name, received=received, size=data['size'], complete=data.get('complete', False), chunk_size=CHUNK)

    @app.get('/montara/uploads')
    def upload_limits():
        root.mkdir(parents=True, exist_ok=True)
        return jsonify(max_file_bytes=limit, chunk_bytes=CHUNK, free_bytes=shutil.disk_usage(root).free)

    @app.post('/montara/uploads')
    def upload_create():
        body = request.get_json(silent=True) or {}
        name, size, fingerprint = body.get('name'), body.get('size'), body.get('fingerprint')
        if not isinstance(name, str) or not name or Path(name).name != name or '\\' in name or len(name) > 200:
            return failure('Choose a valid file name.')
        if Path(name).suffix.lower() in {'.insv', '.msv'}:
            return failure('Export a stitched 360 MP4 from your camera application first.')
        if Path(name).suffix.lower() not in MEDIA:
            return failure('Choose a video or audio file.')
        if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= limit:
            return failure(f'This environment accepts files up to {limit / 1024**2:.0f} MiB.', 413)
        if not isinstance(fingerprint, str) or not re.fullmatch('[a-f0-9]{64}', fingerprint):
            return failure('Invalid file fingerprint.')
        root.mkdir(parents=True, exist_ok=True)
        with (root / 'allocation.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            reserved = 0
            for path in root.glob('*/upload.json'):
                item = load(path.parent)
                if item['name'] == name and item['size'] == size and item['fingerprint'] == fingerprint:
                    return jsonify(public(path.parent, item))
                if not item.get('complete'):
                    reserved += max(0, item['size'] - public(path.parent, item)['received'])
            if shutil.disk_usage(root).free < size + reserved + RESERVE:
                return failure('Not enough storage for this file. Remove an unfinished upload or use a smaller file.', 507)
            work = root / uuid.uuid4().hex
            work.mkdir()
            record = dict(name=name, size=size, fingerprint=fingerprint, complete=False)
            original = body.get('original')
            if name.lower().endswith(PREVIEW):
                if (not isinstance(original, dict) or not isinstance(original.get('name'), str) or Path(original['name']).name != original['name']
                        or isinstance(original.get('size'), bool) or not isinstance(original.get('size'), int)
                        or not re.fullmatch('[a-f0-9]{64}', str(original.get('fingerprint')))):
                    return failure('A preview must name its original.')
                record['preview_of'] = dict(name=original['name'], size=original['size'], fingerprint=original['fingerprint'])
            save(work / 'upload.json', record)
            (work / 'source.part').touch()
            return jsonify(public(work, load(work))), 201

    @app.route('/montara/uploads/<upload_id>', methods=['GET', 'PUT', 'DELETE'])
    def upload_chunk(upload_id):
        try:
            work = lookup(upload_id)
            with (work / 'upload.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                data = load(work)
                if request.method == 'GET':
                    return jsonify(public(work, data))
                if request.method == 'DELETE':
                    if data.get('complete'):
                        return failure('A registered file may already be used by a project.', 409)
                    shutil.rmtree(work)
                    return jsonify(deleted=True)
                if data.get('complete'):
                    return jsonify(public(work, data))
                try:
                    offset = int(request.headers.get('Upload-Offset', '-1'))
                except ValueError:
                    return failure('Invalid upload offset.')
                length = request.content_length
                if length is None or not 0 < length <= CHUNK or offset < 0 or offset + length > data['size']:
                    return failure('Invalid upload chunk.')
                part = work / 'source.part'
                received = part.stat().st_size
                if offset > received or offset < received and offset + length > received:
                    return jsonify(**public(work, data), error={'message': 'Resume at the confirmed upload offset.'}), 409
                if shutil.disk_usage(root).free < length + RESERVE:
                    return failure('Not enough working space to continue this upload.', 507)
                # Reads are bounded by CHUNK; a disconnected retry never duplicates bytes.
                payload = request.stream.read(length + 1)
                if len(payload) != length:
                    return failure('Incomplete chunk. Retry this part.')
                with part.open('r+b') as handle:
                    handle.seek(offset)
                    if offset < received:
                        if handle.read(length) != payload:
                            return failure('The selected file differs from the unfinished upload.', 409)
                    else:
                        handle.write(payload); handle.flush(); os.fsync(handle.fileno())
                return jsonify(public(work, data))
        except ValueError as exc:
            return failure(str(exc), 404)

    @app.post('/montara/uploads/<upload_id>/finish')
    def upload_finish(upload_id):
        try:
            work = lookup(upload_id)
            with (work / 'upload.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                data = load(work)
                if not data.get('complete'):
                    source = work / 'source.part'
                    if source.stat().st_size != data['size']:
                        return failure('Wait for all file parts to arrive.', 409)
                    # Browser fingerprint covers the first and last 64 KiB plus metadata.
                    digest = hashlib.sha256()
                    with source.open('rb') as handle:
                        digest.update(handle.read(65536))
                        handle.seek(max(0, data['size'] - 65536)); digest.update(handle.read(65536))
                    if digest.hexdigest() != data['fingerprint']:
                        return failure('The uploaded file does not match. Remove the unfinished upload and retry.', 409)
                    source.replace(work / data['name'])
                    if data['name'].lower().endswith(LOSSLESS):
                        data['restored'] = restore_lossless(work / data['name']).name
                    elif data['name'].lower().endswith(RANGE):
                        data['restored'] = restore_range(work / data['name']).name
                    elif data['name'].lower().endswith(PREVIEW):
                        data['restored'] = restore_preview(work / data['name']).name
                    data['complete'] = True
                    save(work / 'upload.json', data)
                return jsonify(classify([str(work / data.get('restored', data['name']))]))
        except ValueError as exc:
            return failure(str(exc), 404)
