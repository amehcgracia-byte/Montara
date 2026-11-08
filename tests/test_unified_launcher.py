"""Launcher acceptance with simulated cloud/installer boundaries, never the lab VM."""
import importlib.util
import json
from pathlib import Path
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('launch_montara',ROOT/'deploy/vm/launch.py')
launch=importlib.util.module_from_spec(spec);spec.loader.exec_module(launch)
SHA='a'*40;ENGINE='b'*40;MIXER='c'*40


@pytest.fixture
def scenario(tmp_path,monkeypatch):
    monkeypatch.setenv('HOME',str(tmp_path))
    start=tmp_path/'.montara-tools/bin/montara-start';start.parent.mkdir(parents=True);start.touch()
    state={'vm':'TERMINATED','busy':False,'server_failure':False,'installer_failure':False,'mismatch':False,'calls':[],'downloads':[],'installed':False}
    def download(url):
        state['downloads'].append(url)
        if url.endswith('/commits/main'):return json.dumps({'sha':SHA}).encode()
        if url.endswith('/health'):
            assert state['installed']
            return json.dumps({'local_video':{'engine':'d'*40 if state['mismatch'] else ENGINE},'local_mix':{'mixer':MIXER}}).encode()
        assert '/'+SHA+'/' in url # Code and installer use the same immutable release.
        return b'# reviewed release code'
    def run(args,**kwargs):
        state['calls'].append((args,kwargs))
        out='';code=0
        if args[0]=='lsof':out='123\n'
        elif args[0]=='ps':out='python3 '+str(tmp_path/'.montara-companion/companion.py')
        elif args[0]=='pgrep':out='456\n' if state['busy'] else ''
        elif args[:4]==['gcloud','compute','instances','describe']:out=state['vm']
        elif args[:3]==['gcloud','compute','ssh'] and kwargs.get('input'):
            if state['server_failure']:
                raise subprocess.CalledProcessError(1,args,output=json.dumps({'error':'Montara is working. Retry after it finishes.'}))
            out=json.dumps({'montara':SHA,'engine':ENGINE,'mixer':MIXER})
        elif args[0]=='bash':
            assert kwargs['env']['MONTARA_REF']==SHA
            assert kwargs['env']['MONTARA_VIDEO']==kwargs['env']['MONTARA_MIXER']=='1'
            assert kwargs['env']['MONTARA_BACKGROUND']==kwargs['env']['MONTARA_NO_SHELL_SETUP']=='1'
            if state['installer_failure']:raise subprocess.CalledProcessError(1,args)
            state['installed']=True
        return subprocess.CompletedProcess(args,code,out,'')
    return state,run,download


def test_one_command_starts_updates_both_checks_versions_then_opens(scenario):
    state,run,download=scenario
    assert launch.launch(run,download,lambda _:None)=={'montara':SHA,'engine':ENGINE,'mixer':MIXER}
    calls=[args for args,_ in state['calls']]
    cloud=next(args for args in calls if '--command' in args and 'sudo -u jm' in args[args.index('--command')+1])
    assert cloud[cloud.index('--command')+1]==f'sudo -u jm -H python3 - {SHA}'
    assert calls[-1][0].endswith('/montara-start')
    assert any(args[:4]==['gcloud','compute','instances','start'] for args in calls)
    assert all('8102' not in str(args) and 'fernando' not in str(args) for args in calls)


def test_busy_companion_prevents_even_cloud_start(scenario):
    state,run,download=scenario;state['busy']=True
    with pytest.raises(RuntimeError,match='Companion is working'):launch.launch(run,download,lambda _:None)
    assert not any(args[0]=='gcloud' for args,_ in state['calls'])


def test_busy_server_does_not_update_companion_or_open(scenario):
    state,run,download=scenario;state['server_failure']=True
    with pytest.raises(RuntimeError,match='Montara is working'):launch.launch(run,download,lambda _:None)
    assert not state['installed']
    assert not any(args[0]=='bash' or args[0].endswith('/montara-start') for args,_ in state['calls'])


def test_installer_failure_cannot_open_mismatched_app(scenario):
    state,run,download=scenario;state['installer_failure']=True
    with pytest.raises(subprocess.CalledProcessError):launch.launch(run,download,lambda _:None)
    assert not any(args[0].endswith('/montara-start') for args,_ in state['calls'])


def test_version_mismatch_never_opens_browser(scenario):
    state,run,download=scenario;state['mismatch']=True
    with pytest.raises(RuntimeError,match='has not confirmed'):launch.launch(run,download,lambda _:None)
    assert not any(args[0].endswith('/montara-start') for args,_ in state['calls'])


def test_running_vm_is_not_restarted(scenario):
    state,run,download=scenario;state['vm']='RUNNING'
    launch.launch(run,download,lambda _:None)
    assert not any(args[:4]==['gcloud','compute','instances','start'] for args,_ in state['calls'])


