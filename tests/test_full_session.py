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
    data = read(work); data.update(status='review', duration=20, songs=[dict(start=0,end=20)],ai_review={'status':'reviewed'})
    save(work / 'session.json', data)
    songs = [{'name': 'First', 'start': 0, 'end': 8}, {'name': 'Second', 'start': 12, 'end': 20}]
    assert c.post(f'/montara/session/{job}/prepare', json={'songs': songs}).status_code == 202
    assert read(work)['ai_review']['status'] == 'manual_revision'
    assert read(work)['previous_ai_review']['status'] == 'reviewed'
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


def test_preview_session_exports_from_received_original_ranges_only(tmp_path):
    from mixer_adapter.session import original_windows
    rate = 8000
    original = np.linspace(-.5, .5, rate * 20).astype('float32')       # the person's real track
    preview = tmp_path / 'keys.wav'; sf.write(preview, np.zeros(rate * 20), rate, subtype='FLOAT')  # stands in for the decoded preview
    work = tmp_path / 'job'; work.mkdir()
    song = dict(id=1, name='Song 01', start=6.0, end=10.0, selected=True)
    data = {'tracks': [dict(file='keys.wav', path=str(preview), samplerate=rate, channels=1, offset=2, duration=20)],
            'songs': [song, dict(id=2, name='Song 02', start=12.0, end=14.0, selected=False)],
            'previews': {'keys.wav': {'name': 'keys.wav', 'size': 1, 'fingerprint': 'a' * 64}}}
    save(work / 'session.json', data)
    [window] = original_windows(data, work)                             # unselected song needs nothing
    assert (window['song'], window['start'], window['duration'], window['received']) == (1, 3.5, 5.0, False)
    with pytest.raises(ValueError):                                     # never export the preview
        prepare_tracks(work, song)
    start = int(window['start'] * rate)
    segment = tmp_path / 'segment.wav'; sf.write(segment, original[start:start + int(window['duration'] * rate)], rate, subtype='FLOAT')
    from mixer_adapter.session import register_original
    register_original(work, window, segment)
    assert original_windows(data, work)[0]['received']
    moved = {**data, 'songs': [dict(song, end=11.0), data['songs'][1]]}
    assert not original_windows(moved, work)[0]['received']            # a range belongs to its exact window
    audio, _ = sf.read(prepare_tracks(work, song) / 'keys.wav', dtype='float32')
    np.testing.assert_allclose(audio, original[4 * rate:8 * rate], atol=1e-6)   # song 6–10 s = file 4–8 s (offset 2)
    audio, _ = sf.read(prepare_tracks(work, song, preview=True) / 'keys.wav', dtype='float32')
    np.testing.assert_allclose(audio, 0, atol=1e-6)                     # the browser preview stays on the preview


def test_waveform_and_listen_cover_offsets(tmp_path):
    from mixer_adapter.session import listen_range, session_waveform
    rate = 8000
    loud = tmp_path / 'drums.wav'; sf.write(loud, np.r_[np.zeros(rate * 2), np.ones(rate * 2) * .5], rate, subtype='FLOAT')
    late = tmp_path / 'sax.wav'; sf.write(late, np.ones(rate * 2) * .2, rate, subtype='FLOAT')
    work = tmp_path / 'job'; work.mkdir()
    save(work / 'session.json', {'duration': 6.0, 'tracks': [
        dict(file='drums.wav', path=str(loud), samplerate=rate, channels=1, offset=0, duration=4),
        dict(file='sax.wav', path=str(late), samplerate=rate, channels=1, offset=4, duration=2)]})
    wave = session_waveform(work)
    assert wave['step'] == .25 and len(wave['peaks']) == 24
    assert max(wave['peaks'][:7]) == 0 and min(wave['peaks'][9:16]) > 200 and 0 < min(wave['peaks'][17:]) < 200  # silence, drums, quieter sax
    clip = listen_range(work, 3.0, 5.5)
    assert clip.is_file() and listen_range(work, 3.0, 5.5) == clip
    duration = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', str(clip)],
                                    capture_output=True, text=True).stdout)
    assert abs(duration - 2.5) < .1
    with pytest.raises(ValueError):
        listen_range(work, 1, 1.2)


