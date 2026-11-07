"""Local final export uses native pixels, not a renamed/upscaled edit proxy."""
import hashlib,json,os,shutil,subprocess,sys,time,uuid
from pathlib import Path
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'companion'))
from video_recipe import validate
from video_jobs import VideoJobs


def install_layout(home, engine=None):
    target=home/'video';target.mkdir(parents=True)
    for name in ('local_video.py','video_recipe.py'):shutil.copy2(ROOT/'companion'/name,target/name)
    engine=Path(engine or ROOT/'engine')
    # Tests need only renderer code/assets, not datasets or generated builds.
    shutil.copytree(engine/'core',target/'engine/core',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(engine/'server',target/'engine/server',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(engine/'assets/fonts',target/'engine/assets/fonts')
    shutil.copytree(ROOT/'web/brand',target/'brand')
    (target/'venv').symlink_to(Path(sys.prefix))
    sha=subprocess.check_output(['git','-C',str(engine),'rev-parse','HEAD'],text=True).strip()
    (target/'ENGINE_COMMIT').write_text(sha)
    return target,sha


def fingerprint(path):
    data=path.read_bytes();return hashlib.sha256(data[:65536]+data[-65536:]).hexdigest()


def recipe(sha):
    return {'version':1,'engine':sha,'platform':'youtube','sources':[{'key':0,'path':'server-proxy.small.mp4'}],
            'segments':[{'source':0,'clip_start_sec':0,'duration_sec':4,'master_start_sec':0,'video_light':{'auto':False,'light':0,'shadows':0}}]}


@pytest.mark.parametrize('change',[{'platform':'show'},{'engine':'x'},{'segments':[]},{'segments':[{'source':0,'clip_start_sec':float('nan'),'duration_sec':1,'master_start_sec':0}]},{'segments':[{'source':0,'duration_sec':1,'master_start_sec':0,'motion':{'filter':'movie=/etc/passwd'}}]}])
def test_recipe_rejects_invalid_or_executable_fields(change):
    with pytest.raises(ValueError):validate({**recipe('a'*40),**change})


def test_real_local_final_preserves_native_resolution_and_detail(tmp_path,monkeypatch):
    home=tmp_path/'companion';target,sha=install_layout(home,os.environ.get('MONTARA_TEST_EDITOR'))
    ff='ffmpeg';source=tmp_path/'camera-original.mp4'
    subprocess.run([ff,'-v','error','-y','-f','lavfi','-i','testsrc2=size=1920x1080:rate=30:duration=4','-c:v','libx264','-crf','15','-threads','2','-colorspace','bt709','-color_trc','bt709','-color_primaries','bt709','-color_range','tv',str(source)],check=True)
    folder=tmp_path/'chosen-project';folder.mkdir()
    master=folder/f'montara-render-audio-{uuid.uuid4().hex}.audio'
    subprocess.run([ff,'-v','error','-y','-f','lavfi','-i','sine=duration=4','-f','wav',str(master)],check=True)
    project='b'*16;manager=VideoJobs(home)
    original={'name':source.name,'size':source.stat().st_size,'fingerprint':fingerprint(source)}
    payload={'project':project,'master':master.name,'recipe':recipe(sha),'originals':[{'source':0,'original':original}],'branding':'none','name':'Montara.Notetaker'}
    token=manager.start(payload,{project:folder},lambda _:source)
    deadline=time.monotonic()+180
    while manager.status(token)['status'] not in ('ready','failed') and time.monotonic()<deadline:time.sleep(.2)
    status=manager.status(token)
    assert status['status']=='ready',(status,(folder/'.montara-renders'/token/'render.log').read_text()[-5000:])
    output=manager.output(token)
    assert output.name=='Montara.Notetaker.mp4'
    assert manager.jobs[token]['download_name']=='Montara.Notetaker.mp4'
    assert manager.status(token)['tasks'][0]['label']=='Shot 1/1'
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(output)]))
    stream=next(s for s in info['streams'] if s['codec_type']=='video')
    assert (stream['width'],stream['height'])==(1920,1080)
    def frame(path,filter_='null'):
        raw=subprocess.check_output([ff,'-v','error','-ss','2.0','-i',str(path),'-frames:v','1','-vf',filter_,'-pix_fmt','gray','-f','rawvideo','-'])
        return np.frombuffer(raw,np.uint8).astype(float)
    # Fair A/B: run an actual encoded 720p companion copy through the same
    # final exporter. Comparing a multiply encoded final with an unencoded
    # resize penalizes compression rather than testing the original relink.
    import importlib.util
    module=importlib.util.spec_from_file_location('quality_proxy_helper',ROOT/'companion/companion.py')
    helper=importlib.util.module_from_spec(module);module.loader.exec_module(helper)
    helper.HW_H264=False
    proxy_source=tmp_path/'camera-copy.small.mp4'
    subprocess.run(helper.proxy_command(source,proxy_source,helper.plan(helper.probe(source))),check=True,capture_output=True)
    proxy_identity={'name':proxy_source.name,'size':proxy_source.stat().st_size,'fingerprint':fingerprint(proxy_source)}
    proxy_token=manager.start({**payload,'originals':[{'source':0,'original':proxy_identity}]},{project:folder},lambda _:proxy_source)
    deadline=time.monotonic()+180
    while manager.status(proxy_token)['status'] not in ('ready','failed') and time.monotonic()<deadline:time.sleep(.2)
    assert manager.status(proxy_token)['status']=='ready',manager.status(proxy_token)
    original_pixels=frame(source);final=frame(output);proxy=frame(manager.output(proxy_token))
    assert np.mean((final-original_pixels)**2)<np.mean((proxy-original_pixels)**2)
    manifest=json.loads((folder/'.montara-renders'/token/'render.json').read_text())
    assert manifest['source_files']['0']==str(source.resolve())
    assert source.is_file()  # The camera file is never replaced by an export.
    wrong={**payload,'recipe':{**payload['recipe'],'engine':'c'*40}}
    with pytest.raises(ValueError,match='editor version'):manager.start(wrong,{project:folder},lambda _:source)
    altered={**payload,'originals':[{'source':0,'original':{**original,'fingerprint':'0'*64}}]}
    with pytest.raises(ValueError,match='changed'):manager.start(altered,{project:folder},lambda _:source)


