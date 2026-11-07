"""Real Stage: unrelated camera review + silent B-roll + final video export."""
import argparse,json,subprocess,sys,time,shutil
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright
from e2e_journey import free_port,run
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    media=out/'media';media.mkdir(exist_ok=True)
    for name,seed in [('master.wav',123),('other-song.wav',456)]:
        path=media/name
        if not path.exists():run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'anoisesrc=color=pink:seed={seed}:amplitude=0.1:duration=60','-ar','48000',str(path)])
    for name,audio in [('camera.mp4','master.wav'),('other-song.mp4','other-song.wav'),('silent.mp4',None)]:
        target=media/name
        if target.exists():continue
        command=['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=848x464:rate=30:duration=60']
        if audio:command+=['-i',str(media/audio)]
        command+=['-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p']
        if audio:command+=['-c:a','aac','-shortest']
        run(command+[str(target)])
    port=free_port();url=f'http://127.0.0.1:{port}'
    log=(out/'server.log').open('w');server=subprocess.Popen([sys.executable,str(ROOT/'app.py'),'--port',str(port),'--data',str(out/'data'),'--no-samples'],stdout=log,stderr=subprocess.STDOUT)
    try:
        for _ in range(120):
            try:urlopen(url+'/api/v1/wizard/status',timeout=1).close();break
            except Exception:time.sleep(.5)
        with sync_playwright() as pw:
            browser=pw.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':960})
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.route('http://127.0.0.1:47820/**',lambda route:route.abort())
            def consent(dialog):
                assert 'For testing only: upload the ORIGINAL video' in dialog.message
                dialog.accept()
            page.on('dialog',consent)
            page.goto(url);page.locator('#mode').wait_for(state='visible');page.locator('[data-intent=video]').click();page.locator('[data-platform=youtube]').click()
            page.locator('[data-drop=video] input').set_input_files([str(media/x) for x in ['camera.mp4','other-song.mp4','silent.mp4']])
            page.locator('[data-drop=audio] input').set_input_files(str(media/'master.wav'))
            page.wait_for_function('state.files.length===4 && !state.uploads && state.files.every(f=>f.path)',timeout=120000)
            page.locator('input[name=branding][value=none]').check()
            page.locator('#continueFootage').click();page.locator('#cameras').wait_for(state='visible',timeout=120000)
            page.locator('#continueCameras').click()
            dialog=page.locator('dialog.cut-dialog');dialog.wait_for(state='visible',timeout=180000)
            assert 'other-song.mp4' in dialog.inner_text()
            assert 'silent.mp4' not in dialog.inner_text()
            page.screenshot(path=str(out/'01-review-before-render.png'),full_page=True)
            dialog.get_by_role('button',name='Use these sources',exact=True).click()
            page.wait_for_selector('#frames:not([hidden]),#failed:not([hidden])',timeout=300000)
            assert page.locator('#frames').is_visible(),page.locator('#errorText').inner_text()
            assert page.evaluate("state.files.some(f=>f.name==='silent.mp4' && f.usage==='filler')")
            assert page.evaluate("[...state.syncExcluded].some(p=>p.endsWith('other-song.mp4'))")
            project=page.request.get(url+'/api/v1/project').json()
            assert len(project['inputs']['videos'])==2
            # Source review preserves the uploaded unrelated camera in the UI,
            # while the draft registers only the selected camera and silent B-roll.
            assert page.evaluate("state.files.some(f=>f.name==='other-song.mp4')")
            page.evaluate("async () => await saveCameras()")
            saved=page.request.get(url+'/api/v1/project').json()
            types=saved['settings']['edit']['camera_types']
            assert len(types)==2
            assert all(v['path'] in types for v in saved['inputs']['videos'])
            assert not any(k.endswith('other-song.mp4') for k in types)
            assert project['settings']['edit']['filler_cutaways']
            page.wait_for_function("!document.querySelector('#framesHint').textContent.includes('Preparing')",timeout=180000)
            page.screenshot(path=str(out/'02-cameras-and-silent-filler.png'),full_page=True)
            page.locator('#renderFrames').click()
            page.wait_for_selector('#result:not([hidden]),#failed:not([hidden])',timeout=600000)
            assert page.locator('#result').is_visible(),page.locator('#errorText').inner_text()
            # Headless Chromium on Linux does not ship an H.264 decoder.
            # Test the actual downloaded output end-to-end with ffprobe and ffmpeg;
            # when the browser advertises AVC support, test HTML5 playback too.
            video=page.locator('#resultVideo')
            source=video.get_attribute('src')
            assert source, 'Exported video must have a playable/downloadable URL'
            from urllib.parse import urljoin
            result=out/'render.mp4'
            with urlopen(urljoin(url,source),timeout=180) as incoming, result.open('wb') as dst:
                assert incoming.status==200
                shutil.copyfileobj(incoming,dst,1024*1024)
            probe=json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(result)]))
            assert any(stream['codec_type']=='video' for stream in probe['streams'])
            assert any(stream['codec_type']=='audio' for stream in probe['streams'])
            assert float(probe['format']['duration'])>1
            run(['ffmpeg','-v','error','-i',str(result),'-f','null','-'])
            can_play=video.evaluate("v=>v.canPlayType('video/mp4; codecs=\\\"avc1.42E01E\\\"') !== ''")
            if can_play:
                page.locator('#playerWrap .icon-btn').first.click()
                page.wait_for_function('document.querySelector("#resultVideo").currentTime>.2',timeout=30000)
                video.evaluate('v=>v.pause()')
            else:
                print('Headless Chromium cannot decode H.264; checked complete downloaded MP4 with ffmpeg instead.')
            page.screenshot(path=str(out/'03-exported.png'),full_page=True)
            status=page.request.get(url+'/api/v1/wizard/status').json()
            artifact=Path(status['project_path'])/'artifacts'/'edit_plan.json'
            plan=json.loads(artifact.read_text());filler=[s for s in plan['segments'] if s.get('filler')]
            assert filler and all(s['filename']=='silent.mp4' for s in filler)
            assert not errors,errors
            browser.close()
        (out/'summary.json').write_text(json.dumps({'passed':True,'filler_shots':len(filler),'sources':2,'browser_errors':errors}))
    finally:server.terminate();server.wait(timeout=20);log.close()
if __name__=='__main__':main()
