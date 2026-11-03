"""Cancellation stops only the requested local worker, including queued/racing starts."""
import concurrent.futures,importlib.util,json,subprocess,sys,threading,time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'companion'))
from video_jobs import VideoJobs


@pytest.fixture
def companion_server(tmp_path,monkeypatch):
    monkeypatch.setenv('MONTARA_COMPANION_HOME',str(tmp_path/'home'))
    spec=importlib.util.spec_from_file_location('cancel_companion_test',ROOT/'companion/companion.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    layout=tmp_path/'mixer';(layout/'venv/bin').mkdir(parents=True)
    (layout/'venv/bin/python').symlink_to(sys.executable)
    # Actual worker + separate-group descendant. No engine/DSP mocks can hide a
    # leaked child; Cancel must stop both and leave an unrelated process alone.
    (layout/'local_mix.py').write_text('''import json,subprocess,sys,time
child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(120)'],start_new_session=True)
open(sys.argv[3],'w').write(json.dumps({'status':'working','progress':0.2,'tracks':[],'child':child.pid}))
time.sleep(120)
''')
    original=tmp_path/'original.wav';original.write_bytes(b'original')
    monkeypatch.setattr(helper,'MIXER_HOME',layout)
    monkeypatch.setattr(helper,'CACHE',tmp_path/'cache')
    monkeypatch.setattr(helper,'local_mixer',lambda:{'mixer':'a'*40})
    monkeypatch.setattr(helper,'find_original',lambda _:original)
    server=helper.ThreadingHTTPServer(('127.0.0.1',0),helper.Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def request(path,body=None):
        data=json.dumps(body).encode() if body is not None else None
        with urlopen(Request(f'http://127.0.0.1:{server.server_port}'+path,data=data,headers={'Origin':'http://127.0.0.1:8101','Content-Type':'application/json'}),timeout=15) as response:return json.load(response)
    plan={'mixer':'a'*40,'tracks':[{'file':'original.wav','original':{'name':'original.wav','size':8,'fingerprint':'b'*64}}]}
    try:yield helper,request,plan
    finally:
        for job in helper.mix_jobs.values():
            if job.get('process'):helper.stop_process_tree(job['process'])
        server.shutdown();server.server_close();thread.join(5)


def test_cancel_before_mix_registration_never_launches(companion_server):
    helper,request,plan=companion_server;token='1'*32
    assert request(f'/mix-progress/{token}/cancel',{})['cancelled']
    with pytest.raises(HTTPError) as error:request('/mix-song',{'plan':plan,'progress_id':token})
    assert error.value.code==409
    assert 'process' not in helper.mix_jobs[token]
    assert request(f'/mix-progress/{token}')['status']=='cancelled'


def test_cancel_active_local_mix_stops_its_child_only(companion_server):
    helper,request,plan=companion_server;token='2'*32
    sentinel=subprocess.Popen([sys.executable,'-c','import time;time.sleep(120)'])
    try:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result=pool.submit(request,'/mix-song',{'plan':plan,'progress_id':token})
            snapshot={};deadline=time.monotonic()+10
            while 'child' not in snapshot and time.monotonic()<deadline:
                try:snapshot=request(f'/mix-progress/{token}')
                except HTTPError:pass
                time.sleep(.03)
            assert 'child' in snapshot
            worker=helper.mix_jobs[token]['process']
            assert request(f'/mix-progress/{token}/cancel',{})['cancelled']
            assert worker.poll() is not None and sentinel.poll() is None
            state=subprocess.run(['ps','-o','stat=','-p',str(snapshot['child'])],capture_output=True,text=True).stdout.strip()
            assert not state or state.startswith('Z')
            with pytest.raises(HTTPError) as error:result.result(timeout=5)
            assert error.value.code==409
        assert request(f'/mix-progress/{token}')['status']=='cancelled'
        assert not list(helper.CACHE.glob('mix-*'))
    finally:sentinel.terminate();sentinel.wait(timeout=5)


def test_cancel_queued_video_cannot_launch(tmp_path,monkeypatch):
    manager=VideoJobs(tmp_path)
    manager.jobs['job']={'status':'queued'}
    assert manager.cancel('job')
    manager._run('job')  # would access work/runtime if it tried to launch
    assert manager.status('job')['status']=='cancelled'


def test_cancel_queued_mix_never_starts_when_slot_opens(companion_server):
    helper,request,plan=companion_server;token='3'*32
    helper.MIX_SLOTS.acquire()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        try:
            result=pool.submit(request,'/mix-song',{'plan':plan,'progress_id':token})
            deadline=time.monotonic()+10
            while token not in helper.mix_jobs and time.monotonic()<deadline:time.sleep(.02)
            assert token in helper.mix_jobs
            assert request(f'/mix-progress/{token}/cancel',{})['cancelled']
            assert 'process' not in helper.mix_jobs[token]
        finally:helper.MIX_SLOTS.release()
        with pytest.raises(HTTPError) as error:result.result(timeout=5)
        assert error.value.code==409
    assert 'process' not in helper.mix_jobs[token]
