"""Real UI: Music/Video questions, browser navigation and standalone mastering."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
from urllib.request import urlopen
import numpy as np
import soundfile as sf
from playwright.sync_api import sync_playwright
from e2e_journey import free_port
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    sr=48000;t=np.arange(sr*10)/sr
    mix=out/'finished-mix.wav';sf.write(mix,np.column_stack([.7*np.sin(2*np.pi*330*t),.35*np.sin(2*np.pi*330*t)]),sr,subtype='FLOAT')
    port=free_port();url=f'http://127.0.0.1:{port}'
    log=(out/'server.log').open('w');server=subprocess.Popen([sys.executable,str(ROOT/'app.py'),'--port',str(port),'--data',str(out/'data'),'--no-samples'],stdout=log,stderr=subprocess.STDOUT)
    try:
        for _ in range(120):
            try:
                urlopen(url+'/api/v1/wizard/status',timeout=1).close();break
            except Exception:time.sleep(.5)
        with sync_playwright() as pw:
            browser=pw.chromium.launch();page=browser.new_page(viewport={'width':1280,'height':900})
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.route('http://127.0.0.1:47820/**',lambda route:route.abort())
            page.goto(url);page.locator('#mode').wait_for(state='visible')
            assert page.locator('#intentChoices').is_visible() and not page.locator('#videoChoices').is_visible()
            page.screenshot(path=str(out/'01-music-or-video.png'),full_page=True)
            page.locator('[data-intent=music]').click();page.screenshot(path=str(out/'02-music-tasks.png'),full_page=True)
            page.go_back();assert page.locator('#intentChoices').is_visible()
            page.go_forward();assert page.locator('#musicChoices').is_visible()
            page.evaluate("history.replaceState(history.state,'','?resume=footage')")
            page.locator('[data-audio-task=master]').click()
            assert 'resume=' not in page.url
            assert not page.locator('[data-drop=video]').is_visible()
            assert not page.locator('#footage .branding').is_visible()
            assert 'one finished mix' in page.locator('#taskHelp').inner_text().lower()
            page.locator('[data-drop=audio] input').set_input_files(str(mix))
            page.wait_for_function('!state.uploads && state.files.length===1 && !document.querySelector("#continueFootage").disabled')
            page.screenshot(path=str(out/'03-finished-mix.png'),full_page=True)
            held=[];master_posts=[]
            def hold_first_status(route):
                if route.request.method=='GET' and not route.request.url.endswith('/result') and not held:
                    held.append(route)
                else:route.continue_()
            page.route('**/montara/master/*',hold_first_status)
            page.on('request',lambda request:master_posts.append(request.url) if request.method=='POST' and request.url.endswith('/montara/master') else None)
            page.locator('#continueFootage').click()
            for _ in range(100):
                page.wait_for_timeout(50)
                if held:break
            assert held
            page.go_back();page.locator('#footage').wait_for(state='visible')
            held[0].fulfill(response=held[0].fetch())
            page.wait_for_timeout(300)
            assert page.locator('#footage').is_visible(), 'Late status must not jump out of browser Back'
            page.locator('#continueFootage').click()
            page.wait_for_selector('#result:not([hidden]),#failed:not([hidden])',timeout=120000)
            assert len(master_posts)==1, 'Resume must not start another master'
            page.go_back();page.locator('#footage').wait_for(state='visible')
            page.go_forward();page.locator('#result').wait_for(state='visible',timeout=30000)
            assert page.locator('#result').is_visible(),page.locator('#errorText').inner_text()
            assert 'dBTP' in page.locator('#resultInfo').inner_text()
            assert page.locator('#resultAudio').is_visible()
            assert not page.locator('#playerWrap').is_visible()
            page.locator('#resultAudio').evaluate('audio=>audio.play()')
            page.wait_for_function('document.querySelector("#resultAudio").currentTime>.1')
            page.locator('#resultAudio').evaluate('audio=>audio.pause()')
            page.screenshot(path=str(out/'04-master-result.png'),full_page=True)
            response=page.request.get(url+page.locator('#resultAudio').get_attribute('src'))
            assert response.ok and len(response.body())>10000
            assert not list((out/'data'/'Mixer').glob('*')), 'No stem mixer for master-only'
            before=page.locator('#resultAudio').get_attribute('src')
            page.reload();page.locator('#result').wait_for(state='visible',timeout=30000)
            assert page.locator('#resultAudio').get_attribute('src')==before
            assert not page.locator('#playerWrap').is_visible()
            page.locator('[data-go=mode]:visible').first.click();page.locator('[data-intent=music]').click()
            page.locator('[data-audio-task=song]').click()
            bass=out/'Bass.wav';sf.write(bass,.1*np.sin(2*np.pi*110*t),sr)
            page.locator('[data-drop=audio] input').set_input_files([str(mix),str(bass)])
            page.wait_for_function('audioTracks().length===2 && !state.uploads')
            page.locator('#continueFootage').click()
            page.locator('#mix').wait_for(state='visible',timeout=120000)
            page.wait_for_function('!document.querySelector("#useMix").disabled',timeout=120000)
            assert page.locator('#strips .strip').count()==2
            assert not page.locator('[data-step=frames]').is_visible()
            page.screenshot(path=str(out/'05-song-mixer.png'),full_page=True)
            page.locator('#useMix').click()
            page.wait_for_selector('#result:not([hidden]),#failed:not([hidden])',timeout=180000)
            assert page.locator('#result').is_visible(),page.locator('#errorText').inner_text()
            assert page.locator('#resultAudio').is_visible() and not page.locator('#playerWrap').is_visible()
            page.screenshot(path=str(out/'06-song-mixed.png'),full_page=True)
            page.locator('[data-go=mode]:visible').first.click();page.locator('[data-intent=music]').click()
            page.locator('[data-audio-task=session]').click()
            assert page.locator('#fullSessionOn').is_checked() and page.locator('#stageAudioOnly').is_checked()
            assert not page.locator('[data-drop=video]').is_visible()
            assert 'hours' in page.locator('#taskHelp').inner_text()
            page.screenshot(path=str(out/'05-session-explanation.png'),full_page=True)
            page.go_back();page.locator('#musicChoices').wait_for(state='visible')
            page.locator('#modeQuestionBack').click();page.locator('[data-intent=video]').click()
            page.locator('[data-platform=youtube]').click()
            assert page.locator('[data-drop=video]').is_visible() and page.evaluate('state.audioTask===null')
            page.locator('[data-go=mode]:visible').first.click();page.set_viewport_size({'width':390,'height':844})
            page.screenshot(path=str(out/'06-mobile-questions.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
            assert not errors,errors
            browser.close()
        (out/'summary.json').write_text(json.dumps({'passed':True,'master_downloaded':True,'browser_errors':errors}))
    finally:server.terminate();server.wait(timeout=20);log.close()
if __name__=='__main__':main()