def test_whole_session_listening_copy_is_seekable_webm(tmp_path):
    from mixer_adapter.session import session_listen
    rate = 8000
    a = tmp_path / 'a.wav'; sf.write(a, np.ones(rate * 3) * .3, rate, subtype='FLOAT')
    b = tmp_path / 'b.wav'; sf.write(b, np.ones(rate * 2) * .3, rate, subtype='FLOAT')
    work = tmp_path / 'job'; work.mkdir()
    save(work / 'session.json', {'duration': 5.0, 'tracks': [
        dict(file='a.wav', path=str(a), samplerate=rate, channels=1, offset=0, duration=3),
        dict(file='b.wav', path=str(b), samplerate=rate, channels=1, offset=3, duration=2)]})
    copy = session_listen(work)
    assert copy.suffix == '.webm' and session_listen(work) == copy
    info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(copy)]))
    assert info['streams'][0]['codec_name'] == 'opus' and abs(float(info['format']['duration']) - 5) < .2


def test_original_ranges_are_accepted_while_an_export_runs(tmp_path):
    c = client(tmp_path)
    data_root = tmp_path / 'data'
    work = data_root / 'Sessions' / 'abcdefabcdef'; work.mkdir(parents=True)
    rate = 8000
    preview = tmp_path / 'keys.wav'; sf.write(preview, np.zeros(rate * 20), rate, subtype='FLOAT')
    song = dict(id=1, name='Song 01', start=6.0, end=10.0, selected=True)
    save(work / 'session.json', {'id': 'abcdefabcdef', 'status': 'rendering', 'started_at': time.time(), 'duration': 20.0, 'songs': [song],
                                 'tracks': [dict(file='keys.wav', path=str(preview), samplerate=rate, channels=1, offset=2, duration=20)],
                                 'previews': {'keys.wav': {'name': 'keys.wav', 'size': 1, 'fingerprint': 'a' * 64}}})
    upload = data_root / 'Uploads' / ('b' * 32); upload.mkdir(parents=True)
    sf.write(upload / 'keys.wav', np.ones(rate * 5) * .1, rate, subtype='FLOAT')
    (upload / 'upload.json').write_text(json.dumps({'name': 'keys.wav.flac', 'restored': 'keys.wav', 'complete': True}))
    windows = c.get('/montara/session/abcdefabcdef/originals?song=1').json['originals']
    assert len(windows) == 1 and not windows[0]['received']
    response = c.post('/montara/session/abcdefabcdef/originals', json={'song': 1, 'file': 'keys.wav', 'upload_id': 'b' * 32})
    assert response.status_code == 200 and response.json['originals'][0]['received']
    assert json.loads((work / 'session.json').read_text())['status'] == 'rendering'   # session.json untouched by the range


def test_waveform_from_detection_envelopes(tmp_path):
    from mixer_adapter.session import waveform_from_timelines
    env = np.r_[np.zeros(20), np.ones(20) * .5, np.ones(20) * .1]   # 0.1 s frames: silence, loud, quiet
    waveform_from_timelines(tmp_path, {'a.wav': env, 'b.wav': np.zeros(60)}, 6.0, 0.1)
    wave = json.loads((tmp_path / 'waveform.json').read_text())
    assert wave['step'] == .25 and len(wave['peaks']) == 24
    assert max(wave['peaks'][:7]) == 0 and min(wave['peaks'][9:15]) == 255 and 0 < max(wave['peaks'][17:]) < 100


def test_session_keeps_the_track_types(tmp_path, monkeypatch):
    monkeypatch.setattr(full_session, 'launch', lambda *_: None)
    source = tmp_path / 'data' / 'Robi.wav'; source.parent.mkdir(); source.write_bytes(b'audio')
    result = client(tmp_path).post('/montara/session', json={'tracks': [str(source)],
                                                         'track_types': {'Robi.wav': {'type': 'narration', 'chosen': True}, 'Other.wav': {'type': 'nope'}}})
    work = source.parent / 'Sessions' / result.json['id']
    assert read(work)['track_types'] == {'robi': {'type': 'narration', 'side': '', 'chosen': True}}


