"""HTTPS browser acceptance of FER's isolated account/project catalog.

Synthetic accounts only. No Engine, Companion, external host or real media.
"""
import argparse
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from urano.lab_app import create_isolated_lab_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='montara-urano-') as temporary:
        root = Path(temporary)
        cert, key = root / 'cert.pem', root / 'key.pem'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(key), '-out', str(cert), '-days', '1',
                        '-subj', '/CN=localhost'], check=True, capture_output=True)
        server = make_server('127.0.0.1', 0, create_isolated_lab_app(root),
                             ssl_context=(str(cert), str(key)), threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'https://127.0.0.1:{server.server_port}/urano-lab/'
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                alice = browser.new_context(ignore_https_errors=True)
                bob = browser.new_context(ignore_https_errors=True)
                page = alice.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))

                def register(tab, email):
                    tab.goto(url)
                    tab.locator('#registerTab').click()
                    tab.locator('[name=email]').fill(email)
                    tab.locator('[name=password]').fill('fictional-test-password')
                    tab.locator('#submitAuth').click()
                    tab.locator('#projectsPanel').wait_for(state='visible', timeout=10000)
                    expect(tab.locator('#submitAuth')).to_be_enabled()

                def create(title):
                    page.locator('#newProjectForm [name=title]').fill(title)
                    page.locator('#newProjectForm button').click()
                    expect(page.locator('#projectTitle')).to_have_text(title)
                    expect(page.locator('#saveNotes')).to_be_enabled()

                register(page, 'alice@example.test')
                create('Older project')
                page.locator('#recipeNotes').fill('An edit recovered after logout')
                page.locator('#saveNotes').click()
                expect(page.locator('#notice')).to_contain_text('Notas guardadas')
                create('Recent project')
                assert page.locator('.project-row').count() == 2
                page.reload()
                page.locator('#projectsPanel').wait_for(state='visible')
                page.locator('.project-row').filter(has_text='Older project').click()
                expect(page.locator('#recipeNotes')).to_have_value('An edit recovered after logout')
                page.screenshot(path=str(out / '01-old-project-recovered.png'), full_page=True)
                page.locator('#logoutBtn').click()
                page.locator('#authPanel').wait_for(state='visible')
                page.locator('[name=email]').fill('alice@example.test')
                page.locator('[name=password]').fill('fictional-test-password')
                page.locator('#submitAuth').click()
                page.locator('#projectsPanel').wait_for(state='visible')
                page.locator('.project-row').first.wait_for()
                assert page.locator('.project-row').count() == 2
                other = bob.new_page()
                register(other, 'bob@example.test')
                assert other.locator('.project-row').count() == 0
                other.screenshot(path=str(out / '02-second-user-isolated.png'), full_page=True)
                assert not errors, errors
                browser.close()
            summary = {'passed': True, 'browser_signup_login': True,
                       'older_project_recovered': True, 'reload_and_logout': True,
                       'second_user_isolated': True, 'editor_connected': False}
            (out / 'summary.json').write_text(json.dumps(summary, indent=2))
            print(json.dumps(summary))
        finally:
            server.shutdown()
            thread.join(timeout=5)


if __name__ == '__main__':
    main()
