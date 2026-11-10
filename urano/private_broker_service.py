"""I26 isolated root service for a private, lab-only systemd Engine broker.

Only allows trusted OS peer identity and a *fixed synthetic* project. No HTTP,
arbitrary units, paths, shell fragments or user-supplied owner/project.
No production Owner integration until UID, IPC and project grant are hardened.
"""
from __future__ import annotations

import argparse
import json
import os
import pwd
import re
import socket
import stat
import stat
import subprocess
import time
from pathlib import Path

from urano.job_recovery_ledger import JobRecoveryLedger,BusyOwner,StaleJob
from urano.restricted_broker_ipc import authenticate_peer,parse_stop
from urano.restricted_systemd_broker import (
    RestrictedTargetControl,expected_cgroup,fixed_launch_properties,UnverifiedTarget
)

OWNER="i26-demo-owner"
PROJECT="i26-demo-project"
SOCKET=Path("/run/montara-i26-broker/control.sock")
LEDGER=Path("/var/lib/montara-i26-broker/jobs.sqlite3")
READY_FILE="ready.json"


def cmd(args,timeout=12):
    return subprocess.run(args,check=True,capture_output=True,text=True,timeout=timeout)


class SystemdDirect:
    def show(self,unit):
        expected_cgroup(unit)
        r=cmd(["/usr/bin/systemctl","--system","show",unit+".service",
               "-p","ActiveState","-p","ControlGroup","-p","MainPID",
               "-p","MemoryMax","-p","TasksMax"])
        return dict(line.split("=",1) for line in r.stdout.splitlines() if "=" in line)

    def stop_exact(self,unit):
        expected_cgroup(unit)
        cmd(["/usr/bin/systemctl","--system","stop","--no-block",unit+".service"])


class DemoBroker:
    def __init__(self,bundle):
        self.bundle=Path(bundle)
        self.ledger=JobRecoveryLedger(LEDGER)
        self.control=RestrictedTargetControl(self.ledger,SystemdDirect())
        # Recover ONLY exact I24 names recorded before a crash. No TTL.
        for orphan in self.ledger.recover_after_restart():
            if self.ledger.target_for_trusted(orphan) is None:
                continue  # fail closed, owner is still fenced
            try:
                if self.control.stop_verified(orphan):
                    self.ledger.confirm_stopped(
                        self.ledger.request_stop(orphan),verified_cgroup_empty=True)
            except Exception:
                pass  # retain orphaned/stopping state; deny new launch

    def demo_start(self):
        lease=self.ledger.start_trusted(OWNER,PROJECT)
        unit=self.ledger.reserve_target_unit(lease)
        try:
            props=fixed_launch_properties(unit,self.bundle)
            command=["/usr/bin/systemd-run","--system","--no-block","--collect",
                "--quiet","--unit="+unit]
            for prop in props:
                command.extend(["-p",prop])
            command.extend([
                "/usr/bin/env","/opt/montara-engine/python/bin/python3.11",
                "-u","/opt/montara/broker/private_broker_worker.py",
                "/opt/montara-engine",unit,
            ])
            cmd(command,timeout=14)
            ready_path=Path("/run")/unit/READY_FILE
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                details=self.control.systemd.show(unit)
                if details.get("ControlGroup")==expected_cgroup(unit) and (
                    details.get("ActiveState")=="active" and
                    details.get("MemoryMax")==str(768*1048576) and
                    details.get("TasksMax")=="64"):
                    try:
                        marker=json.loads(ready_path.read_text())
                    except (FileNotFoundError,json.JSONDecodeError,PermissionError):
                        marker=None
                    if marker and marker.get("ready") is True:
                        uid=marker.get("uid")
                        if isinstance(uid,int) and uid not in (0,os.getuid()):
                            self.ledger.mark_running(lease)
                            return {"ok":True,"job_id":lease.job_id,
                                    "generation":lease.generation,"engine_opened":True,
                                    "worker_uid":uid}
                if details.get("ActiveState") in ("failed","inactive"):
                    break
                time.sleep(.25)
            raise RuntimeError("Real isolated Engine not ready")
        except Exception:
            # Never release an uncertain service without OS proof.
            try:
                current=self.ledger.get_trusted(lease.job_id)
                if current and self.control.stop_verified(current):
                    self.ledger.confirm_stopped(
                        self.ledger.request_stop(current),verified_cgroup_empty=True)
            except Exception:
                pass
            raise

    def stop(self,payload):
        job_id,generation=parse_stop(payload)
        current=self.ledger.get_trusted(job_id)
        if current is None or current.generation!=generation:
            raise StaleJob("Unknown or stale job")
        if current.state in ("starting","running","orphaned"):
            current=self.ledger.request_stop(current)
        elif current.state!="stopping":
            raise StaleJob("Job already stopped")
        if not self.control.stop_verified(current):
            raise UnverifiedTarget("Cgroup not empty")
        self.ledger.confirm_stopped(current,verified_cgroup_empty=True)
        return {"ok":True,"state":"stopped"}


