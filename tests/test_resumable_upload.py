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