@pytest.mark.parametrize('already_current',[False,True])
def test_server_update_is_confined_to_jm_and_preserves_data(tmp_path,monkeypatch,already_current):
    import io
    spec=importlib.util.spec_from_file_location('update_jm',ROOT/'deploy/vm/update_jm.py')
    remote=importlib.util.module_from_spec(spec);spec.loader.exec_module(remote)
    monkeypatch.setattr(remote.getpass,'getuser',lambda:'jm');monkeypatch.setattr(remote.Path,'home',lambda:tmp_path)
    conf=tmp_path/'.config/montara/env';conf.parent.mkdir(parents=True)
    conf.write_text('MONTARA_PREVIEW_PASSWORD=test-only\nMONTARA_PREVIEW_USER=montara\n')
    media=tmp_path/'montara-data/keep.mp4';media.parent.mkdir();media.write_bytes(b'unchanged original')
    calls=[];updated=[already_current]
    warming=[not already_current]
    def request(req,timeout):
        if req.full_url.endswith('/status') and warming[0]:
            from urllib.error import URLError
            warming[0]=False
            raise URLError('Server is starting')
        value={'status':'done'} if req.full_url.endswith('/status') else {'version':'Montara '+SHA[:7]}
        return io.BytesIO(json.dumps(value).encode())
    monkeypatch.setattr(remote,'urlopen',request)
    monkeypatch.setattr(remote.time,'sleep',lambda _:None)
    def command(args,**kwargs):
        calls.append((args,kwargs));out=''
        if args[-2:]==['rev-parse','HEAD']:
            out=ENGINE if args[2].endswith('/engine') else MIXER if args[2].endswith('/mixer') else SHA if updated[0] else 'd'*40
        if args[:2]==['bash','deploy/vm/user_install.sh']:updated[0]=True
        return subprocess.CompletedProcess(args,0,out,'')
    monkeypatch.setattr(remote,'run',command)
    assert remote.update(SHA)=={'montara':SHA,'engine':ENGINE,'mixer':MIXER}
    assert media.read_bytes()==b'unchanged original'
    assert not any('-f' in args or 'reset' in args or 'clean' in args for args,_ in calls)
    installs=[(args,kwargs) for args,kwargs in calls if args[:2]==['bash','deploy/vm/user_install.sh']]
    if already_current:assert not installs
    else:assert installs[0][0][-1]=='8101' and installs[0][1]['env']['MONTARA_OFFLINE']=='1'
    monkeypatch.setattr(remote.getpass,'getuser',lambda:'fer')
    calls.clear()
    with pytest.raises(RuntimeError,match='JM installation'):remote.update(SHA)
    assert not calls


def test_server_busy_guard_prevents_git_and_restart(tmp_path,monkeypatch):
    import io
    spec=importlib.util.spec_from_file_location('update_jm_busy',ROOT/'deploy/vm/update_jm.py')
    remote=importlib.util.module_from_spec(spec);spec.loader.exec_module(remote)
    monkeypatch.setattr(remote.getpass,'getuser',lambda:'jm');monkeypatch.setattr(remote.Path,'home',lambda:tmp_path)
    conf=tmp_path/'.config/montara/env';conf.parent.mkdir(parents=True);conf.write_text('MONTARA_PREVIEW_PASSWORD=test-only\n')
    monkeypatch.setattr(remote,'urlopen',lambda *a,**kw:io.BytesIO(b'{"status":"running"}'))
    def read_only(args,**kw):
        assert args[-2:]==['rev-parse','HEAD'],'An active render must not invoke Git changes or restart'
        return subprocess.CompletedProcess(args,0,'d'*40,'')
    monkeypatch.setattr(remote,'run',read_only)
    with pytest.raises(RuntimeError,match='Montara is working'):remote.update(SHA)


def test_already_current_companion_is_not_reinstalled_or_stopped(scenario,tmp_path):
    state,run,download=scenario;state.update(installed=True,busy=True,vm='RUNNING')
    marker=tmp_path/'.montara-companion/APP_RELEASE.json';marker.parent.mkdir()
    marker.write_text(json.dumps({'montara':SHA,'engine':ENGINE,'mixer':MIXER}))
    launch.launch(run,download,lambda _:None)
    assert not any(args[0] in {'lsof','pgrep','bash'} for args,_ in state['calls'])
    assert state['calls'][-1][0][0].endswith('/montara-start')


@pytest.mark.parametrize('kind',['session','mastering','process','dirty'])
def test_server_guard_does_not_replace_active_or_modified_installation(tmp_path,monkeypatch,kind):
    import io
    spec=importlib.util.spec_from_file_location('update_jm_guard',ROOT/'deploy/vm/update_jm.py')
    remote=importlib.util.module_from_spec(spec);spec.loader.exec_module(remote)
    monkeypatch.setattr(remote.getpass,'getuser',lambda:'jm');monkeypatch.setattr(remote.Path,'home',lambda:tmp_path)
    conf=tmp_path/'.config/montara/env';conf.parent.mkdir(parents=True);conf.write_text('MONTARA_PREVIEW_PASSWORD=test-only\n')
    if kind in {'session','mastering'}:
        folder=tmp_path/'montara-data'/('Sessions' if kind=='session' else 'Mastering')/'test';folder.mkdir(parents=True)
        (folder/('session.json' if kind=='session' else 'job.json')).write_text('{"status":"rendering"}' if kind=='session' else '{"status":"running"}')
    monkeypatch.setattr(remote,'urlopen',lambda *a,**kw:io.BytesIO(b'{"status":"done"}'))
    def read_only(args,**kw):
        if args[0]=='ps':out='ffmpeg -i source.mp4' if kind=='process' else 'gunicorn deploy.entry:app'
        elif args[-2:]==['rev-parse','HEAD']:out='d'*40
        elif args[-2:]==['status','--porcelain']:out=' M app.py'
        else:pytest.fail('Busy or dirty installation must not be changed')
        return subprocess.CompletedProcess(args,0,out,'')
    monkeypatch.setattr(remote,'run',read_only)
    with pytest.raises(RuntimeError):remote.update(SHA)
