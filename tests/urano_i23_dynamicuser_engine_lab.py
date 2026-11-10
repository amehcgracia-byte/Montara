"""I23 opt-in: run real pinned Engine under a transient DynamicUser identity.

Single operator-run smoke test. NEVER call from Owner HTTP or production broker.
Uses synthetic project data only; no service installation, real tenant or media.
"""
import argparse
import io
import json
import os
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


def command(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def pack(repo, engine, venv, pyroot, dest):
    pinned=command(["git","-C",str(repo),"rev-parse","HEAD:engine"],capture_output=True,text=True).stdout.strip()
    actual=command(["git","-C",str(engine),"rev-parse","HEAD"],capture_output=True,text=True).stdout.strip()
    if len(pinned)!=40 or actual!=pinned:
        raise RuntimeError("Engine SHA differs from pinned submodule")
    # Git archive excludes all untracked operator files, tokens and credentials.
    for source, subdir, paths in ((engine,"engine",[]),(repo,"app",["urano"])):
        target=dest/subdir
        target.mkdir()
        proc=subprocess.Popen(["git","-C",str(source),"archive","--format=tar","HEAD",*paths],
                              stdout=subprocess.PIPE)
        try:command(["tar","-xf","-","-C",str(target)],stdin=proc.stdout)
        finally:proc.stdout.close()
        if proc.wait(timeout=40):
            raise RuntimeError("Failed to archive pinned code")
    if not (dest/"engine/server/api.py").is_file():
        raise RuntimeError("Missing real Engine API")
    site=venv/"lib/python3.11/site-packages"
    if not site.is_dir():
        raise RuntimeError("Python 3.11 dependencies missing")
    shutil.copytree(pyroot,dest/"python",symlinks=True)
    shutil.copytree(site,dest/"site",symlinks=True)
    # Only ephemeral copies change permissions; never touch original HOME.
    for root,dirs,files in os.walk(dest,followlinks=False):
        os.chmod(root,0o755)
        for name in dirs+files:
            path=Path(root)/name
            if path.is_symlink():
                if os.readlink(path).startswith("/home/"):
                    raise RuntimeError("Package references protected home")
            elif path.is_file():
                os.chmod(path,0o555 if path.stat().st_mode & 0o111 else 0o444)
    return pinned


# Executed only INSIDE the locked-down systemd transient service.
ENGINE_DRIVER = r'''
import io,json,os,sys
from pathlib import Path
bundle=Path("/opt/montara-i23")
sys.path[:0]=[str(bundle/"site"),str(bundle/"app"),str(bundle/"engine")]
from core.project import new_project_document
from urano.engine_worker_process import run
data=Path("/run")/sys.argv[1]
project=data/"Projects"/"I23-Synthetic"
project.mkdir(parents=True)
(project/"project.json").write_text(json.dumps(new_project_document("I23-Synthetic")))
request=io.StringIO('{"op":"open","folder":"I23-Synthetic"}\n{"op":"stop"}\n')
response=io.StringIO()
run(request,response,engine_dir=bundle/"engine",data_root=data)
messages=[json.loads(line) for line in response.getvalue().splitlines()]
assert messages[0].get("type")=="ready",messages
assert any(x.get("type")=="opened" and x.get("ok") is True for x in messages),messages
assert messages[-1].get("type")=="stopped",messages
try:
    Path("/home/fgardel00").stat()
    home_blocked=False
except (PermissionError,FileNotFoundError):
    home_blocked=True
print("I23_REPORT:"+json.dumps({"engine_opened":True,"host_uid":os.getuid(),
    "home_blocked":home_blocked,"worker_closed":True}),flush=True)
'''


def test_service(dest, unit):
    args=["sudo","-n","systemd-run","--system","--pipe","--wait","--collect","--quiet",
          "--unit="+unit,
          "-p","DynamicUser=yes","-p","NoNewPrivileges=yes",
          "-p","ProtectHome=yes","-p","ProtectSystem=strict",
          "-p","PrivateTmp=yes","-p","PrivateNetwork=yes",
          "-p","PrivateDevices=yes","-p","RestrictSUIDSGID=yes",
          "-p","MemoryMax=768M","-p","TasksMax=64","-p","CPUQuota=100%",
          "-p","RuntimeDirectory="+unit,"-p","RuntimeDirectoryMode=0700",
          "-p",f"BindReadOnlyPaths={dest}:/opt/montara-i23",
          "/opt/montara-i23/python/bin/python3.11","-u","-c",ENGINE_DRIVER,unit]
    result=command(args,capture_output=True,text=True,timeout=120)
    reports=[x.partition("I23_REPORT:")[2] for x in result.stdout.splitlines()
             if "I23_REPORT:" in x]
    if len(reports)!=1:
        raise RuntimeError("No authentic Engine open/close confirmation")
    parsed=json.loads(reports[0])
    if (not parsed.get("engine_opened") or not parsed.get("worker_closed")
        or not parsed.get("home_blocked") or parsed["host_uid"] in (0,os.getuid())):
        raise RuntimeError("Isolation or Engine execution not verified")
    return parsed


def main():
    p=argparse.ArgumentParser()
    for field in ("repo","engine","venv","python-root"):
        p.add_argument("--"+field,type=Path,required=True)
    p.add_argument("--operator-opt-in",action="store_true")
    args=p.parse_args()
    if not args.operator_opt_in:
        p.error("Requires explicit --operator-opt-in; never call from web")
    unit="montara-i23-lab-"+secrets.token_hex(6)
    with tempfile.TemporaryDirectory(prefix="montara-i23-bundle.",dir="/tmp") as temp:
        dest=Path(temp)
        sha=pack(args.repo,args.engine,args.venv,args.python_root,dest)
        result=test_service(dest,unit)
        print(json.dumps({"engine_sha":sha,"production_sandbox_certified":False,
                          "companion_tested":False,"mp4_tested":False,**result},sort_keys=True))


if __name__=="__main__":
    main()