def dispatch(conn: socket.socket, trusted_uid: int, web_uid: int,
             broker: DemoBroker):
    """Single local request; the peer must be authorized BEFORE parsing."""
    authenticate_peer(conn,trusted_uid=trusted_uid,web_uid=web_uid)
    data=conn.recv(513)
    if len(data)>512 or not data:
        raise ValueError("Invalid broker frame")
    obj=json.loads(data)
    if not isinstance(obj,dict) or not isinstance(obj.get("op"),str):
        raise ValueError("Invalid request")
    if obj["op"]=="ping" and set(obj)=={"op"}:
        return {"ok":True,"service":"montara-i26","mode":"lab"}
    if obj["op"]=="demo_start" and set(obj)=={"op"}:
        return broker.demo_start()
    if obj["op"]=="stop":
        parse_stop(data)
        return broker.stop(data)
    raise ValueError("Operation not allowed")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--bundle",required=True)
    parser.add_argument("--trusted-uid",required=True,type=int)
    parser.add_argument("--web-uid",required=True,type=int)
    args=parser.parse_args()
    if os.geteuid()!=0:
        raise RuntimeError("Only root-owned service may manage the isolated systemd units")
    if args.trusted_uid<=0 or args.trusted_uid==args.web_uid:
        raise ValueError("Broker caller must not be web UID or root")
    if not re.fullmatch(r"/opt/montara/bundles/engine-[0-9a-f]{40}",args.bundle):
        raise ValueError("Invalid pinned bundle")
    bundle=Path(args.bundle)
    if (bundle.is_symlink() or bundle.stat().st_uid != 0 or
        bundle.stat().st_mode & 0o022 or
        not (bundle / "engine" / "server" / "api.py").is_file()):
        raise ValueError("Engine bundle must be root-owned and immutable")
    broker=DemoBroker(args.bundle)
    if SOCKET.is_symlink():
        raise RuntimeError("Socket symlink forbidden")
    if SOCKET.exists():
        SOCKET.unlink()
    srv=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    try:
        srv.bind(str(SOCKET))
        os.chmod(SOCKET,0o660)
        srv.listen(8)
        while True:
            conn,_=srv.accept()
            with conn:
                conn.settimeout(5)
                try:
                    reply=dispatch(conn,args.trusted_uid,args.web_uid,broker)
                except (ValueError,TypeError,PermissionError,BusyOwner,StaleJob,UnverifiedTarget,
                        RuntimeError,subprocess.SubprocessError,TimeoutError,KeyError) as exc:
                    reply={"ok":False,"error":type(exc).__name__}
                try:conn.sendall(json.dumps(reply,separators=(",",":")).encode()+b"\n")
                except (BrokenPipeError,ConnectionResetError):pass
    finally:
        srv.close()
        SOCKET.unlink(missing_ok=True)


if __name__=="__main__":
    main()

