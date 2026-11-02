"""A slow MP3 transfer must not enable partial playback or restart finished players."""
import re
import mimetypes
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def test_results_wait_for_complete_mp3_and_keep_players_across_polls(tmp_path):
    mp3 = tmp_path / 'song.mp3'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=d=2', str(mp3)], check=True)
    raw = mp3.read_bytes()
    blocked, release = threading.Event(), threading.Event()
    requests = []
    html = re.sub(r'<script\b[^>]*>.*?</script>', '', (ROOT / 'web/index.html').read_text(), flags=re.S)
    html = html.replace('</body>', '''<script>
      const $ = s => document.querySelector(s);
      const renderFiles = () => {}, show = () => {}, toast = () => {};
      const escapeHtml = s => String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
      const clock = s => Math.round(s) + 's';
      </script><script src="/full-session.js"></script></body>''')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if self.path.startswith('/montara/session/test/result/'):
                requests.append(self.path)
                self.send_response(200)
                self.send_header('Content-Type', 'audio/mpeg')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw[:len(raw)//2]); self.wfile.flush()
                if '/result/1?' in self.path:
                    blocked.set(); release.wait(20)
                self.wfile.write(raw[len(raw)//2:])
                return
            path = ROOT / 'web' / urlsplit(self.path).path.lstrip('/')
            static = path.is_file() and path.resolve().is_relative_to(ROOT / 'web')
            content = path.read_bytes() if static else html.encode()
            self.send_response(200)
            self.send_header('Content-Type', (mimetypes.guess_type(path)[0] or 'application/octet-stream') if static else 'text/html')
            self.end_headers(); self.wfile.write(content)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{server.server_port}/')
            page.evaluate('''() => {
              fullSession.id = 'test';
              const songs = [1,2].map(id => ({id, name:'Song '+id, start:id*10, end:id*10+2, selected:true}));
              fullSession.data = {status:'rendering', songs, results:songs, track_files:['voice.wav','keys.wav']};
              document.querySelector('#sessionReview').hidden = false;
              drawSessionResults(fullSession.data); paintSessionRender(fullSession.data);
            }''')
            assert blocked.wait(10)
            page.wait_for_function("document.querySelector('[data-result=\"2\"] audio').src.startsWith('blob:')")
            # Song 2 can be heard while song 1 is still downloading. No partial song-1 source.
            assert page.locator('[data-result="1"] audio').get_attribute('src') is None
            assert page.locator('[data-result="1"] audio').is_hidden()
            assert page.locator('[data-result="1"] progress').is_visible()
            assert page.locator('[data-render-song="1"]').get_attribute('aria-valuenow') != '100'
            page.evaluate("window.secondPlayer = document.querySelector('[data-result=\"2\"] audio'); drawSessionResults(fullSession.data)")
            release.set()
            page.wait_for_function("document.querySelector('[data-result=\"1\"] audio').src.startsWith('blob:')")
            assert page.locator('[data-render-song="1"]').get_attribute('aria-valuenow') == '100'
            assert page.evaluate("secondPlayer === document.querySelector('[data-result=\"2\"] audio')")
            page.evaluate("document.querySelector('[data-result=\"1\"] audio').play()")
            page.wait_for_function("document.querySelector('[data-result=\"1\"] audio').ended")
            assert len(requests) == 2 and not errors
            page.screenshot(path=str(tmp_path / 'buffered-results.png'), full_page=True)
            browser.close()
    finally:
        release.set(); server.shutdown(); server.server_close(); thread.join(5)
