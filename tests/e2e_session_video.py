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
            if page.locator('[data-intent=video]').is_visible(): page.locator('[data-intent=video]').click()
            page.locator('[data-platform="youtube"]').click();page.locator('#videoName').fill('Session camera song')
            page.locator('#fullSessionOn').check()
            page.wait_for_function('montaraCompanion.info !== null',timeout=10000)
            page.locator('[data-drop=video] input').set_input_files(str(source))
            page.locator('[data-drop=audio] input').set_input_files([str(media/'Kick.wav'),str(media/'Bass.wav')])
            page.wait_for_function("state.files.length===3 && !state.uploads && state.files.every(f=>f.path)",timeout=120000)
            assert page.evaluate("state.files.filter(f=>f.kind==='video').every(f=>f.small && f.original && f.projection==='equirect')")
            assert page.evaluate('state.files.filter(f=>f.preview).length')==2
            compressed=page.evaluate('audioTracks().map(f=>f.path)')
            assert all(Path(p).suffix=='.ogg' for p in compressed)
            assert all(sf.info(p).subtype=='OPUS' for p in compressed)
            assert not list((out/'data'/'Uploads').glob('*/*.wav')), 'No full-jam PCM expanded during upload'
            page.screenshot(path=str(out/'01-proxy-and-stems.png'),full_page=True)
            # The user's manual instrument choice survives the compact source suffix.
            page.locator('#audioFiles [data-track-type]').first.select_option('sax')
            renders=[]
            page.on('request',lambda request:renders.append(request.url) if '/montara/session/' in request.url and request.url.endswith('/render') else None)
            page.locator('#continueFootage').click()
            # No browser mixer preview or acceptance in the camera + stems path.
            mixer_requests=[]
            page.on('request',lambda request:mixer_requests.append(request.url) if '/montara/mix' in request.url else None)
            page.wait_for_function("!document.querySelector('#cameras').hidden || /Could not|different songs|several songs|failed/i.test(document.querySelector('#toast:not([hidden])')?.textContent || '') || document.querySelector('#failed:not([hidden])')",timeout=600000)
            assert page.locator('#cameras').is_visible(),page.locator('#toast').inner_text()
            assert page.evaluate('fullSession.data.songs.filter(s=>s.selected).length')==1
            song=page.evaluate('fullSession.data.songs.find(s=>s.selected)')
            session_id=page.evaluate('fullSession.id')
            assert abs(song['start']-240)<1 and abs(song['end']-260)<1,song
            assert page.locator('#rangeTrack option').count()==1
            assert page.locator('#rangeTrack option').inner_text()=='Your song master'
            assert page.evaluate('!!state.mixMaster')
            assert len(renders)==1
            assert page.evaluate('fullSession.data.results.length')==1
            assert not mixer_requests, 'Automatic master must not prepare/analyse a separate browser mixer'
            assert not page.locator('#mix').is_visible()
            page.wait_for_function('range.duration>18 && range.duration<22',timeout=30000)
            download=page.request.get(url+page.locator('#mixedMasterDownload').get_attribute('href'))
            assert download.ok and 'audio/' in download.headers.get('content-type','')
            master=out/'master.mp3';master.write_bytes(download.body())
            raw=subprocess.check_output(['ffmpeg','-v','error','-ss','5','-i',str(master),'-t','1','-ac','1','-ar','8000','-f','f32le','-'])
            spectrum=np.abs(np.fft.rfft(np.frombuffer(raw,dtype=np.float32)))
            assert all(spectrum[freq]>10*np.median(spectrum[40:500]) for freq in (80,160)), 'Both musical stems must be present in the final master'
            page.wait_for_function("document.querySelector('.pano-img').style.backgroundImage !== ''",timeout=60000)
            page.locator('.pano').scroll_into_view_if_needed()
            page.locator('.pano').click(position={'x':160,'y':80})
            page.wait_for_function("document.querySelector('.preview img').naturalWidth>0 && !document.querySelector('.preview img').hidden",timeout=30000)
            page.evaluate('()=>new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)))')
            page.locator('.pano').screenshot(path=str(out/'panorama-visible.png'))
            from PIL import Image, ImageStat
            assert max(ImageStat.Stat(Image.open(out/'panorama-visible.png')).stddev)>30, 'Panorama must be visibly drawn'
            page.screenshot(path=str(out/'02-master-before-range.png'),full_page=True)
            # Recovering the draft must not replace the two stems with its guide/master.
            page.goto(url+'/?resume=footage');page.locator('#footage').wait_for(state='visible')
            assert page.locator('#audioFiles li').count()==2
            assert page.locator('#videoFiles li').count()==1
            assert page.evaluate('audioTracks().every(f=>!f.path.includes("listen-all"))')
            assert page.evaluate('!!state.mixMaster')
            page.screenshot(path=str(out/'03-source-stems-recovered.png'),full_page=True)
            session_dir=out/'data'/'Sessions'/session_id
            session_data=json.loads((session_dir/'session.json').read_text())
            assert session_data['track_types'].get('kick',{}).get('type')=='sax'
            assert not (session_dir/'extras.log').exists(), 'Video mode must not launch full-song detection/listening extras'
            assert json.loads((session_dir/'waveform.json').read_text())['source']=='video-sync-guide'
            extracted=list((session_dir/'songs'/'1'/'tracks').glob('*.wav'))
            assert len(extracted)==2
            for track in extracted:
                assert 18<sf.info(track).duration<22, 'Only camera-range PCM is extracted, not the whole jam/song'
            summary={'passed':True,'panorama_proxy':True,'stems_mixed':2,'automatic_master':True,'browser_mixer_skipped':True,'compact_uploads':True,'downloadable_master':True,'matched_song':song,'master_before_range':True,'session_seconds':390,'mixed_seconds':round(song['end']-song['start'],3),'all_song_detection_skipped':True}
            (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
            browser.close()
    finally:
        for p in procs:
            p.terminate()
            try:p.wait(timeout=15)
            except subprocess.TimeoutExpired:p.kill();p.wait()
        for log in logs:log.close()


if __name__=='__main__':main()
