"""Real browser: 360 proxy + two session stems -> matched song master -> camera range."""
import argparse,json,os,shutil,subprocess,sys,time
from pathlib import Path
from urllib.request import urlopen
import numpy as np
import soundfile as sf
from playwright.sync_api import sync_playwright
from e2e_journey import ROOT, free_port, run


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    media=out/'sources';media.mkdir(exist_ok=True)
    sr=8000;t=np.arange(sr*390)/sr
    active=((t>=3)&(t<180))|((t>=210)&(t<387))
    rng=np.random.default_rng(942)
    # Distinct musical accents: repeated metronomes cannot prove which song matched.
    beats=rng.uniform(.1,1,780)
    pulse=np.exp(-10*(t%.5))*beats[np.minimum((t*2).astype(int),779)]
    tracks=[]
    for name,freq in [('Kick',80),('Bass',160)]:
        sound=((.07*np.sin(2*np.pi*freq*t)+.04*rng.standard_normal(t.size))*active*(pulse if name=='Kick' else .3+.7*pulse)).astype('float32')
        tracks.append(sound);sf.write(media/(name+'.wav'),sound,sr)
    sf.write(media/'guide.wav',sum(tracks),sr)
    source=media/'panorama.mp4'
    run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=640x320:rate=24:duration=20',
         '-ss','240','-i',str(media/'guide.wav'),'-t','20','-c:v','libx264','-preset','ultrafast','-crf','10','-c:a','aac',str(source)])
    sys.path.insert(0,str(ROOT/'companion'))
    from companion import probe
    from spherical_proxy import preserve_panorama
    preserve_panorama(source,probe)
    home=out/'companion';home.mkdir(exist_ok=True)
    port,hport=free_port(),free_port();url=f'http://127.0.0.1:{port}';base=f'http://127.0.0.1:{hport}'
    env={**os.environ,'MONTARA_COMPANION_HOME':str(home),'MONTARA_COMPANION_PORT':str(hport),
         'MONTARA_COMPANION_ROOTS':str(media),'OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'}
    logs=[(out/'server.log').open('w'),(out/'companion.log').open('w')]
    procs=[subprocess.Popen([sys.executable,str(ROOT/'app.py'),'--port',str(port),'--data',str(out/'data'),'--no-samples'],cwd=ROOT,env=env,stdout=logs[0],stderr=subprocess.STDOUT),
           subprocess.Popen([sys.executable,str(ROOT/'companion/companion.py')],cwd=ROOT,env=env,stdout=logs[1],stderr=subprocess.STDOUT)]
    try:
        for endpoint in (url+'/montara/version',base+'/health'):
            for _ in range(300):
                try:
                    with urlopen(endpoint,timeout=2):break
                except Exception:
                    assert all(p.poll() is None for p in procs),'Test process exited: inspect logs'
                    time.sleep(.5)
            else:raise AssertionError('Server not ready')
        with sync_playwright() as pw:
            browser=pw.chromium.launch();page=browser.new_page(viewport={'width':1280,'height':900})
            page.on('pageerror',lambda e:print('BROWSER',e,flush=True))
            page.route('**/companion.js',lambda r:r.fulfill(body=(ROOT/'web/companion.js').read_text().replace('http://127.0.0.1:47820',base),content_type='application/javascript'))
            page.route(base+'/projects',lambda r:r.fulfill(json=None,headers={'Access-Control-Allow-Origin':url}))
            # Any original-video fallback must fail this journey rather than authorize it.
            page.on('dialog',lambda d:(_ for _ in ()).throw(AssertionError(d.message)))
            page.goto(url);page.locator('#mode').wait_for(state='visible',timeout=30000)
            page.locator('[data-platform="youtube"]').click();page.locator('#videoName').fill('Session camera song')
            page.locator('#fullSessionOn').check()
            page.wait_for_function('montaraCompanion.info !== null',timeout=10000)
            page.locator('[data-drop=video] input').set_input_files(str(source))
            page.locator('[data-drop=audio] input').set_input_files([str(media/'Kick.wav'),str(media/'Bass.wav')])
            page.wait_for_function("state.files.length===3 && !state.uploads && state.files.every(f=>f.path)",timeout=120000)
            assert page.evaluate("state.files.filter(f=>f.kind==='video').every(f=>f.small && f.original && f.projection==='equirect')")
            assert page.evaluate('state.files.filter(f=>f.preview).length')==2
            page.screenshot(path=str(out/'01-proxy-and-stems.png'),full_page=True)
            page.locator('#continueFootage').click()
            page.wait_for_function("!document.querySelector('#cameras').hidden || /Could not|different songs|several songs|failed/i.test(document.querySelector('#toast:not([hidden])')?.textContent || '') || document.querySelector('#failed:not([hidden])')",timeout=600000)
            assert page.locator('#cameras').is_visible(),page.locator('#toast').inner_text()
            assert page.evaluate('fullSession.data.songs.filter(s=>s.selected).length')==1
            song=page.evaluate('fullSession.data.songs.find(s=>s.selected)')
            assert song['start']>180,song
            assert page.locator('#rangeTrack option').count()==1
            assert page.locator('#rangeTrack option').inner_text()=='Your song master'
            assert page.evaluate('!!state.mixMaster')
            page.wait_for_function("document.querySelector('.pano-img').style.backgroundImage !== ''",timeout=60000)
            page.locator('.pano').scroll_into_view_if_needed()
            page.locator('.pano').click(position={'x':160,'y':80})
            page.wait_for_function("document.querySelector('.preview img').naturalWidth>0 && !document.querySelector('.preview img').hidden",timeout=30000)
            page.evaluate('()=>new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)))')
            page.locator('.pano').screenshot(path=str(out/'panorama-visible.png'))
            page.screenshot(path=str(out/'02-master-before-range.png'),full_page=True)
            summary={'passed':True,'panorama_proxy':True,'stems_mixed':2,'matched_song':song,'master_before_range':True}
            (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
            browser.close()
    finally:
        for p in procs:
            p.terminate()
            try:p.wait(timeout=15)
            except subprocess.TimeoutExpired:p.kill();p.wait()
        for log in logs:log.close()


if __name__=='__main__':main()
