"""Browser Back/Forward through idle Stage, Push and Show, retaining input."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

from e2e_journey import ROOT, free_port
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    port = free_port(); url = f'http://127.0.0.1:{port}'
    with (out/'server.log').open('w') as log:
        server = subprocess.Popen([sys.executable, str(ROOT/'app.py'), '--port', str(port), '--data', str(out/'data')],
                                  stdout=log, stderr=subprocess.STDOUT, env={**os.environ, 'PYTHONUNBUFFERED':'1'})
        try:
            for _ in range(120):
                try: urlopen(url+'/montara/version', timeout=1).close(); break
                except OSError: time.sleep(.5)
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page(viewport={'width':1440, 'height':960})
                errors = []; page.on('pageerror', lambda e: (errors.append(str(e)), print('PAGE_ERROR', str(e), flush=True)))
                page.goto(url); page.locator('#mode').wait_for(state='visible')
                page.locator('.mode[data-platform="youtube"]').click()
                page.wait_for_function("document.querySelectorAll('#videoFiles li, #audioFiles li').length===12")
                page.locator('#videoName').fill('Keep my Stage take')
                page.go_back(); page.locator('#mode').wait_for(state='visible')
                page.go_forward(); page.locator('#footage').wait_for(state='visible')
                assert page.locator('#videoName').input_value() == 'Keep my Stage take'
                assert page.locator('#videoFiles li, #audioFiles li').count() == 12
                page.locator('#continueFootage').click()
                page.locator('#cameras').wait_for(state='visible', timeout=120_000)
                page.go_back(); page.locator('#footage').wait_for(state='visible')
                page.go_forward(); page.locator('#cameras').wait_for(state='visible')
                page.screenshot(path=str(out/'stage-forward.png'), full_page=True)
                page.go_back(); page.go_back(); page.locator('#mode').wait_for(state='visible')
                page.locator('.mode[data-platform="reel"]').click()
                page.locator('#footage').wait_for(state='visible')
                page.locator('#videoName').fill('Keep my reel')
                page.go_back(); page.locator('#mode').wait_for(state='visible')
                page.go_forward(); page.locator('#footage').wait_for(state='visible')
                assert page.locator('#videoName').input_value() == 'Keep my reel'
                assert page.locator('#formatRow').is_visible()
                page.screenshot(path=str(out/'push-forward.png'), full_page=True)
                page.go_back(); page.locator('#mode').wait_for(state='visible')
                page.locator('.mode[data-platform="show"]').click()
                page.locator('#showSetup').wait_for(state='visible')
                page.wait_for_function("document.querySelector('#showInputStatus').textContent.includes('Example')")
                page.wait_for_function("!document.querySelector('#showChooseType').disabled", timeout=60_000)
                page.locator('#showChooseType').click()
                page.locator('#showStyle').wait_for(state='visible')
                page.go_back(); page.locator('#showSetup').wait_for(state='visible')
                page.go_forward(); page.locator('#showStyle').wait_for(state='visible')
                page.screenshot(path=str(out/'show-forward.png'), full_page=True)
                assert not errors, errors
                browser.close()
            (out/'summary.json').write_text(json.dumps({'passed':True,'modes':['Stage','Push','Show'],'page_errors':errors}, indent=2))
        finally:
            server.terminate(); server.wait(timeout=30)


if __name__ == '__main__': main()
