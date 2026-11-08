"""Run only as jm via the unified Mac launcher; no FER/service/media changes."""
import base64
import getpass
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
from urllib.request import Request,urlopen


def run(args, **kwargs):return subprocess.run(args,check=True,text=True,**kwargs)


def update(release):
    if getpass.getuser()!='jm' or not re.fullmatch('[a-f0-9]{40}',release):raise RuntimeError('Use the JM installation and a full release identity.')
    root=Path.home()/'montara';settings=Path.home()/'.config/montara/env'
    if not settings.is_file():raise RuntimeError('JM is not configured. No update was made.')
    config={}
    for line in settings.read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            k,v=line.split('=',1);values=shlex.split(v);config[k]=' '.join(values)
    login=config.get('MONTARA_PREVIEW_USER','montara')+':'+config['MONTARA_PREVIEW_PASSWORD']
    auth='Basic '+base64.b64encode(login.encode()).decode()
    def request(path):
        with urlopen(Request('http://127.0.0.1:8101'+path,headers={'Authorization':auth}),timeout=15) as response:return json.load(response)
    def pins():
        result={'montara':run(['git','-C',str(root),'rev-parse','HEAD'],capture_output=True).stdout.strip()}
        for name in ('engine','mixer'):result[name]=run(['git','-C',str(root/name),'rev-parse','HEAD'],capture_output=True).stdout.strip()
        return result
    current=pins()
    if current['montara']==release and not run(['git','-C',str(root),'status','--porcelain'],capture_output=True).stdout.strip():
        try:
            if release[:7] in request('/montara/version').get('version',''):return current
        except OSError:pass
    status=request('/api/v1/wizard/status').get('status')
    if not isinstance(status,str):raise RuntimeError('Cannot confirm whether Montara is idle. No update was made.')
    if status in {'running','cancelling'}:raise RuntimeError('Montara is working. Retry after it finishes.')
    # Background session/mastering jobs are not all part of the wizard.
    data=Path(config.get('MONTARA_DATA',str(Path.home()/'montara-data')))
    if not data.resolve().is_relative_to(Path.home().resolve()):raise RuntimeError('JM data must belong to the JM account. No update was made.')
    for pattern in ('Sessions/*/session.json','Mastering/*/job.json'):
        for path in data.glob(pattern):
            value=json.loads(path.read_text())
            if value.get('status') in {'queued','running','analyzing','detecting','mixing','rendering','exporting','preparing'}:
                raise RuntimeError('A session or mastering job is active. Retry after it finishes.')
    processes=run(['ps','-u',str(os.getuid()),'-o','args='],capture_output=True).stdout.splitlines()
    for command in processes:
        if re.search(r'(?:^|/|\s)(?:ffmpeg|ffprobe)(?:\s|$)|mixer_adapter[/.](?:session|single_song)|local_mix\.py',command):
            raise RuntimeError('Montara media processing is active. Retry after it finishes.')
    if run(['git','-C',str(root),'status','--porcelain'],capture_output=True).stdout.strip():raise RuntimeError('JM checkout has local changes. Nothing was overwritten.')
    run(['git','-C',str(root),'fetch','--no-recurse-submodules','origin',release])
    # No forced checkout, clean, reset, data migration or project reconstruction.
    run(['git','-C',str(root),'checkout','--detach',release])
    run(['git','-C',str(root),'submodule','update','--init','--recursive'])
    env={**os.environ,'MONTARA_OFFLINE':'1'}
    run(['bash','deploy/vm/user_install.sh',release,'8101'],cwd=root,env=env)
    for _ in range(45):
        try:
            if release[:7] in request('/montara/version').get('version',''):break
        except OSError:pass
        time.sleep(1)
    else:raise RuntimeError('JM did not confirm the updated web version.')
    return pins()


if __name__=='__main__':
    try:print(json.dumps(update(sys.argv[1])))
    except Exception as error:
        message=str(error) if isinstance(error,RuntimeError) else 'JM update stopped. Companion was not changed.'
        print(json.dumps({'error':message}))
        raise SystemExit(1)
