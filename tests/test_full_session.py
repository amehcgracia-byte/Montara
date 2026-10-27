"""Session boundaries, isolation and real bounded audio extraction."""
import json
import math
import sys
import subprocess
import time
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import full_session
from mixer_adapter.session import prepare_tracks, read, save, validate_songs


@pytest.mark.parametrize('songs', [[], [{'start': 0, 'end': math.nan}], [{'start': True, 'end': 3}],
    [{'start': -1, 'end': 3}], [{'start': 0, 'end': 11}],
    [{'start': 0, 'end': 5}, {'start': 4, 'end': 8}], [{'start': 0, 'end': 5, 'selected': False}]])
def test_reject_invalid_song_windows(songs):
    with pytest.raises(ValueError):
        validate_songs(songs, 10)


def test_extract_window_aligns_offsets_and_pads_missing_audio(tmp_path):
    source = tmp_path / 'keys.wav'
    sf.write(source, np.ones(8000 * 4) * .1, 8000, subtype='FLOAT')
    work = tmp_path / 'job'; work.mkdir()
    save(work / 'session.json', {'tracks': [dict(file='keys.wav', path=str(source), samplerate=8000,
                                               channels=1, offset=2, duration=4)]})
    folder = prepare_tracks(work, {'id': 1, 'start': 1, 'end': 8})
    audio, sr = sf.read(folder / 'keys.wav')
    assert sr == 8000 and len(audio) == 7 * 8000
    np.testing.assert_allclose(audio[:8000], 0, atol=1e-6)
    np.testing.assert_allclose(audio[8000:40000], .1, atol=1e-6)
    np.testing.assert_allclose(audio[40000:], 0, atol=1e-6)


def test_browser_preview_is_limited_to_one_minute(tmp_path):
    source = tmp_path / 'bass.wav'
    sf.write(source, np.zeros(8000 * 65), 8000)
    work = tmp_path / 'job'; work.mkdir()
    save(work / 'session.json', {'tracks': [dict(file='bass.wav', path=str(source), samplerate=8000,
                                               channels=1, offset=0, duration=65)]})
    folder = prepare_tracks(work, {'id': 1, 'start': 0, 'end': 65}, preview=True)
    assert sf.info(folder / 'bass.wav').duration == 60
    assert not (work / 'songs').exists()


def client(tmp_path):
    app = Flask(__name__)
    full_session.register_full_session(app, tmp_path / 'data', tmp_path / 'fixtures')
    return app.test_client()


def test_reject_foreign_sources_and_duplicate_track_names(tmp_path, monkeypatch):
    outside = tmp_path / 'private.wav'; outside.write_bytes(b'private')
    c = client(tmp_path)
    assert c.post('/montara/session', json={'tracks': [str(outside)]}).status_code == 400
    root = tmp_path / 'data'; root.mkdir()
    source = root / 'track.wav'; source.write_bytes(b'audio')
    assert c.post('/montara/session', json={'tracks': [str(source), str(source)]}).status_code == 400


def test_review_persists_and_busy_jobs_cannot_be_replaced(tmp_path, monkeypatch):
    monkeypatch.setattr(full_session, 'launch', lambda *_: None)
    source = tmp_path / 'data' / 'keys.wav'; source.parent.mkdir(); source.write_bytes(b'audio')
    c = client(tmp_path)
    result = c.post('/montara/session', json={'tracks': [str(source)]})
    assert result.status_code == 202
    job = result.json['id']; work = source.parent / 'Sessions' / job
    assert (work / 'tracks' / source.name).is_symlink()
    assert c.post(f'/montara/session/{job}/prepare', json={'songs': []}).status_code == 409
    data = read(work); data.update(status='review', duration=20)
    save(work / 'session.json', data)
    songs = [{'name': 'First', 'start': 0, 'end': 8}, {'name': 'Second', 'start': 12, 'end': 20}]
    assert c.post(f'/montara/session/{job}/prepare', json={'songs': songs}).status_code == 202
    # A new app instance recovers the same manifest, rather than an in-memory job dict.
    assert client(tmp_path).get(f'/montara/session/{job}').json['songs'][1]['start'] == 12
    assert c.post(f'/montara/session/{job}/cancel', json={}).status_code == 202
    assert (work / 'cancel').exists()
    data = read(work); data.update(status='rendering', started_at=0)
    save(work / 'session.json', data)
    assert c.get(f'/montara/session/{job}').json['status'] == 'failed'


def test_no_space_does_not_modify_original(tmp_path, monkeypatch):
    source = tmp_path / 'keys.wav'; source.write_bytes(b'original')
    work = tmp_path / 'job'; work.mkdir()
    save(work / 'session.json', {'tracks': [dict(file='keys.wav', path=str(source), samplerate=48000,
                                               channels=2, offset=0, duration=3600)]})
    from types import SimpleNamespace
    monkeypatch.setattr('mixer_adapter.session.shutil.disk_usage', lambda _: SimpleNamespace(free=1))
    with pytest.raises(ValueError, match='working space'):
        prepare_tracks(work, dict(id=1, start=0, end=3600))
    assert source.read_bytes() == b'original'


def test_queued_worker_can_be_cancelled_without_starting_analysis(tmp_path):
    import fcntl
    work = tmp_path / 'job'; work.mkdir()
    save(work / 'session.json', dict(id='test', status='detecting'))
    with (tmp_path / 'compute.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        process = subprocess.Popen([sys.executable, '-m', 'mixer_adapter.session', str(work), 'detect'],
                                   cwd=Path(__file__).resolve().parents[1], start_new_session=True,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            (work / 'cancel').touch()
            assert process.wait(timeout=10) == 1
            assert read(work)['status'] == 'cancelled'
            assert not (work / 'vendor-state').exists()
        finally:
            if process.poll() is None:
                process.terminate(); process.wait(timeout=5)