def test_a_range_belongs_to_its_window_not_to_a_song_number(tmp_path):
    """Confirm queues ranges by window; a later split renumbers songs and the upload still lands."""
    c = client(tmp_path)
    data_root = tmp_path / 'data'
    work = data_root / 'Sessions' / 'abcdefabcdef'; work.mkdir(parents=True)
    rate = 8000
    preview = tmp_path / 'keys.wav'; sf.write(preview, np.zeros(rate * 30), rate, subtype='FLOAT')
    songs = [dict(id=1, name='A', start=0.0, end=10.0, selected=True), dict(id=2, name='B', start=12.0, end=20.0, selected=True)]
    save(work / 'session.json', {'id': 'abcdefabcdef', 'status': 'review', 'duration': 30.0, 'songs': songs,
                                 'tracks': [dict(file='keys.wav', path=str(preview), samplerate=rate, channels=1, offset=0, duration=30)],
                                 'previews': {'keys.wav': {'name': 'keys.wav', 'size': 1, 'fingerprint': 'a' * 64}}})
    # The page confirms song 2 at 12-20 (unsaved edits are fine: no session write needed).
    windows = c.get('/montara/session/abcdefabcdef/originals?song=2&start=12&end=20').json['originals']
    assert windows[0]['window'] == [12.0, 20.0] and windows[0]['start'] == 11.5
    assert c.get('/montara/session/abcdefabcdef/originals?song=2&start=12&end=99').status_code >= 400
    # Song 1 is split meanwhile: 12-20 is now song 3.
    data = read(work); data['songs'] = [dict(id=1, name='A', start=0.0, end=5.0, selected=True), dict(id=2, name='A2', start=5.0, end=10.0, selected=True),
                                         dict(id=3, name='B', start=12.0, end=20.0, selected=True)]
    save(work / 'session.json', data)
    upload = data_root / 'Uploads' / ('c' * 32); upload.mkdir(parents=True)
    sf.write(upload / 'keys.wav', np.ones(rate * 9) * .1, rate, subtype='FLOAT')
    (upload / 'upload.json').write_text(json.dumps({'name': 'keys.wav.flac', 'restored': 'keys.wav', 'complete': True}))
    response = c.post('/montara/session/abcdefabcdef/originals', json={'song': 2, 'window': [12, 20], 'file': 'keys.wav', 'upload_id': 'c' * 32})
    assert response.status_code == 200 and response.json['originals'][0]['received']
    assert [w['received'] for w in c.get('/montara/session/abcdefabcdef/originals?song=3').json['originals']] == [True]


def test_empty_tracks_are_not_sent_or_mixed_and_can_be_brought_back(tmp_path):
    from types import SimpleNamespace
    from mixer_adapter.session import empty_tracks, song_windows, prepare_tracks
    stems = [SimpleNamespace(path=Path(f'/x/{n}.wav')) for n in ('Kick', 'Bass')]
    loud, hiss = np.r_[np.zeros(100), np.ones(100) * .3], np.ones(200) * 10 ** (-60 / 20)
    assert empty_tracks(stems, {'Kick.wav': loud, 'Bass.wav': hiss}, 0.1) == ['Bass.wav']
    assert empty_tracks(stems, {'Kick.wav': hiss, 'Bass.wav': hiss}, 0.1) == []   # never all of them
    c = client(tmp_path)
    work = tmp_path / 'data' / 'Sessions' / 'abcdefabcdef'; work.mkdir(parents=True)
    rate = 8000
    tracks = []
    for name in ('Kick', 'Bass'):
        path = tmp_path / f'{name}.wav'; sf.write(path, np.ones(rate * 20) * .1, rate, subtype='FLOAT')
        tracks.append(dict(file=f'{name}.wav', path=str(path), samplerate=rate, channels=1, offset=0, duration=20))
    data = {'id': 'abcdefabcdef', 'status': 'review', 'duration': 20.0, 'tracks': tracks, 'empty_tracks': ['Bass.wav'],
            'songs': [dict(id=1, name='A', start=2.0, end=8.0, selected=True)],
            'previews': {t['file']: {'name': t['file'], 'size': 1, 'fingerprint': 'a' * 64} for t in tracks}}
    save(work / 'session.json', data)
    assert [w['file'] for w in song_windows(data, data['songs'][0])] == ['Kick.wav']
    data.pop('previews'); save(work / 'session.json', data)
    assert sorted(p.name for p in prepare_tracks(work, data['songs'][0]).glob('*.wav')) == ['Kick.wav']
    assert c.post('/montara/session/abcdefabcdef/include', json={'file': 'Bass.wav'}).json['empty_tracks'] == []
    assert not (work / 'songs').exists()
    assert c.post('/montara/session/abcdefabcdef/include', json={'file': 'Bass.wav'}).status_code == 400
