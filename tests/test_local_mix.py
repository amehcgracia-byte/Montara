"""A song mixed by the companion's local mixer equals the same song mixed on the server."""
import json, os, shutil, subprocess, sys, time
from pathlib import Path

import numpy as np
import soundfile as sf
from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import full_session
from mixer_adapter.session import local_plan, render_song, save, read


def install_layout(home: Path) -> Path:
    """The folder install.sh --mixer makes: local_mix.py, adapters, track_types and the mixer."""
    mix = home / 'mixer'
    (mix / 'mixer_adapter').mkdir(parents=True)
    for f in ('mixer_adapter/single_song.py', 'mixer_adapter/extract.py', 'track_types.py'):
        shutil.copy(ROOT / f, mix / f)
    shutil.copy(ROOT / 'companion' / 'local_mix.py', mix / 'local_mix.py')
    (mix / 'mixer').symlink_to(ROOT / 'mixer')
    return mix


def session(tmp_path):
    rate, seconds = 22050, 14
    t = np.arange(rate * seconds) / rate
    data_root = tmp_path / 'data'
    work = data_root / 'Sessions' / 'abcdefabcdef'; work.mkdir(parents=True)
    tracks, previews = [], {}
    for name, freq, offset in (('Kick.wav', 60, 0.0), ('Keys.wav', 440, 1.5), ('Sax.wav', 660, 0.0)):
        path = tmp_path / name
        sf.write(path, (0.2 * np.sin(2 * np.pi * freq * t) * (np.sin(2 * np.pi * 2 * t) > 0)).astype('float32'), rate, subtype='FLOAT')
        tracks.append(dict(file=name, path=str(path), samplerate=rate, channels=1, offset=offset, duration=seconds))
        previews[name] = {'name': name, 'size': path.stat().st_size, 'fingerprint': 'a' * 64}
    song = dict(id=1, name='Song 01', start=2.0, end=11.0, selected=True)
    data = {'id': 'abcdefabcdef', 'status': 'review', 'duration': float(seconds), 'songs': [song], 'tracks': tracks,
            'previews': previews, 'track_types': {'sax': {'type': 'sax', 'side': '', 'chosen': True}},
            'settings': {'per_song': {'1': {'faders': {'Keys.wav': -3.0}}}}}
    save(work / 'session.json', data)
    return data_root, work, data, song


def test_local_mix_equals_the_server_mix(tmp_path):
    data_root, work, data, song = session(tmp_path)
    plan = local_plan(data, song)
    assert [t['file'] for t in plan['tracks']] == ['Kick.wav', 'Keys.wav', 'Sax.wav'] and plan['tracks'][1]['delay_ms'] == 0
    for track in plan['tracks']:   # the companion finds the original on this computer
        track['path'] = next(t['path'] for t in data['tracks'] if t['file'] == track['file'])
    mix = install_layout(tmp_path / 'companion')
    plan_file = tmp_path / 'plan.json'
    plan_file.write_text(json.dumps({**plan, 'faders': {'Keys.wav': -3.0}}))
    out = subprocess.run([sys.executable, str(mix / 'local_mix.py'), str(plan_file), str(tmp_path / 'local.mp3')], cwd=mix,
                         capture_output=True, text=True, timeout=600)
    assert out.returncode == 0, out.stderr[-2000:]
    assert json.loads(out.stdout.strip().splitlines()[-1])['output'].endswith('local.mp3')
    # The server mixes the same song from the same originals (no previews on the server side here).
    server_data = read(work); server_data.pop('previews'); save(work / 'session.json', server_data)
    (work / 'results').mkdir(exist_ok=True)
    render_song(work, 1)
    server_mp3 = Path(json.loads((work / 'results' / '1.json').read_text())['path'])
    decode = lambda p: subprocess.run(['ffmpeg', '-v', 'error', '-i', str(p), '-f', 'f32le', '-ac', '2', '-ar', '22050', '-'],
                                      capture_output=True, check=True).stdout
    local, server = np.frombuffer(decode(tmp_path / 'local.mp3'), np.float32), np.frombuffer(decode(server_mp3), np.float32)
    n = min(len(local), len(server))
    assert abs(len(local) - len(server)) < 4000
    diff = np.sqrt(np.mean((local[:n] - server[:n]) ** 2)) / max(1e-9, np.sqrt(np.mean(server[:n] ** 2)))
    print('relative difference', diff)
    assert diff < 0.01   # same code, same samples: the two mixes match (MP3 encoding is the only noise)


def test_local_plan_and_result_endpoints_and_render_skips_local_songs(tmp_path, monkeypatch):
    data_root, work, data, song = session(tmp_path)
    sys.path.insert(0, str(ROOT / 'tests'))
    from test_full_session import client as make_client
    client = make_client(tmp_path)
    plan = client.get('/montara/session/abcdefabcdef/local-plan?song=1&start=2&end=11').json
    assert plan['window'] == [2.0, 11.0] and len(plan['tracks']) == 3 and 'mixer' in plan
    upload = data_root / 'Uploads' / ('d' * 32); upload.mkdir(parents=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=d=2', str(upload / 'Song 01.mp3')], check=True)
    (upload / 'upload.json').write_text(json.dumps({'name': 'Song 01.mp3', 'complete': True}))
    response = client.post('/montara/session/abcdefabcdef/local-result', json={'song': 1, 'window': [2, 11], 'upload_id': 'd' * 32})
    assert response.status_code == 200 and (work / 'exports' / 'local-2.000-11.000.mp3').is_file()
    # The export takes the local song as it is and mixes nothing on the server.
    subprocess.run([sys.executable, '-m', 'mixer_adapter.session', str(work), 'render'], cwd=ROOT, check=True, capture_output=True, timeout=300)
    result = read(work)
    assert result['status'] == 'done' and result['results'][0]['local'] is True and result['results'][0]['path'].endswith('local-2.000-11.000.mp3')
