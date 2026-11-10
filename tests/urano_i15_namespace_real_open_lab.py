"""Opt-in local namespace smoke: Linux mount+net namespaces, real pinned Engine.

Never use production owner folders; does not establish production-safe isolation.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import os
import uuid
from pathlib import Path

from urano.engine_bindings import EngineProjectRegistry
from urano.private_worker_supervisor import PrivateWorkerSupervisor
from urano.project_catalog import ProjectCatalog, ProjectNotFound
from urano.runtime_activation import RuntimeActivationGuard


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    engine = Path.home() / 'montara-owner-beta' / 'engine'
    launcher = repo / 'tests' / 'urano_i15_namespace_entry.sh'
    venv = Path.home() / 'montara-owner-beta' / '.venv'
    python_runtime = Path(sys.executable).resolve().parent.parent.parent
    pin = subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD:engine'],text=True).strip()
    actual = subprocess.check_output(['git','-C',str(engine),'rev-parse','HEAD'],text=True).strip()
    if actual != pin:
        raise RuntimeError('Pinned engine mismatch')
    sys.path.insert(0,str(engine))
    from core.project import new_project_document
    sys.path.pop(0)
    result = {'engine_sha':pin,'production_sandbox_certified':False,'companion_tested':False}
    with tempfile.TemporaryDirectory(prefix='montara-i15-workspace.',dir='/tmp') as fixture, \
         tempfile.TemporaryDirectory(prefix='montara-i15-lab.',dir='/tmp') as root, \
         tempfile.TemporaryDirectory(prefix='montara-i15-state.',dir='/tmp') as state, \
         tempfile.TemporaryDirectory(prefix='montara-i15-foreign.',dir='/tmp') as forbidden:
        workspace = Path(fixture)
        forbidden_file = Path(forbidden) / 'other-owner.txt'
        forbidden_file.write_text('SYNTHETIC-I15-OTHER-OWNER')
        # A second short-lived namespace receives this workspace but not
        # the other owner's fixture, host home or owner auth secrets.
        probed = subprocess.run(['unshare','--user','--map-root-user','--mount','--net','--',
                   str(launcher),'--probe',str(root),str(workspace),str(repo),str(engine),str(venv),str(python_runtime)],
                   capture_output=True,text=True,timeout=35,
                   env={**os.environ,'MONTARA_I15_FOREIGN_OWNER_TEST':str(forbidden_file),
                       'MONTARA_I15_HOST_HOME_TEST':str(Path.home()/'.config')})
        if probed.returncode:
            raise RuntimeError('Sandbox preflight did not complete: '+probed.stderr[-200:])
        reports=dict(line.split(' ',1) for line in probed.stdout.splitlines() if ' ' in line)
        required=('host_home_hidden','foreign_owner_hidden','real_engine_import','network_blocked','proc_not_mounted','engine_read_only')
        if any(reports.get(key)!='True' for key in required):
            raise AssertionError('Restricted filesystem / network probe failed')
        result.update({key:True for key in required})
        folder = workspace / 'Projects' / 'I15-real-engine'
        folder.mkdir(parents=True)
        (folder/'project.json').write_text(json.dumps(new_project_document('I15-real-engine')))
        catalog = ProjectCatalog(Path(state)/'catalog.sqlite3')
        registry = EngineProjectRegistry(Path(state)/'bindings.sqlite3', workspace, catalog)
        guard = RuntimeActivationGuard(Path(state)/'runtime.sqlite3',catalog,registry)
        owner = 'i15:lab-' + str(uuid.uuid4())
        project = catalog.create(owner,'Real Engine ephemeral isolation')
        foreign = catalog.create('i15:foreign','Private for somebody else')
        registry.bind_trusted(owner,project.id,'I15-real-engine')
        runtime = guard.register_trusted(owner)
        command = ['unshare','--user','--map-root-user','--mount','--net','--',
                   str(launcher),'--worker',str(root),str(workspace),str(repo),str(engine),str(venv),str(python_runtime)]
        supervisor = PrivateWorkerSupervisor(guard,owner,runtime,engine,workspace,
                     startup_timeout=110,open_timeout=100,command=command)
        started = time.monotonic()
        try:
            supervisor.start()
            result['handshake_seconds']=round(time.monotonic()-started,3)
            if not supervisor.process:
                raise AssertionError('Worker absent')
            pid=supervisor.process.pid
            for namespace in ('user','mnt','net'):
                child=os.readlink(f'/proc/{pid}/ns/{namespace}')
                parent=os.readlink(f'/proc/self/ns/{namespace}')
                if child==parent:
                    raise AssertionError('Worker did not receive dedicated namespace: '+namespace)
            result['dedicated_user_mount_network_namespaces']=True
            result['pid_namespace_isolated']=False
            # One sample of actual worker's resident memory; not a cgroup peak.
            memlines=Path(f'/proc/{pid}/status').read_text().splitlines()
            rss=[int(x.split()[1]) for x in memlines if x.startswith('VmRSS:')]
            if rss:result['worker_rss_one_sample_mib']=round(rss[0]/1024,2)
            try:
                supervisor.open_project(foreign.id)
            except ProjectNotFound:
                result['foreign_uuid_denied']=True
            else:
                raise AssertionError('Foreign project opened')
            opening=time.monotonic()
            ticket=supervisor.open_project(project.id)
            result['real_engine_open_seconds']=round(time.monotonic()-opening,3)
            assert ticket.project_id == project.id
            assert guard.get_state(owner,runtime)[0]=='ready'
            result['real_engine_open']=True
        finally:
            supervisor.stop()
        result['fully_reaped']=supervisor.process is None
        result['guard_idle']=guard.get_state(owner,runtime)[0]=='idle'
        result['elapsed_seconds']=round(time.monotonic()-started,3)
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__=='__main__': main()
