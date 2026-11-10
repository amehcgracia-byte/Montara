"""Opt-in Linux real Engine probe: userns/mountns/netns/pidns + systemd cgroup.

NO deployment, real owners, networking, sudo, persistent system units, video,
or claim of a production security boundary. systemd-run creates temporary user
services, not new VM-wide service files. Use on an approved test host only.
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

MEMORY_BYTES = 512 * 1024 * 1024
TASKS_LIMIT = 24
CPU_QUOTA = "100%"
UNIT_PATTERN = re.compile(r"montara-i16-lab-[0-9a-f]{12}")


def checked_engine(repo: Path, engine: Path) -> str:
    pinned = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD:engine"], text=True, timeout=8).strip()
    actual = subprocess.check_output(["git", "-C", str(engine), "rev-parse", "HEAD"], text=True, timeout=8).strip()
    if pinned != actual or len(actual) != 40:
        raise ValueError("Engine submodule version mismatch")
    return actual


def properties(unit: str) -> dict[str,str]:
    if not UNIT_PATTERN.fullmatch(unit):
        raise ValueError("Unrecognized lab unit")
    value = subprocess.check_output(["systemctl", "--user", "show", unit + ".service",
                                    "-p", "MemoryMax", "-p", "TasksMax", "-p", "CPUQuotaPerSecUSec",
                                    "-p", "MemoryCurrent", "-p", "MemoryPeak", "-p", "TasksCurrent",
                                    "-p", "ControlGroup", "-p", "ActiveState"],
                                    text=True, timeout=8)
    return dict(x.split("=",1) for x in value.splitlines() if "=" in x)


def verify_limits(values: dict[str,str], unit: str):
    if (values.get("MemoryMax") != str(MEMORY_BYTES) or
        values.get("TasksMax") != str(TASKS_LIMIT) or
        values.get("CPUQuotaPerSecUSec") != "1s" or
        not values.get("ControlGroup", "").endswith("/" + unit + ".service") or
        values.get("ActiveState") != "active"):
        raise AssertionError("Cgroup limits not confirmed by systemd")


def stop_unit(unit: str) -> None:
    if not UNIT_PATTERN.fullmatch(unit):
        raise ValueError("Refusing to stop a non-I16 unit")
    subprocess.run(["systemctl", "--user", "stop", unit + ".service"],
                   timeout=12, capture_output=True, check=False)


def receive(proc: subprocess.Popen, *, seconds: float=20.0) -> dict:
    if proc.stdout is None:
        raise RuntimeError("No Engine output")
    ready, _, _ = select.select([proc.stdout], [], [], seconds)
    if not ready:
        raise TimeoutError("Engine packet timeout")
    line = proc.stdout.readline(8193)
    if not line or len(line)>8192:
        raise RuntimeError("Engine output closed or oversized")
    packet = json.loads(line)
    if not isinstance(packet, dict):
        raise RuntimeError("Engine packet not object")
    return packet


def probe(repo: Path, engine: Path, venv: Path, *, cancel: bool=False) -> dict:
    engine_sha = checked_engine(repo, engine)
    if not (repo/'tests'/'urano_i15_namespace_entry.sh').is_file():
        raise ValueError("I15 lab namespace entry missing")
    interpreter = Path(sys.executable).resolve()
    python_root = interpreter.parent.parent.parent
    if not python_root.is_dir() or not venv.is_dir():
        raise ValueError("Pinned Python runtime missing")
    # Only synthetic, unique, owned temp paths; the C8 Owner databases and
    # actual users' projects never enter the mount namespace.
    with tempfile.TemporaryDirectory(prefix="montara-i15-workspace.",dir="/tmp") as workspace, \
         tempfile.TemporaryDirectory(prefix="montara-i15-lab.",dir="/tmp") as root:
        sys.path.insert(0,str(engine))
        try:
            from core.project import new_project_document
            folder = Path(workspace)/'Projects'/'I16-Synthetic'
            folder.mkdir(parents=True)
            (folder/'project.json').write_text(json.dumps(new_project_document('I16-Synthetic')))
        finally:
            sys.path.remove(str(engine))
        unit='montara-i16-lab-'+uuid.uuid4().hex[:12]
        cmd=["systemd-run","--user","--pipe","--wait","--collect","--quiet",
             "--unit="+unit,"--property=MemoryMax=512M","--property=TasksMax=24",
             "--property=CPUQuota=100%", "unshare","--user","--map-root-user",
             "--mount","--net","--pid","--fork","--",
             str(repo/'tests'/'urano_i15_namespace_entry.sh'),'--worker',root,workspace,
             str(repo),str(engine),str(venv),str(python_root)]
        env={**os.environ, "PYTHONPATH":str(repo)}
        started=time.monotonic()
        proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,bufsize=0,start_new_session=True,env=env)
        result={"engine_sha":engine_sha,"real_engine_open":False,
                "user_mount_net_pid_namespaces":False,"cgroup_limits_verified":False,
                "clean_shutdown":False,"forced_cancel_reaped":False,
                "production_isolation_certified":False,"companion_tested":False,
                "video_render_tested":False}
        try:
            ready=receive(proc,seconds=45)
            if ready.get('type')!='ready' or ready.get('worker_pid')!=1:
                raise RuntimeError('Worker not PID 1 in its namespace')
            result['user_mount_net_pid_namespaces']=True
            result['startup_seconds']=round(time.monotonic()-started,3)
            values=properties(unit)
            verify_limits(values,unit)
            result['cgroup_limits_verified']=True
            result['memory_limit_mib']=MEMORY_BYTES//(1024*1024)
            result['tasks_limit']=TASKS_LIMIT
            result['cpu_quota_one_core_equivalent']=True
            result['memory_peak_at_open_mib']=round(int(values.get('MemoryPeak',0))/1048576,2)
            proc.stdin.write(b'{"op":"open","folder":"I16-Synthetic"}\n');proc.stdin.flush()
            opened=receive(proc)
            if opened.get('ok') is not True or opened.get('type')!='opened':
                raise RuntimeError('Real Engine failed to open synthetic project')
            result['real_engine_open']=True
            if cancel:
                # Operator requests hard stop of exactly this random temporary
                # service. systemd stops/reaps all processes in its cgroup.
                stop_unit(unit)
                proc.wait(timeout=12)
                result['forced_cancel_reaped']=properties(unit).get('ActiveState')!='active'
                if not result['forced_cancel_reaped']:
                    raise RuntimeError('Cgroup remains active after stop')
            else:
                proc.stdin.write(b'{"op":"stop"}\n');proc.stdin.flush()
                packet=receive(proc)
                if packet.get('type')!='stopped' or packet.get('ok') is not True:
                    raise RuntimeError('Worker did not confirm close')
                proc.stdin.close()
                proc.wait(timeout=12)
                result['clean_shutdown']=proc.returncode==0
                if not result['clean_shutdown']:
                    raise RuntimeError('Worker exit was nonzero')
            result['elapsed_seconds']=round(time.monotonic()-started,3)
            return result
        finally:
            if proc.poll() is None:
                stop_unit(unit)
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill();proc.wait(timeout=5)
            # Expose no stdout, stderr or paths from a live shared server.
            if proc.stdin and not proc.stdin.closed:proc.stdin.close()
            if proc.stdout:proc.stdout.close()
            if proc.stderr:proc.stderr.close()
            # systemd --collect unloads temporary units after process exit.


def main():
    parser=argparse.ArgumentParser(description="I16 opt-in Linux cgroup lab")
    parser.add_argument('--repo-root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--engine-dir',type=Path,required=True)
    parser.add_argument('--venv',type=Path,required=True)
    parser.add_argument('--cancel',action='store_true')
    a=parser.parse_args()
    print(json.dumps(probe(a.repo_root.resolve(),a.engine_dir.resolve(),a.venv.resolve(),cancel=a.cancel),indent=2,sort_keys=True))

if __name__=='__main__':main()