def test_native_http_ranges_and_origin_boundaries(tmp_path,monkeypatch):
    import importlib.util,threading
    from http.server import ThreadingHTTPServer
    from urllib.request import Request,urlopen
    from urllib.error import HTTPError
    monkeypatch.setenv('MONTARA_COMPANION_HOME',str(tmp_path/'home'))
    spec=importlib.util.spec_from_file_location('native_http_test',ROOT/'companion/companion.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    token='a'*32;video=tmp_path/'final.mp4';video.write_bytes(b'0123456789')
    helper.video_jobs.jobs[token]={'status':'ready','progress':1,'path':video,'download_name':'Montara.Notetaker.mp4'}
    server=ThreadingHTTPServer(('127.0.0.1',0),helper.Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url=f'http://127.0.0.1:{server.server_port}/video-renders/{token}/file'
    try:
        with urlopen(Request(url,headers={'Origin':'http://127.0.0.1:8101','Range':'bytes=2-5'})) as r:
            assert r.status==206 and r.read()==b'2345'
            assert r.headers['Content-Range']=='bytes 2-5/10'
        with pytest.raises(HTTPError) as denied:urlopen(Request(url,headers={'Origin':'https://unrelated.example'}))
        assert denied.value.code==403
        with pytest.raises(HTTPError) as invalid:urlopen(Request(url,headers={'Origin':'http://localhost:8101','Range':'bytes=20-30'}))
        assert invalid.value.code==416
        # A browser download navigation has no Origin; only an unguessable ready
        # job's exact download URL is a capability, never a filesystem path.
        with urlopen(url+'?download=1') as r:
            assert r.read()==b'0123456789' and 'attachment' in r.headers['Content-Disposition']
            assert r.headers['Content-Disposition'].endswith('Montara.Notetaker.mp4')
    finally:server.shutdown();server.server_close();thread.join(timeout=3)


def test_personal_transparent_logo_gets_separate_fading_bookends(tmp_path):
    from PIL import Image
    home=tmp_path/'companion';target,sha=install_layout(home)
    folder=tmp_path/'project';folder.mkdir()
    source=folder/f'montara-render-source-{uuid.uuid4().hex}.mp4'
    master=folder/f'montara-render-audio-{uuid.uuid4().hex}.audio'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=blue:s=320x180:r=30:d=4','-c:v','libx264',str(source)],check=True)
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=duration=4','-f','wav',str(master)],check=True)
    logo=folder/f'montara-render-logo-{uuid.uuid4().hex}.png'
    image=Image.new('RGBA',(64,64),(0,0,0,0));image.paste((255,0,0,255),(16,16,48,48));image.save(logo)
    manager=VideoJobs(home);project='a'*16
    body={'project':project,'master':master.name,'recipe':recipe(sha),'originals':[{'source':0,'asset':source.name}],'branding':'mine','logo':logo.name,'name':'Personal'}
    with pytest.raises(ValueError):manager.start({**body,'logo':'../private.png'},{project:folder},lambda _:None)
    token=manager.start(body,{project:folder},lambda _:None)
    deadline=time.monotonic()+180
    while manager.status(token)['status'] not in ('ready','failed') and time.monotonic()<deadline:time.sleep(.2)
    assert manager.status(token)['status']=='ready',(manager.status(token),(folder/'.montara-renders'/token/'render.log').read_text()[-2000:])
    output=manager.output(token)
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(output)]))
    assert abs(float(info['format']['duration'])-(4+10.0+10.2))<.12
    reopened=VideoJobs(home)
    assert reopened.status(token)['status']=='ready' and reopened.output(token)==output
    def frame_at(second):
        raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(second),'-i',str(output),'-frames:v','1','-vf','scale=192:108','-f','rawvideo','-pix_fmt','rgb24','-'])
        return np.frombuffer(raw,np.uint8).reshape(108,192,3)
    assert frame_at(.1).mean()<16  # starts from black
    assert frame_at(5.0)[54,96,0]>110  # transparent red logo on black
    assert frame_at(12.0)[10,10,2]>100  # original blue camera video
    assert frame_at(24.05).mean()<16  # fades back to black


def test_native_recipe_accepts_deep_flat_crop_but_keeps_motion_limits():
    data=recipe('a'*40)
    data['segments'][0]['flat_framing']={'zoom':5.4,'x':.3,'y':.4}
    validate(data)
    data['segments'][0]['flat_framing']['zoom']=6.1
    with pytest.raises(ValueError):validate(data)
    data['segments'][0]['flat_framing']['zoom']=5.4
    data['segments'][0]['motion']={'type':'ken_burns','zoom_start':5.4}
    with pytest.raises(ValueError):validate(data)


@pytest.mark.parametrize('speed',[0.5,1.0,1.5,2.0])
def test_native_recipe_keeps_independent_shot_speed(speed):
    data=recipe('a'*40)
    data['segments'][0]['playback_speed']=speed
    checked=validate(data)
    assert checked['segments'][0]['playback_speed']==speed
    assert checked['segments'][0]['duration_sec']==4.0


@pytest.mark.parametrize('invalid',[0,0.49,2.01,float('nan'),'setpts=2',True])
def test_native_recipe_rejects_invalid_speed(invalid):
    data=recipe('a'*40)
    data['segments'][0]['playback_speed']=invalid
    with pytest.raises(ValueError):validate(data)
