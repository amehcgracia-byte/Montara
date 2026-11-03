"""Isolated browser -> engine recipe -> companion -> original-quality file.

Uses a preselected test folder in place of the OS folder picker. All media,
proxying, HTTP, analysis, lighting and final rendering are real.
"""
import argparse,hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
from urllib.request import Request,urlopen
from playwright.sync_api import sync_playwright
from e2e_journey import ROOT,free_port,run
from test_local_video import install_layout


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    media=out/'fixtures';media.mkdir(exist_ok=True)
    master=media/'master.wav'
    run(['ffmpeg','-v','error','-y','-f','lavfi','-i','anoisesrc=color=pink:seed=9876:amplitude=.2:duration=20','-ar','48000',str(master)])
    for i in range(2):
        run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=1920x1080:rate=30:duration=20','-i',str(master),'-vf',f'eq=brightness={-.1+i*.04}','-c:v','libx264','-preset','ultrafast','-threads','2','-c:a','aac','-shortest',str(media/f'camera-{i}.mp4')])
    home=out/'companion';home.mkdir(exist_ok=True)
    install_layout(home)
    for name in ('companion.py','video_jobs.py','video_recipe.py'):shutil.copy2(ROOT/'companion'/name,home/name)
    chosen=out/'chosen-folder';chosen.mkdir(exist_ok=True)
    project_id='b'*16;(home/'projects.json').write_text(json.dumps({project_id:str(chosen)}))
    port,helper_port=free_port(),free_port();url=f'http://127.0.0.1:{port}';base=f'http://127.0.0.1:{helper_port}'
    env={**os.environ,'MONTARA_COMPANION_HOME':str(home),'MONTARA_COMPANION_ROOTS':str(media),'MONTARA_COMPANION_PORT':str(helper_port),'PYTHONUNBUFFERED':'1'}
    logs=[(out/'server.log').open('w'),(out/'companion.log').open('w')]
    processes=[subprocess.Popen([sys.executable,str(ROOT/'app.py'),'--port',str(port),'--data',str(out/'data')],stdout=logs[0],stderr=subprocess.STDOUT,env=env),subprocess.Popen([sys.executable,str(home/'companion.py')],stdout=logs[1],stderr=subprocess.STDOUT,env=env)]
    try:
        for endpoint in (url+'/api/v1/wizard/status',base+'/health'):
            for _ in range(120):
                try:
                    with urlopen(endpoint,timeout=2):break
                except Exception:time.sleep(1)
            else:raise AssertionError('Isolated test host did not start')
        with sync_playwright() as pw:
            browser=pw.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000})
            page.route('**/companion.js',lambda route:route.fulfill(body=(ROOT/'web/companion.js').read_text().replace('http://127.0.0.1:47820',base),content_type='application/javascript'))
            page.route(base+'/projects',lambda route:route.fulfill(json={'id':project_id,'folder':str(chosen)},headers={'Access-Control-Allow-Origin':url}))
            page.goto(url);page.locator('#mode').wait_for(state='visible',timeout=30000)
            page.locator('.mode[data-platform="youtube"]').click()
            page.locator('#videoName').fill('Native acceptance')
            page.locator('[data-drop=video] input').set_input_files([str(media/f'camera-{i}.mp4') for i in range(2)]+[str(master)])
            page.wait_for_function("!document.querySelector('#continueFootage').disabled",timeout=180000)
            page.locator('input[name=branding][value="none"]').check()
            page.locator('#continueFootage').click();page.locator('#cameras').wait_for(state='visible',timeout=180000)
            page.locator('#continueCameras').click();page.wait_for_selector('#frames:not([hidden]), #failed:not([hidden])',timeout=600000)
            assert not page.locator('#failed').is_visible(),page.locator('#errorText').inner_text()
            page.wait_for_function("!document.querySelector('#framesHint').textContent.includes('Preparing')",timeout=180000)
            page.locator('.frame .shot-edit').first.click();dialog=page.locator('dialog.cut-dialog')
            dialog.wait_for(state='visible');assert dialog.locator('[name=lightAuto]').is_checked()
            dialog.locator('[name=light]').evaluate("e=>{e.value='0.05';e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));}")
            page.wait_for_timeout(1000);page.screenshot(path=str(out/'light-controls.png'),full_page=True)
            dialog.get_by_role('button',name='Save shot',exact=True).click();dialog.wait_for(state='detached',timeout=120000)
            page.locator('#renderFrames').click()
            page.locator('#making #renderBars').wait_for(state='visible',timeout=120000)
            page.wait_for_function("[...document.querySelectorAll('#renderBars i')].some(bar=>Number(bar.style.getPropertyValue('--p'))>=.99)",timeout=180000)
            page.screenshot(path=str(out/'native-shot-progress.png'),full_page=True)
            page.wait_for_selector('#result:not([hidden]), #failed:not([hidden])',timeout=300000)
            assert not page.locator('#failed').is_visible(),page.locator('#errorText').inner_text()
            # preload=metadata need not decode a picture until the user seeks
            # or plays (Chromium on Linux can stop at HAVE_METADATA).
            page.wait_for_function("document.querySelector('#resultVideo').readyState>=1",timeout=30000)
            page.locator('#resultVideo').evaluate('video=>{video.currentTime=2;}')
            page.wait_for_function("!document.querySelector('#resultVideo').seeking && document.querySelector('#resultVideo').readyState>=2",timeout=30000)
            page.screenshot(path=str(out/'native-result.png'),full_page=True)
            result_url=page.locator('#resultVideo').get_attribute('src');assert result_url.startswith(base+'/video-renders/')
            assert page.locator('#download').get_attribute('download')=='Native acceptance.mp4'
            with urlopen(page.locator('#download').get_attribute('href'),timeout=120) as download:
                assert 'Native%20acceptance.mp4' in download.headers['Content-Disposition']
            result=page.request.get(result_url,headers={'Origin':url,'Range':'bytes=0-1023'});assert result.status==206
            final=out/'render.mp4'
            # Stream the full file outside Playwright's base64 protocol: repeatedly
            # concatenating its large message is quadratic in the Python client.
            with urlopen(Request(result_url,headers={'Origin':url}),timeout=120) as response,final.open('wb') as target:
                shutil.copyfileobj(response,target,1024*1024)
            # This branch bypasses the old server export rather than rendering twice.
            status=page.request.get(url+'/api/v1/wizard/status').json();assert not status.get('result')
            jobs=list((chosen/'.montara-renders').glob('*/render.json'));assert len(jobs)==1
            recipe=json.loads(jobs[0].read_text())
            for value in recipe['source_files'].values():
                original=Path(value);expected=media/original.name
                assert expected.is_file() and '.small.' not in original.name
                assert hashlib.sha256(original.read_bytes()).digest()==hashlib.sha256(expected.read_bytes()).digest()
            assert any(s.get('video_light',{}).get('light')==.05 for s in recipe['recipe']['segments'])
            info=json.loads(run(['ffprobe','-v','error','-show_streams','-of','json',str(final)]))
            video=next(s for s in info['streams'] if s['codec_type']=='video');assert (video['width'],video['height'])==(1920,1080)
            run(['ffmpeg','-v','error','-i',str(final),'-f','null','-'])
            browser.close();(out/'summary.json').write_text(json.dumps({'passed':True,'size':'1920x1080','original_sources':len(recipe['source_files']),'native_render':True,'server_export_skipped':True},indent=2));print((out/'summary.json').read_text())
    except Exception:
        try:print('NATIVE_VIDEO_STATE',page.locator('#resultVideo').evaluate('v=>({ready:v.readyState,network:v.networkState,error:v.error?.message,duration:v.duration,seeking:v.seeking})'),flush=True)
        except Exception:pass
        raise
    finally:
        for process in processes:
            process.terminate()
            try:process.wait(timeout=20)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        for log in logs:log.close()


if __name__=='__main__':main()
