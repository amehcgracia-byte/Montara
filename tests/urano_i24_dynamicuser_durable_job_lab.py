"""Operator-only I24 physical integration: durable target -> real Engine DynamicUser.

No public HTTP, no real owner and no production activation. All state is temp.
"""
import argparse
import json
import os
import select
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from urano.job_recovery_ledger import BusyOwner, JobRecoveryLedger
from urano.project_catalog import ProjectCatalog
from urano_i23_dynamicuser_engine_lab import pack

DRIVER = r'''
import json,os,sys
from pathlib import Path
bundle=Path("/opt/montara-i24")
sys.path[:0]=[str(bundle/"site"),str(bundle/"app"),str(bundle/"engine")]
from core.project import new_project_document
from urano.engine_worker_process import run
root=Path("/run")/sys.argv[1]
folder=root/"Projects"/"I24-Synthetic"
folder.mkdir(parents=True)
(folder/"project.json").write_text(json.dumps(new_project_document("I24-Synthetic")))
print("I24_UID:"+str(os.getuid()),flush=True)
run(sys.stdin,sys.stdout,engine_dir=bundle/"engine",data_root=root)
'''

def show(unit):
    x=subprocess.run(["sudo","-n","systemctl","--system","show",unit+".service",
        "-p","ActiveState","-p","ControlGroup","-p","MemoryMax","-p","TasksMax"],
        capture_output=True,text=True,timeout=9,check=True)
    return dict(y.split("=",1) for y in x.stdout.splitlines() if "=" in y)

def packet(proc,seconds=35):
    ready,_,_=select.select([proc.stdout],[],[],seconds)
    if not ready:raise TimeoutError("Engine worker timeout")
    line=proc.stdout.readline(8193)
    if not line or len(line)>8192:raise RuntimeError("Engine worker protocol failure")
    return line.strip()

def stop_exact(unit):
    r=subprocess.run(["sudo","-n","systemctl","--system","stop","--no-block",unit+".service"],
       capture_output=True,text=True,timeout=10)
    if r.returncode:raise RuntimeError("Target systemd stop rejected")

def verified_empty(unit,group):
    if group!="/system.slice/"+unit+".service":
        raise ValueError("Unrecognized cgroup identity")
    for _ in range(60):
        status=show(unit)
        p=Path("/sys/fs/cgroup")/group.lstrip("/")/"cgroup.procs"
        try:remaining=p.read_text().split()
        except FileNotFoundError:remaining=[]
        if status.get("ActiveState") not in ("active","activating","deactivating") and not remaining:
            return True
        time.sleep(.15)
    return False

def main(args):
    since=time.monotonic()
    with tempfile.TemporaryDirectory(prefix="montara-i24-ledger.",dir="/tmp") as data, \
         tempfile.TemporaryDirectory(prefix="montara-i24-bundle.",dir="/tmp") as temp:
        d=Path(data);bundle=Path(temp)
        sha=pack(args.repo,args.engine,args.venv,args.python_root,bundle)
        projects=ProjectCatalog(d/"projects.sqlite3")
        project=projects.create("i24-test-owner","Synthetic I24")
        ledger=JobRecoveryLedger(d/"jobs.sqlite3")
        first=ledger.start_trusted("i24-test-owner",project.id)
        unit=ledger.reserve_target_unit(first)
        assert JobRecoveryLedger(d/"jobs.sqlite3").target_for_trusted(first)==unit
        command=["sudo","-n","systemd-run","--system","--pipe","--wait","--collect","--quiet",
            "--unit="+unit,"-p","DynamicUser=yes","-p","NoNewPrivileges=yes",
            "-p","ProtectHome=yes","-p","ProtectSystem=strict",
            "-p","PrivateTmp=yes","-p","PrivateDevices=yes","-p","PrivateNetwork=yes",
            "-p","RestrictSUIDSGID=yes","-p","MemoryMax=768M","-p","TasksMax=64",
            "-p","CPUQuota=100%","-p","KillMode=control-group",
            "-p","TimeoutStopSec=3s","-p","SendSIGKILL=yes",
            "-p","RuntimeDirectory="+unit,"-p","RuntimeDirectoryMode=0700",
            "-p",f"BindReadOnlyPaths={bundle}:/opt/montara-i24",
            "/usr/bin/env","/opt/montara-i24/python/bin/python3.11","-u","-c",DRIVER,unit]
        proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,text=True,bufsize=1)
        group=None;ok=False
        try:
            identity=packet(proc)
            if not identity.startswith("I24_UID:"):raise RuntimeError("Worker UID missing")
            host_uid=int(identity.partition(":")[2])
            if host_uid in (0,os.getuid()):raise RuntimeError("UID not isolated")
            ready=json.loads(packet(proc))
            if ready.get("type")!="ready":raise RuntimeError("Worker not ready")
            active=show(unit)
            group=active.get("ControlGroup")
            if (group!="/system.slice/"+unit+".service" or
                active.get("MemoryMax")!=str(768*1048576) or
                active.get("TasksMax")!="64"):
                raise RuntimeError("Runtime identity/resources failed verification")
            proc.stdin.write('{"op":"open","folder":"I24-Synthetic"}\n')
            proc.stdin.flush()
            opened=json.loads(packet(proc))
            if opened.get("ok") is not True or opened.get("type")!="opened":
                raise RuntimeError("Real Engine refused project")
            ledger.mark_running(first)
            restarted=JobRecoveryLedger(d/"jobs.sqlite3")
            pending=restarted.recover_after_restart()
            if len(pending)!=1 or restarted.target_for_trusted(pending[0])!=unit:
                raise RuntimeError("Target lost across simulated restart")
            try:restarted.start_trusted("i24-test-owner",project.id)
            except BusyOwner:pass
            else:raise RuntimeError("Owner job not fenced after restart")
            stopping=restarted.request_stop(pending[0])
            stop_exact(unit)
            proc.wait(timeout=15)
            if not verified_empty(unit,group):raise RuntimeError("Cgroup still live")
            restarted.confirm_stopped(stopping,verified_cgroup_empty=True)
            next_job=restarted.start_trusted("i24-test-owner",project.id)
            if next_job.generation<=first.generation:
                raise RuntimeError("Generation not incremented")
            ok=True
            print(json.dumps({"real_engine_opened":True,"host_uid":host_uid,
                "durable_target_before_launch":True,"recovered_target_after_restart":True,
                "owner_fenced_until_reaped":True,"cgroup_empty_after_cancel":True,
                "generation_advanced":True,"elapsed_seconds":round(time.monotonic()-since,2),
                "engine_sha":sha,"production_ready":False,"companion_tested":False},sort_keys=True))
        finally:
            if not ok:
                try:stop_exact(unit)
                except Exception:pass
            if proc.poll() is None:
                try:proc.wait(timeout=12)
                except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
            if proc.stdin and not proc.stdin.closed:proc.stdin.close()
            if proc.stdout:proc.stdout.close()

if __name__=="__main__":
    a=argparse.ArgumentParser()
    for field in ("repo","engine","venv","python-root"):
        a.add_argument("--"+field,type=Path,required=True)
    a.add_argument("--operator-opt-in",action="store_true")
    options=a.parse_args()
    if not options.operator_opt_in:a.error("Operator opt-in required")
    main(options)

