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

from native_real_media_input import validate_real_sources, hash_streamed


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--real-camera',action='append',default=[],
                        help='existing local video, specify exactly twice')
    parser.add_argument('--real-master',type=str,
                        help='existing local audio master; NEVER uploaded to GitHub')
    args=parser.parse_args()
    real_mode=bool(args.real_camera or args.real_master)
    if real_mode:
        if len(args.real_camera)!=2 or not args.real_master:
            parser.error('Real footage requires two --real-camera arguments and --real-master')
        try:
            cameras,master=validate_real_sources(args.real_camera,args.real_master,args.output)
        except ValueError as exc:
            parser.error(str(exc))
        media=None  # originals remain in their existing private directories
    else:
        media=args.output.resolve()/'fixtures'
        cameras=[media/f'camera-{i}.mp4' for i in range(2)]
        master=media/'master.wav'
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    if not real_mode:
        media.mkdir(exist_ok=True)
        run(['ffmpeg','-v','error','-y','-f','lavfi','-i','anoisesrc=color=pink:seed=9876:amplitude=.2:duration=20','-ar','48000',str(master)])
        for i in range(2):
            run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=1920x1080:rate=30:duration=20','-i',str(master),'-vf',f'eq=brightness={-.1+i*.04}','-c:v','libx264','-preset','ultrafast','-threads','2','-c:a','aac','-shortest',str(cameras[i])])
    home=out/'companion';home.mkdir(exist_ok=True)
    install_layout(home)
    for name in ('companion.py','video_jobs.py','video_recipe.py'):shutil.copy2(ROOT/'companion'/name,home/name)
    chosen=out/'chosen-folder';chosen.mkdir(exist_ok=True)
    project_id='b'*16;(home/'projects.json').write_text(json.dumps({project_id:str(chosen)}))
    port,helper_port=free_port(),free_port();url=f'http://127.0.0.1:{port}';base=f'http://127.0.0.1:{helper_port}'
    # Selected real sources are only whitelisted locally in this isolated Companion process.
    roots=sorted({str(p.parent) for p in [*cameras,master]}) if real_mode else [str(media)]
    env={**os.environ,'MONTARA_COMPANION_HOME':str(home),'MONTARA_COMPANION_ROOTS':os.pathsep.join(roots),'MONTARA_COMPANION_PORT':str(helper_port),'PYTHONUNBUFFERED':'1'}
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
            channel=os.environ.get('MONTARA_TEST_BROWSER_CHANNEL')
            browser=pw.chromium.launch(**({'channel':channel} if channel else {}));page=browser.new_page(viewport={'width':1440,'height':1000})
            assert page.evaluate('!!document.createElement("video").canPlayType(\'video/mp4;codecs="avc1.42E01E"\')'), 'Native playback acceptance needs a browser with H.264 (set MONTARA_TEST_BROWSER_CHANNEL=chrome)'
            page.on('console',lambda message:print('BROWSER_ERROR',message.text,flush=True) if message.type=='error' else None)
            page.route('**/companion.js',lambda route:route.fulfill(body=(ROOT/'web/companion.js').read_text().replace('http://127.0.0.1:47820',base),content_type='application/javascript'))
            page.route(base+'/projects',lambda route:route.fulfill(json={'id':project_id,'folder':str(chosen)},headers={'Access-Control-Allow-Origin':url}))
            page.goto(url);page.locator('#mode').wait_for(state='visible',timeout=30000)
            if page.locator('[data-intent=video]').is_visible(): page.locator('[data-intent=video]').click()
            page.locator('.mode[data-platform="youtube"]').click()
            page.locator('#videoName').fill('Native acceptance')
            page.locator('[data-drop=video] input').set_input_files([str(p) for p in cameras]+[str(master)])
            page.wait_for_function("!document.querySelector('#continueFootage').disabled",timeout=180000)
            page.locator('input[name=branding][value="none"]').check()
            page.locator('#continueFootage').click();page.locator('#cameras').wait_for(state='visible',timeout=180000)
            page.locator('#continueCameras').click();page.wait_for_selector('#frames:not([hidden]), #failed:not([hidden])',timeout=600000)
            assert not page.locator('#failed').is_visible(),page.locator('#errorText').inner_text()
            page.wait_for_function("!document.querySelector('#framesHint').textContent.includes('Preparing')",timeout=180000)
            thumb=page.locator('.frame .thumb').first
            thumb.click()
            page.wait_for_function("document.querySelector('.frame video').readyState>=2",timeout=120000)
            thumb.click()  # Explicit user gesture unlocks audio on restrictive browsers.
            page.wait_for_function("!document.querySelector('.frame video').paused && !document.querySelector('.frame video').muted",timeout=15000)
            page.screenshot(path=str(out/'audible-frame-preview.png'))
            recovered=browser.new_page(viewport={'width':390,'height':844})
            recovered.goto(url+'/?resume=frames')
            recovered.locator('#frames').wait_for(state='visible',timeout=120000)
            assert recovered.locator('#frameGrid .frame').count()>0
            recovered.screenshot(path=str(out/'mobile-project-recovered.png'))
            recovered.close()
            page.locator('.frame .shot-edit').first.click();dialog=page.locator('dialog.cut-dialog')
            dialog.wait_for(state='visible');assert dialog.locator('[name=lightAuto]').count()==0
            dialog.locator('.flat-zoom-row input').evaluate("e=>{e.value='3.4';e.dispatchEvent(new Event('input',{bubbles:true}));}")
            page.wait_for_timeout(1000);page.screenshot(path=str(out/'framing-controls.png'),full_page=True)
            dialog.get_by_role('button',name='Save shot',exact=True).click();dialog.wait_for(state='detached',timeout=120000)
            page.locator('#renderFrames').click()
            page.locator('#making #renderBars').wait_for(state='visible',timeout=120000)
            page.wait_for_function("[...document.querySelectorAll('#renderBars i')].some(bar=>Number(bar.style.getPropertyValue('--p'))>=.99)",timeout=180000)
            page.screenshot(path=str(out/'native-shot-progress.png'),full_page=True)
            page.wait_for_selector('#result:not([hidden]), #failed:not([hidden])',timeout=300000)
            assert not page.locator('#failed').is_visible(),page.locator('#errorText').inner_text()
            result_url=page.locator('#resultVideo').get_attribute('src');assert result_url.startswith(base+'/video-renders/')
            final=out/'render.mp4'
            with urlopen(Request(result_url,headers={'Origin':url}),timeout=120) as response,final.open('wb') as target:
                shutil.copyfileobj(response,target,1024*1024)
            # preload=metadata need not decode a picture until the user seeks
            # or plays (Chromium on Linux can stop at HAVE_METADATA).
            try:page.wait_for_function("document.querySelector('#resultVideo').readyState>=1",timeout=30000)
            except Exception:
                print('NATIVE_VIDEO_STATE',page.locator('#resultVideo').evaluate('v=>({ready:v.readyState,network:v.networkState,error:v.error?.message,duration:v.duration,seeking:v.seeking,h264:v.canPlayType(\'video/mp4;codecs="avc1.42E01E"\')})'),flush=True)
                raise
            page.locator('#resultVideo').evaluate('video=>{video.currentTime=2;}')
            page.wait_for_function("!document.querySelector('#resultVideo').seeking && document.querySelector('#resultVideo').readyState>=2",timeout=30000)
            page.screenshot(path=str(out/'native-result.png'),full_page=True)
            result_url=page.locator('#resultVideo').get_attribute('src');assert result_url.startswith(base+'/video-renders/')
            assert page.locator('#download').get_attribute('download')=='Native acceptance.mp4'
            with urlopen(page.locator('#download').get_attribute('href'),timeout=120) as download:
                assert 'Native%20acceptance.mp4' in download.headers['Content-Disposition']
            result=page.request.get(result_url,headers={'Origin':url,'Range':'bytes=0-1023'});assert result.status==206
            page.reload();page.locator('#result').wait_for(state='visible',timeout=60000)
            assert page.locator('#resultVideo').get_attribute('src')==result_url
            page.screenshot(path=str(out/'native-result-restored.png'),full_page=True)
            # This branch bypasses the old server export rather than rendering twice.
            status=page.request.get(url+'/api/v1/wizard/status').json();assert not status.get('result')
            jobs=list((chosen/'.montara-renders').glob('*/render.json'));assert len(jobs)==1
            recipe=json.loads(jobs[0].read_text())
            originals_by_name={p.name:p for p in cameras}
            for value in recipe['source_files'].values():
                original=Path(value)
                expected=originals_by_name.get(original.name)
                assert expected is not None and expected.is_file() and '.small.' not in original.name
                assert hash_streamed(original)==hash_streamed(expected)
            assert any(s.get('flat_framing',{}).get('zoom')==3.4 for s in recipe['recipe']['segments'])
            assert any(s.get('video_light',{}).get('auto') is True for s in recipe['recipe']['segments'])
            info=json.loads(run(['ffprobe','-v','error','-show_streams','-of','json',str(final)]))
            video=next(s for s in info['streams'] if s['codec_type']=='video')
            if not real_mode:
                assert (video['width'],video['height'])==(1920,1080)
            else:
                assert video['width']>0 and video['height']>0
                assert any(s['codec_type']=='audio' for s in info['streams'])
            run(['ffmpeg','-v','error','-i',str(final),'-f','null','-'])
            browser.close();(out/'summary.json').write_text(json.dumps({'passed':True,'size':f"{video['width']}x{video['height']}",'original_sources':len(recipe['source_files']),'native_render':True,'server_export_skipped':True,'real_footage':real_mode,'architecture':'Companion local original render, Engine remote recipe in isolated local test'},indent=2));print((out/'summary.json').read_text())
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
