"""Real Stage session journey: upload -> detect -> review -> mix -> two exports.

No cloud models or network video imports. Runs unchanged on Linux and macOS.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from io import BytesIO
from urllib.request import urlopen

import numpy as np
import soundfile as sf
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def upload_recovery(page, url, media, output):
    original = media / 'Upload-recovery.wav'
    sr = 48000
    audio = (.03 * np.sin(2 * np.pi * 330 * np.arange(sr * 30) / sr)).astype('float32')
    sf.write(original, np.column_stack((audio, audio)), sr, subtype='FLOAT')
    assert original.stat().st_size > 8 * 1024**2
    page.goto(url); page.locator('#mode').wait_for(state='visible'); page.locator('[data-platform="youtube"]').click()

    def interrupt(route):
        if route.request.method == 'PUT' and int(route.request.headers.get('upload-offset', '0')) >= 4 * 1024**2:
            route.abort()
        else:
            route.continue_()

    page.route('**/montara/uploads/*', interrupt)
    page.locator('[data-drop="audio"] input').set_input_files(str(original))
    page.wait_for_function("state.files.some(f=>f.kind==='error')", timeout=30_000)
    page.unroute('**/montara/uploads/*', interrupt)
    offsets = []
    page.on('request', lambda request: offsets.append(int(request.headers.get('upload-offset', '0'))) if request.method == 'PUT' else None)
    page.reload(); page.locator('#mode').wait_for(state='visible'); page.locator('[data-platform="youtube"]').click()
    page.locator('[data-drop="audio"] input').set_input_files(str(original))
    page.wait_for_function("state.files.some(f=>f.kind==='master'||f.kind==='songs')", timeout=30_000)
    path = Path(page.evaluate("state.files.find(f=>f.kind==='master'||f.kind==='songs').path"))
    assert offsets[0] == 4 * 1024**2, offsets
    assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(original.read_bytes()).digest()
    page.screenshot(path=str(output / '00-upload-recovered.png'), full_page=True)


def run(output):
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=True)
    media = output / 'sources'; media.mkdir(exist_ok=True)
    sr = 8000; t = np.arange(sr * 390) / sr
    active = ((t >= 3) & (t < 180)) | ((t >= 210) & (t < 387))
    for name, frequency in [('Kick', 80), ('Bass', 160)]:
        audio = (.1 * np.sin(2 * np.pi * frequency * t) * active).astype('float32')
        if name == 'Kick': audio *= np.exp(-12 * (t % .5))
        sf.write(media / f'{name}.wav', audio, sr)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    url = f'http://127.0.0.1:{port}'
    env = {**os.environ, 'OMP_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '2'}
    with (output / 'server.log').open('w') as log:
        process = subprocess.Popen([sys.executable, str(ROOT / 'app.py'), '--port', str(port), '--data', str(output / 'data'), '--no-samples'], cwd=ROOT, env=env, stdout=log, stderr=log)
        try:
            for _ in range(120):
                try:
                    with urlopen(url + '/montara/version', timeout=1): break
                except Exception:
                    if process.poll() is not None: raise RuntimeError('Server did not start; inspect server.log')
                    time.sleep(.5)
            errors = []
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 1280, 'height': 900})
                page.on('pageerror', lambda error: errors.append(str(error)))
                upload_recovery(page, url, media, output)
                page.goto(url)
                page.locator('#mode').wait_for(state='visible')
                page.locator('[data-platform="youtube"]').click()
                page.locator('#stageAudioOnly').check()
                page.locator('#fullSessionOn').check()
                page.locator('[data-drop="audio"] input').set_input_files([str(media / 'Kick.wav'), str(media / 'Bass.wav')])
                page.wait_for_function("document.querySelectorAll('#audioFiles li').length===2 && !document.querySelector('#continueFootage').disabled")
                page.screenshot(path=str(output / '01-input.png'), full_page=True)
                page.locator('#continueFootage').click()
                page.wait_for_function("document.querySelectorAll('[data-session-song]').length===2", timeout=180_000)
                detected = page.evaluate('fullSession.data.songs')
                assert abs(detected[0]['end'] - 195) < 3
                page.screenshot(path=str(output / '02-detected.png'), full_page=True)
                rows = page.locator('[data-session-song]')
                page.wait_for_function('sessionWave.data && sessionWave.data.peaks.length > 100', timeout=60_000)
                # A real drag on a handle moves that song's end.
                handle = rows.nth(0).locator('.song-cut.end')
                box = handle.bounding_box(); before = page.evaluate('fullSession.data.songs[0].end')
                page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2); page.mouse.down()
                page.mouse.move(box['x'] - 60, box['y'] + box['height'] / 2, steps=6); page.mouse.up()
                assert page.evaluate('fullSession.data.songs[0].end') < before - 1
                # Exact short windows for a quick export (same as dragging, without pixel arithmetic).
                page.evaluate("fullSession.data.songs[0].start=5;fullSession.data.songs[0].end=20;fullSession.data.songs[1].start=215;fullSession.data.songs[1].end=230;drawSessionSongs()")
                page.screenshot(path=str(output / '02b-waveforms.png'), full_page=True)
                rows.nth(0).locator('[data-song-play]').click()
                page.wait_for_function('sessionPlayer.audio && sessionPlayer.audio.currentTime > 0.2', timeout=60_000)
                rows.nth(0).locator('[data-song-play]').click()
                assert page.evaluate('sessionPlayer.audio') is None
                rows.nth(0).locator('[data-song-mixer]').click()
                page.wait_for_function("!document.querySelector('#mix').hidden && !document.querySelector('#useMix').disabled", timeout=180_000)
                page.locator('#playMix').click(); page.wait_for_timeout(400); page.locator('#playMix').click()
                page.evaluate("(() => { const input = document.querySelector('#strips input[type=range]'); input.value = Number(input.value) - 3; input.dispatchEvent(new Event('input', {bubbles: true})); })()")
                page.screenshot(path=str(output / '03-song-mix.png'), full_page=True)
                page.locator('#useMix').click()
                page.wait_for_function("!document.querySelector('#sessionReview').hidden && document.querySelector('.song-tag')")
                page.locator('#sessionMix').click()
                page.wait_for_function("document.querySelectorAll('#sessionResults audio').length===2", timeout=240_000)
                data = page.evaluate('fullSession.data')
                assert data['status'] == 'done'
                saved = json.loads((output / 'data' / 'Sessions' / data['id'] / 'session.json').read_text())
                assert list(saved['settings']['per_song']) == ['1'] and saved['settings']['per_song']['1']['faders']
                for song in data['results']:
                    response = page.request.get(f'{url}/montara/session/{data["id"]}/result/{song["id"]}')
                    assert response.ok and len(response.body()) > 1000
                    target = output / f'song-{song["id"]}.mp3'; target.write_bytes(response.body())
                    info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_format', '-of', 'json', str(target)]))
                    assert abs(float(info['format']['duration']) - 15) < 1
                page.screenshot(path=str(output / '04-exported.png'), full_page=True)
                page.reload(); page.locator('#mode').wait_for(state='visible'); page.locator('[data-platform="youtube"]').click()
                page.locator('#sessionResume').click()
                page.wait_for_function("document.querySelectorAll('#sessionResults audio').length===2")
                page.set_viewport_size({'width': 390, 'height': 844})
                page.screenshot(path=str(output / '05-mobile-resume.png'), full_page=True)
                assert not errors, errors
                browser.close()
            summary = dict(platform=sys.platform, detected_songs=detected, exported_songs=data['results'], browser_errors=errors)
            (output / 'summary.json').write_text(json.dumps(summary, indent=2))
            print(json.dumps(summary))
        finally:
            process.terminate(); process.wait(timeout=15)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True)
    parser.add_argument('--stdout-screenshots', action='store_true', help='Small visual evidence when artifact storage is unavailable')
    args = parser.parse_args(); run(args.output)
    if args.stdout_screenshots:
        from PIL import Image
        for source in sorted(Path(args.output).glob('*.png')):
            buffer = BytesIO()
            Image.open(source).convert('RGB').save(buffer, format='WEBP', quality=75)
            print('MONTARA_SCREENSHOT ' + source.stem + '.webp ' + base64.b64encode(buffer.getvalue()).decode())
