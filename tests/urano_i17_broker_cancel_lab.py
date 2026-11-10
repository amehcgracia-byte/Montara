"""Operator-only I17 proof: independent controller survives worker cgroup STOP.

This is NOT a production broker or public HTTP interface. Data is synthetic,
units have an I17-only prefix, and the controller is a separate transient
systemd user service (not in the Engine service's cgroup).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import select
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

PREFIX="montara-i17-target-"
NAME=re.compile(r"montara-i17-target-[0-9a-f]{12}\Z")


def command(*args, timeout=10, check=True):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=check)


def unit_status(unit):
    if not NAME.fullmatch(unit):
        raise ValueError('Refuse non-I17 target')
    result=command('systemctl','--user','show',unit+'.service',
                   '-p','ActiveState','-p','ControlGroup','-p','MemoryMax',
                   '-p','TasksMax','-p','CPUQuotaPerSecUSec','-p','MemoryPeak',
                   timeout=7,check=False)
    return dict(l.split('=',1) for l in result.stdout.splitlines() if '=' in l)


def target_stop(unit):
    if not NAME.fullmatch(unit):
        raise ValueError('Refuse non-I17 target')
    return command('systemctl','--user','stop','--no-block',unit+'.service',timeout=6,check=False)


def cgroup_pids(group):
    if not isinstance(group,str) or not re.fullmatch(
        r'/user\.slice/user-[0-9]+\.slice/user@[0-9]+\.service/app\.slice/montara-i17-target-[0-9a-f]{12}\.service',group):
        raise ValueError('Unexpected cgroup')
    p=Path('/sys/fs/cgroup') / group.lstrip('/') / 'cgroup.procs'
    try:return tuple(int(s) for s in p.read_text().split())
    except FileNotFoundError:return ()


def packet(process, timeout):
    ready,_,_=select.select([process.stdout],[],[],timeout)
    if not ready:raise TimeoutError('Engine pipe stalled')
    raw=process.stdout.readline(8193)
    if not raw or len(raw)>8192:raise RuntimeError('Engine pipe closed')
    obj=json.loads(raw)
    if not isinstance(obj,dict):raise RuntimeError('Invalid worker packet')
    return obj


def check_sha(repo,engine):
    want=command('git','-C',str(repo),'rev-parse','HEAD:engine').stdout.strip()
    got=command('git','-C',str(engine),'rev-parse','HEAD').stdout.strip()
    if len(want)!=40 or got!=want:
        raise RuntimeError('Engine submodule mismatch')
    return want


def attempt(repo, engine, venv):
    sha=check_sha(repo,engine)
    pyroot=Path(sys.executable).resolve().parent.parent.parent
    if not pyroot.is_dir():raise RuntimeError('Python runtime not available')
    sys.path.insert(0,str(engine))
    try:
        from core.project import new_project_document
        document=new_project_document('I17-Real-Engine')
    finally:sys.path.pop(0)
    with tempfile.TemporaryDirectory(prefix='montara-i15-workspace.',dir='/tmp') as workspace, \
         tempfile.TemporaryDirectory(prefix='montara-i15-lab.',dir='/tmp') as root:
        folder=Path(workspace)/'Projects'/'I17-Real-Engine'
        folder.mkdir(parents=True)
        (folder/'project.json').write_text(json.dumps(document))
        unit=PREFIX+uuid.uuid4().hex[:12]
        args=['systemd-run','--user','--pipe','--wait','--collect','--quiet',
              '--unit='+unit,'--property=MemoryMax=512M','--property=TasksMax=32',
              '--property=TimeoutStopSec=3s','--property=SendSIGKILL=yes',
              '--property=KillMode=control-group',
              '--property=CPUQuota=100%',str(repo/'tests'/'urano_i17_target_entry.sh'),
              '--i17-lab',str(repo/'tests'/'urano_i15_namespace_entry.sh'),'--worker',
              root,workspace,str(repo),str(engine),str(venv),str(pyroot)]
        start=time.monotonic()
        p=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL,start_new_session=True,bufsize=0,
                           env={**os.environ,'PYTHONPATH':str(repo)})
        result={'real_engine_open':False,'forced_cancel_certified':False,
                'controller_survived_cancel':False,'engine_pids_reaped':False,
                'production_safe':False,'ffmpeg_descendant_tested':False,
                'companion_tested':False,'engine_sha':sha}
        try:
            ready=packet(p,35)
            if ready.get('type')!='ready' or ready.get('worker_pid')!=1:
                raise RuntimeError('Engine did not start as namespace PID 1')
            details=unit_status(unit)
            group=details.get('ControlGroup','')
            if (details.get('MemoryMax')!=str(512*1048576) or
                details.get('TasksMax')!='32' or
                details.get('CPUQuotaPerSecUSec')!='1s'):
                raise RuntimeError('Missing cgroup quotas')
            before=cgroup_pids(group)
            ffmpeg_pids=tuple(pid for pid in before
                if Path(f'/proc/{pid}/comm').exists() and
                Path(f'/proc/{pid}/comm').read_text().strip()=='ffmpeg')
            if not ffmpeg_pids:
                for _ in range(20):
                    time.sleep(0.1)
                    before=cgroup_pids(group)
                    ffmpeg_pids=tuple(pid for pid in before
                        if Path(f'/proc/{pid}/comm').exists() and
                        Path(f'/proc/{pid}/comm').read_text().strip()=='ffmpeg')
                    if ffmpeg_pids:break
            if not ffmpeg_pids:raise RuntimeError('Synthetic FFmpeg descendant missing')
            result['ffmpeg_descendant_tested']=True
            p.stdin.write(b'{"op":"open","folder":"I17-Real-Engine"}\n');p.stdin.flush()
            opened=packet(p,20)
            if opened.get('ok') is not True or opened.get('type')!='opened':
                raise RuntimeError('Real Engine project not opened')
            result['real_engine_open']=True
            result['startup_and_open_seconds']=round(time.monotonic()-start,3)
            result['cgroup_pids_before_cancel']=len(before)
            result['ffmpeg_processes_before_cancel']=len(ffmpeg_pids)
            result['memory_peak_at_cancel_mib']=round(int(details.get('MemoryPeak') or 0)/1048576,2)
            done=target_stop(unit)
            if done.returncode:
                raise RuntimeError('systemd could not stop exact target')
            result['controller_survived_cancel']=True
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:raise RuntimeError('target pipe wrapper survived STOP')
            for _ in range(60):
                after=unit_status(unit)
                if after.get('ActiveState') not in ('active','activating') and not cgroup_pids(group):
                    result['engine_pids_reaped']=True;break
                time.sleep(0.2)
            result['forced_cancel_certified']=result['engine_pids_reaped']
            result['cgroup_empty_after_cancel']=not cgroup_pids(group)
            result['ffmpeg_descendant_reaped']=(not cgroup_pids(group) and
                all(not Path(f'/proc/{pid}/cmdline').exists() or
                    b'ffmpeg' not in Path(f'/proc/{pid}/cmdline').read_bytes()
                    for pid in ffmpeg_pids))
            if not result['ffmpeg_descendant_reaped']:
                raise RuntimeError('Synthetic FFmpeg descendant survived')
            result['total_seconds']=round(time.monotonic()-start,3)
            if not result['forced_cancel_certified']:
                raise RuntimeError('target cgroup still active')
            return result
        finally:
            if p.poll() is None:
                target_stop(unit)
                try:p.wait(timeout=5)
                except subprocess.TimeoutExpired:p.kill();p.wait(timeout=4)
            if p.stdin and not p.stdin.closed:p.stdin.close()
            if p.stdout:p.stdout.close()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--repo-root',type=Path,required=True)
    parser.add_argument('--engine-dir',type=Path,required=True)
    parser.add_argument('--venv',type=Path,required=True)
    args=parser.parse_args()
    dest=args.output.resolve()
    if (dest.parent != Path('/tmp') or
        not re.fullmatch(r'montara-i17-report\.[0-9a-f]{12}\.json',dest.name)):
        raise ValueError('Lab output must be temporary I17 .json')
    try:
        data=attempt(args.repo_root.resolve(),args.engine_dir.resolve(),args.venv.resolve())
    except Exception as exc:
        data={'error_class':type(exc).__name__,'error_detail':str(exc)[:120],'forced_cancel_certified':False,
              'production_safe':False}
    temp=dest.with_suffix('.tmp')
    temp.write_text(json.dumps(data,sort_keys=True))
    os.replace(temp,dest)
    if not data.get('forced_cancel_certified'):raise SystemExit(1)

if __name__=='__main__':main()
