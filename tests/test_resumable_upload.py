"""Interrupted uploads, replayed chunks, storage limits and session boundaries."""
import hashlib
from pathlib import Path
import sys

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from resumable_upload import register_resumable_upload


def make_client(root):
    app = Flask(__name__)
    register_resumable_upload(app, root, lambda paths: {'videos': [{'path': paths[0]}]})
    return app.test_client()


def fingerprint(payload):
    return hashlib.sha256(payload[:65536] + payload[max(0, len(payload) - 65536):]).hexdigest()


def create(client, payload, **extra):
    return client.post('/montara/uploads', json=dict(name='camera.mp4', size=len(payload), fingerprint=fingerprint(payload), **extra))


def test_resume_from_new_web_process_and_replay_without_duplicate_bytes(tmp_path):
    c = make_client(tmp_path)
    payload = b'0123456789' * 100
    job = create(c, payload).json
    url = '/montara/uploads/' + job['id']
    assert c.put(url, data=payload[:500], headers={'Upload-Offset': '0'}).json['received'] == 500
    assert c.put(url, data=payload[:500], headers={'Upload-Offset': '0'}).json['received'] == 500
    c = make_client(tmp_path)
    assert create(c, payload).json['id'] == job['id']
    assert c.get(url).json['received'] == 500
    assert c.post(url + '/finish', json={}).status_code == 409
    assert c.put(url, data=payload[500:], headers={'Upload-Offset': '500'}).json['received'] == 1000
    result = c.post(url + '/finish', json={})
    assert result.status_code == 200
    assert Path(result.json['videos'][0]['path']).read_bytes() == payload
    assert c.post(url + '/finish', json={}).json == result.json
    assert c.delete(url).status_code == 409  # A registered original may be in a project.


def test_wrong_offset_or_changed_chunk_is_rejected(tmp_path):
    c = make_client(tmp_path); job = create(c, b'abcd').json; url = '/montara/uploads/' + job['id']
    assert c.put(url, data=b'bc', headers={'Upload-Offset': '1'}).status_code == 409
    assert c.put(url, data=b'ab', headers={'Upload-Offset': '0'}).status_code == 200
    assert c.put(url, data=b'xx', headers={'Upload-Offset': '0'}).status_code == 409
    assert c.put(url, data=b'ef', headers={'Upload-Offset': '2'}).status_code == 200
    assert c.post(url + '/finish', json={}).status_code == 409  # Final fingerprint differs.
    assert c.delete(url).status_code == 200
    assert not (tmp_path / 'Uploads' / job['id']).exists()


@pytest.mark.parametrize('name', ['../private.mp4', 'test.insv', 'test.msv', 'secret.txt', 'dir\\clip.mp4'])
def test_reject_paths_and_unusable_sources(tmp_path, name):
    c = make_client(tmp_path)
    assert c.post('/montara/uploads', json={'name': name, 'size': 4, 'fingerprint': 'a' * 64}).status_code == 400


def test_public_preview_keeps_existing_total_file_limit(tmp_path, monkeypatch):
    monkeypatch.setenv('MONTARA_SESSION_TOKEN', 'private-session')
    c = make_client(tmp_path)
    assert c.get('/montara/uploads').json['max_file_bytes'] == 256 * 1024**2
    assert c.post('/montara/uploads', json={'name': 'large.mp4', 'size': 257 * 1024**2, 'fingerprint': 'a' * 64}).status_code == 413


def test_reservations_prevent_overcommitting_disk_and_partial_upload_can_be_removed(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr('resumable_upload.shutil.disk_usage', lambda _: SimpleNamespace(free=128 * 1024**2 + 1500))
    c = make_client(tmp_path); first = create(c, b'a' * 1000)
    assert first.status_code == 201
    assert create(c, b'b' * 1000).status_code == 507
    assert c.delete('/montara/uploads/' + first.json['id']).status_code == 200
    assert create(c, b'b' * 1000).status_code == 201


def _pcm(path):
    data = Path(path).read_bytes(); i = data.find(b'data')
    return data[i + 8:i + 8 + int.from_bytes(data[i + 4:i + 8], 'little')]


def _bext_samples(path):
    data = Path(path).read_bytes(); i = data.find(b'bext')
    return int.from_bytes(data[i + 8 + 338:i + 8 + 346], 'little') if i >= 0 else None


@pytest.mark.skipif(not __import__('shutil').which('ffmpeg'), reason='needs ffmpeg')
def test_companion_flac_becomes_the_identical_wav_with_its_time_reference(tmp_path):
    import subprocess
    wav, flac = tmp_path / 'src.wav', tmp_path / 'Kick.wav.flac'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=f=220:d=2', '-af', 'apad=pad_dur=3', '-ar', '48000', '-c:a', 'pcm_s24le',
                    '-write_bext', '1', '-metadata', 'time_reference=172800000', str(wav)], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(wav), '-c:a', 'flac', str(flac)], check=True)
    payload = flac.read_bytes()
    c = make_client(tmp_path / 'data')
    job = c.post('/montara/uploads', json=dict(name=flac.name, size=len(payload), fingerprint=fingerprint(payload))).json
    url = '/montara/uploads/' + job['id']
    for offset in range(0, len(payload), 4 * 1024**2):
        assert c.put(url, data=payload[offset:offset + 4 * 1024**2], headers={'Upload-Offset': str(offset)}).status_code == 200
    restored = Path(c.post(url + '/finish', json={}).json['videos'][0]['path'])
    assert restored.name == 'Kick.wav' and not (restored.parent / flac.name).exists()
    assert _pcm(restored) == _pcm(wav)
    assert _bext_samples(restored) == 172800000
    assert c.post(url + '/finish', json={}).json['videos'][0]['path'] == str(restored)


@pytest.mark.skipif(not __import__('shutil').which('ffmpeg'), reason='needs ffmpeg')
def test_opus_preview_decodes_at_original_rate_with_time_reference_and_names_its_original(tmp_path):
    import subprocess
    from resumable_upload import preview_original
    wav, opus = tmp_path / 'src.wav', tmp_path / 'Keys.wav.opus'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=f=220:d=3', '-ar', '44100', '-c:a', 'pcm_s24le',
                    '-write_bext', '1', '-metadata', 'time_reference=88200', str(wav)], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(wav), '-c:a', 'libopus', '-b:a', '96k', '-metadata', 'montara_sample_rate=44100',
                    '-metadata', 'montara_bits=24', '-f', 'ogg', str(opus)], check=True)
    payload = opus.read_bytes()
    c = make_client(tmp_path / 'data')
    body = dict(name=opus.name, size=len(payload), fingerprint=fingerprint(payload))
    assert c.post('/montara/uploads', json=body).status_code == 400          # a preview must name its original
    original = {'name': 'Keys.wav', 'size': wav.stat().st_size, 'fingerprint': 'b' * 64}
    job = c.post('/montara/uploads', json={**body, 'original': original}).json
    url = '/montara/uploads/' + job['id']
    assert c.put(url, data=payload, headers={'Upload-Offset': '0'}).status_code == 200
    decoded = Path(c.post(url + '/finish', json={}).json['videos'][0]['path'])
    assert decoded.name == 'Keys.wav' and preview_original(decoded) == original
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=sample_rate:format_tags=time_reference', '-of', 'default=nw=1:nk=1',
                          str(decoded)], capture_output=True, text=True).stdout.split()
    assert out == ['44100', '88200']
    assert _bext_samples(decoded) == 88200
    assert preview_original(wav) is None
