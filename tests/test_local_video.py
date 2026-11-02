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
    subprocess.run([ff,'-v','error','-y','-f','lavfi','-i','testsrc2=size=1920x1080:rate=30:duration=4','-c:v','libx264','-crf','15','-threads','2',str(source)],check=True)
    folder=tmp_path/'chosen-project';folder.mkdir()
    master=folder/f'montara-render-audio-{uuid.uuid4().hex}.audio'
    subprocess.run([ff,'-v','error','-y','-f','lavfi','-i','sine=duration=4','-f','wav',str(master)],check=True)
    project='b'*16;manager=VideoJobs(home)
    original={'name':source.name,'size':source.stat().st_size,'fingerprint':fingerprint(source)}
    payload={'project':project,'master':master.name,'recipe':recipe(sha),'originals':[{'source':0,'original':original}],'branding':'none'}
    token=manager.start(payload,{project:folder},lambda _:source)
    deadline=time.monotonic()+180
    while manager.status(token)['status'] not in ('ready','failed') and time.monotonic()<deadline:time.sleep(.2)
    status=manager.status(token)
    assert status['status']=='ready',(status,(folder/'.montara-renders'/token/'render.log').read_text()[-5000:])
    output=manager.output(token)
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(output)]))
    stream=next(s for s in info['streams'] if s['codec_type']=='video')
    assert (stream['width'],stream['height'])==(1920,1080)
    def frame(path,filter_='null'):
        raw=subprocess.check_output([ff,'-v','error','-ss','2.0','-i',str(path),'-frames:v','1','-vf',filter_,'-pix_fmt','gray','-f','rawvideo','-'])
        return np.frombuffer(raw,np.uint8).astype(float)
    original_pixels=frame(source);final=frame(output)
    proxy=frame(source,'scale=1280:720,scale=1920:1080')
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
    helper.video_jobs.jobs[token]={'status':'ready','progress':1,'path':video}
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
    finally:server.shutdown();server.server_close();thread.join(timeout=3)
