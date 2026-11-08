#!/usr/bin/env python3
"""One invocation updates JM and its Companion to one release, then opens Montara.

Run: curl -fsSL https://raw.githubusercontent.com/amehcgracia-byte/Montara/main/deploy/vm/launch.py | python3
Never operates on FER or modifies project/media files.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.request import Request, urlopen

REPOSITORY = 'amehcgracia-byte/Montara'
VM = ['montara-test', '--zone', 'europe-west3-a', '--project', 'montara-pruebas-10292226']
URL = 'http://127.0.0.1:8101'


def execute(args, **kwargs):
    kwargs.setdefault('check', True)
    return subprocess.run(args, text=True, **kwargs)


def fetch(url):
    with urlopen(Request(url, headers={'User-Agent': 'Montara-launcher'}), timeout=45) as response:
        return response.read()


def companion_idle(run=execute):
    listeners = run(['lsof', '-t', '-iTCP:47820', '-sTCP:LISTEN'], capture_output=True, check=False)
    if listeners.returncode not in (0,1):raise RuntimeError('Cannot check Companion activity. No update was made.')
    for pid in listeners.stdout.split():
        if not pid.isdigit():raise RuntimeError('Cannot identify Companion. No update was made.')
        command=run(['ps','-p',pid,'-o','command='],capture_output=True).stdout
        if str(Path.home()/'.montara-companion/companion.py') not in command:
            raise RuntimeError('Port 47820 belongs to another application. No update was made.')
        children = run(['pgrep', '-P', pid], capture_output=True, check=False)
        if children.returncode not in (0,1):raise RuntimeError('Cannot check Companion activity. No update was made.')
        if children.stdout.strip():
            raise RuntimeError('Companion is working. Wait for it to finish and run this command again.')


def health(download=fetch):
    return json.loads(download('http://127.0.0.1:47820/health'))


def launch(run=execute, download=fetch, sleep=time.sleep):
    start=Path.home()/'.montara-tools/bin/montara-start'
    if not start.is_file():
        raise RuntimeError('Install the Montara Mac connection tools first. No update was made.')
    release = json.loads(download(f'https://api.github.com/repos/{REPOSITORY}/commits/main'))['sha']
    if not isinstance(release, str) or not re.fullmatch('[a-f0-9]{40}', release):
        raise RuntimeError('Cannot identify the Montara release. No update was made.')
    marker=Path.home()/'.montara-companion/APP_RELEASE.json'
    local_current=False
    try:
        installed=json.loads(marker.read_text());local=health(download)
        local_current=(isinstance(installed,dict) and installed.get('montara')==release
            and (local.get('local_video') or {}).get('engine')==installed.get('engine')
            and (local.get('local_mix') or {}).get('mixer')==installed.get('mixer'))
    except (OSError,ValueError):pass
    if not local_current:companion_idle(run)
    base = f'https://raw.githubusercontent.com/{REPOSITORY}/{release}'
    # Capture the exact helper before changing either installation.
    remote = download(base+'/deploy/vm/update_jm.py').decode()
    installer = download(base+'/companion/install.sh')
    state = run(['gcloud', 'compute', 'instances', 'describe', *VM, '--format=value(status)'], capture_output=True).stdout.strip()
    if state != 'RUNNING':
        print('Starting Montara…', flush=True)
        run(['gcloud', 'compute', 'instances', 'start', *VM, '--quiet'])
        for _ in range(30):
            probe=run(['gcloud','compute','ssh',*VM,'--quiet','--command','true',
                       '--ssh-flag=-oConnectTimeout=10','--ssh-flag=-oConnectionAttempts=1'],capture_output=True,check=False)
            if probe.returncode==0:break
            sleep(3)
        else:raise RuntimeError('Montara has not started accepting connections. Retry in a moment.')
    print('Updating Montara; existing projects are retained…', flush=True)
    try:
        deployed = run(['gcloud', 'compute', 'ssh', *VM, '--quiet', '--command',
            f'sudo -u jm -H python3 - {release}'], input=remote, capture_output=True)
    except subprocess.CalledProcessError as error:
        try:message=json.loads((error.stdout or '').splitlines()[-1])['error']
        except (ValueError,IndexError,KeyError,TypeError):message='Server update stopped. Companion was not changed.'
        raise RuntimeError(str(message)[:250]) from None
    # The helper emits one final structured line after all checks pass.
    try: pins = json.loads(deployed.stdout.splitlines()[-1])
    except (ValueError, IndexError):raise RuntimeError('Server update did not confirm its release. Companion was not changed.') from None
    if not isinstance(pins,dict) or pins.get('montara') != release or any(not re.fullmatch('[a-f0-9]{40}', str(pins.get(k,''))) for k in ('engine','mixer')):
        raise RuntimeError('Server release verification failed. Companion was not changed.')
    if not local_current:
        companion_idle(run)
        print('Updating Companion to the same release…', flush=True)
        with tempfile.TemporaryDirectory(prefix='montara-launch-') as temporary:
            script=Path(temporary)/'install.sh';script.write_bytes(installer)
            env={**os.environ,'MONTARA_REF':release,'MONTARA_VIDEO':'1','MONTARA_MIXER':'1',
                 'MONTARA_BACKGROUND':'1','MONTARA_NO_SHELL_SETUP':'1'}
            run(['bash', str(script)], env=env)
    for _ in range(30):
        try:
            local=health(download)
            if ((local.get('local_video') or {}).get('engine')==pins['engine']
                and (local.get('local_mix') or {}).get('mixer')==pins['mixer']):break
        except (OSError, ValueError):pass
        sleep(1)
    else:raise RuntimeError('Companion has not confirmed the server versions. Montara was not opened; run this command again to retry.')
    marker.parent.mkdir(parents=True,exist_ok=True)
    pending=marker.with_suffix('.tmp');pending.write_text(json.dumps(pins));pending.replace(marker)
    print('Montara and Companion are up to date. Opening Montara…', flush=True)
    # Existing start command reuses an open tunnel and reconnects dropped tunnels.
    run([str(start)])
    return pins


def main():
    try:launch()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        # Never echo SSH output, command environments or private server settings.
        message=str(error) if isinstance(error, RuntimeError) else 'The update stopped. Check your connection and run this command again.'
        print('Montara: '+message, flush=True)
        return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
