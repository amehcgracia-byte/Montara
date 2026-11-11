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
import select
import sqlite3
import stat
import stat
import subprocess
import time
from pathlib import Path

from urano.private_owner_admission import verify_owner_and_project,OwnerAdmissionDenied
from urano.private_stage_owner_admission import verify_stage_owner_request,ReadOnlyOwnerCatalog
from urano.private_stage_snapshot_bridge import trusted_stage_snapshot
from urano.private_stage_unix_transport import SystemdUnixStageTransport
from urano.private_engine_route_contract import PrivateEngineRouteDenied
from urano.private_editor_connect_admission import verify_editor_connect_request
from urano.private_editor_fd_handoff import (
    EditorFdLease, open_verified_editor_socket, send_editor_fd
)
from urano.job_recovery_ledger import JobRecoveryLedger,BusyOwner,StaleJob
from urano.restricted_broker_ipc import authenticate_peer,parse_stop
from urano.restricted_systemd_broker import (
    RestrictedTargetControl,expected_cgroup,fixed_launch_properties,UnverifiedTarget,
    WorkerResourceProfile
)

OWNER="i26-demo-owner"
PROJECT="i26-demo-project"
SOCKET=Path("/run/montara-i26-broker/control.sock")
OWNER_SOCKET=Path("/run/montara-i27-admission/control.sock")
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
    def __init__(self,bundle,*,jm_bundle=None,resources=None,private_preview_limit_mib=256):
        self.bundle=Path(bundle)
        self.jm_bundle=Path(jm_bundle) if jm_bundle is not None else None
        from urano.jm_private_proxy_overlay import private_proxy_limit_mib
        self.private_preview_limit_mib=private_proxy_limit_mib(private_preview_limit_mib)
        self.resources=resources if resources is not None else WorkerResourceProfile()
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

    def demo_start(self, owner_id=OWNER, project_id=PROJECT):
        lease=self.ledger.start_trusted(owner_id,project_id)
        unit=self.ledger.reserve_target_unit(lease)
        try:
            props=fixed_launch_properties(unit,self.bundle,jm_bundle=self.jm_bundle,
                                          resources=self.resources,
                                          owner_id=owner_id if self.jm_bundle is not None else None)
            command=["/usr/bin/systemd-run","--system","--no-block","--collect",
                "--quiet","--unit="+unit]
            for prop in props:
                command.extend(["-p",prop])
            command.extend([
                "/usr/bin/env","/opt/montara-engine/python/bin/python3.11",
                "-u","/opt/montara/broker/private_broker_worker.py",
                "/opt/montara-engine",unit,
                *([project_id,str(lease.generation)] if project_id!=PROJECT else []),
                *(["--jm-bundle","/opt/montara-jm",
                    "--private-proxy-limit-mib",str(self.private_preview_limit_mib)]
                  if self.jm_bundle is not None else []),
            ])
            cmd(command,timeout=14)
            ready_path=Path("/run")/unit/READY_FILE
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                details=self.control.systemd.show(unit)
                if details.get("ControlGroup")==expected_cgroup(unit) and (
                    details.get("ActiveState")=="active" and
                    details.get("MemoryMax")==str(self.resources.memory_mb*1048576) and
                    details.get("TasksMax")==str(self.resources.tasks_max)):
                    try:
                        marker=json.loads(ready_path.read_text())
                    except (FileNotFoundError,json.JSONDecodeError,PermissionError):
                        marker=None
                    if (marker and marker.get("ready") is True and
                        marker.get("folder")==(
                            "I26-Synthetic" if project_id==PROJECT else project_id)):
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

    def editor_connect_owner(self, owner_id, project_id, generation):
        """Grant one pinned JM HTTP connection, never proxy media via root."""
        return open_verified_editor_socket(
            self.ledger, self.control.systemd.show,
            owner_id=owner_id, project_id=project_id, generation=generation,
        )

    def ensure_owner(self, owner_id, project_id):
        """Idempotent admission for first valid proxy upload and later edits.

        Repeat calls only reuse a verified active worker for the SAME project.
        Never replace or release an uncertain owner unit/cgroup.
        """
        jobs=self.ledger.unverified_for_owner(owner_id)
        if not jobs:
            result=self.demo_start(owner_id,project_id)
            return {"ok":True,"project_id":project_id,
                    "state":"ready","generation":result["generation"]}
        if len(jobs)!=1 or jobs[0].project_id!=project_id or jobs[0].state!="running":
            raise BusyOwner("Owner Engine worker not safely reusable")
        lease=jobs[0]
        unit=self.ledger.target_for_trusted(lease)
        if unit is None:
            raise StaleJob("No pinned Engine worker")
        details=self.control.systemd.show(unit)
        try:
            pid=int(details.get("MainPID","0"))
        except (ValueError,TypeError):
            pid=0
        if (details.get("ActiveState")!="active"
            or details.get("ControlGroup")!=expected_cgroup(unit)
            or pid<=1):
            raise UnverifiedTarget("Owner worker is no longer verified")
        marker=Path("/run")/unit/READY_FILE
        try:
            data=json.loads(marker.read_text())
        except (OSError,ValueError) as exc:
            raise UnverifiedTarget("Owner worker readiness unavailable") from exc
        if (data.get("ready") is not True or data.get("folder")!=project_id
            or type(data.get("uid")) is not int or data["uid"]<=0):
            raise UnverifiedTarget("Owner worker project mismatch")
        return {"ok":True,"project_id":project_id,
                "state":"ready","generation":lease.generation}

    def stage_snapshot_owner(self, owner_id, project_id, generation, owner_db_root):
        """Broker-owned trusted read: no browser-supplied worker endpoint."""
        snapshot = trusted_stage_snapshot(
            owner_id, project_id, generation=generation,
            catalog=ReadOnlyOwnerCatalog(owner_db_root),
            ledger=self.ledger,
            engine_sha=self.bundle.name.removeprefix("engine-"),
            transport=SystemdUnixStageTransport(self.control.systemd.show),
        )
        return {"ok": True, **snapshot}

    def stop_owner(self, owner_id, project_id):
        jobs=self.ledger.unverified_for_owner(owner_id)
        if len(jobs)!=1 or jobs[0].project_id!=project_id:
            raise StaleJob("No matching project session")
        current=jobs[0]
        if current.state in ("starting","running","orphaned"):
            current=self.ledger.request_stop(current)
        elif current.state!="stopping":
            raise StaleJob("Job already stopped")
        if not self.control.stop_verified(current):
            raise UnverifiedTarget("Cgroup not empty")
        self.ledger.confirm_stopped(current,verified_cgroup_empty=True)
        return {"ok":True,"state":"stopped","project_id":project_id}

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


def dispatch_owner(conn, web_uid:int, owner_db_root:Path, broker:DemoBroker):
    """Independent session, CSRF and project verification in the root broker."""
    import struct
    raw=conn.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,struct.calcsize("3i"))
    pid,uid,gid=struct.unpack("3i",raw)
    if pid<=0 or uid!=web_uid:
        raise PermissionError("Unauthorized browser service account")
    data=conn.recv(513)
    if not data or len(data)>384:
        raise ValueError("Owner frame denied")
    # The read path has a separate strict schema including the worker
    # generation. It rechecks the existing broker-side Google session+CSRF.
    # Dispatch on the parsed operation, not a substring inside raw JSON.
    # An encoded string or unrelated field cannot select a privileged route.
    try:
        envelope=json.loads(data)
    except (ValueError,UnicodeError) as exc:
        raise ValueError("Invalid private owner frame") from exc
    if not isinstance(envelope,dict):
        raise ValueError("Invalid private owner frame")
    if envelope.get("op")=="connect_editor":
        owner_id,project_id,generation=verify_editor_connect_request(
            data,owner_db_root=owner_db_root)
        return broker.editor_connect_owner(owner_id,project_id,generation)
    if envelope.get("op")=="stage_snapshot_owner":
        owner_id,project_id,generation=verify_stage_owner_request(
            data,owner_db_root=owner_db_root)
        return broker.stage_snapshot_owner(
            owner_id,project_id,generation,owner_db_root)
    op,owner_id,project_id=verify_owner_and_project(data,owner_db_root=owner_db_root)
    if op=="ensure_owner":
        return broker.ensure_owner(owner_id,project_id)
    if op=="open_owner":
        result=broker.demo_start(owner_id,project_id)
        # Do not disclose systemd/worker/unit identifiers to HTTP.
        return {"ok":True,"project_id":project_id,"state":"ready",
                "generation":result["generation"]}
    if op=="close_owner":
        return broker.stop_owner(owner_id,project_id)
    raise ValueError("Invalid owner operation")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--bundle",required=True)
    parser.add_argument("--trusted-uid",required=True,type=int)
    parser.add_argument("--web-uid",required=True,type=int)
    parser.add_argument("--web-gid",type=int)
    parser.add_argument("--owner-db-root")
    parser.add_argument("--jm-bundle")
    parser.add_argument("--worker-memory-mb",type=int,default=768)
    parser.add_argument("--worker-cpu-percent",type=int,default=100)
    parser.add_argument("--worker-tasks-max",type=int,default=64)
    parser.add_argument("--private-proxy-limit-mib",type=int,default=256)
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
    if args.jm_bundle:
        if not re.fullmatch(r"/opt/montara/bundles/jm-[0-9a-f]{40}",args.jm_bundle):
            raise ValueError("Unpinned private JM editor bundle")
        jm=Path(args.jm_bundle)
        if (jm.is_symlink() or jm.stat().st_uid!=0 or jm.stat().st_mode & 0o022
                or not (jm/"app.py").is_file()
                or not (jm/"web/index.html").is_file()
                or not (jm/"web/montara.js").is_file()
                or not (jm/"web/companion.js").is_file()):
            raise ValueError("Private JM bundle must be root-owned and complete")
        from urano.jm_bundle_manifest import (
            verify_jm_bundle_files, verify_pinned_chema_manifest
        )
        manifest_file=jm/"montara-jm-bundle.json"
        if (manifest_file.is_symlink() or not manifest_file.is_file()
                or manifest_file.stat().st_size > 8192
                or manifest_file.stat().st_uid != 0
                or manifest_file.stat().st_mode & 0o022):
            raise ValueError("Untrusted original JM release manifest")
        try:
            manifest=json.loads(manifest_file.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError) as exc:
            raise ValueError("Corrupt original JM release manifest") from exc
        verify_pinned_chema_manifest(
            manifest,expected_editor_commit=jm.name[3:],
            expected_engine_commit=bundle.name[7:],
            expected_private_preview_limit_mib=args.private_proxy_limit_mib)
        verify_jm_bundle_files(jm,manifest)
    resources=WorkerResourceProfile(args.worker_memory_mb,args.worker_cpu_percent,
                                    args.worker_tasks_max)
    broker=DemoBroker(args.bundle,jm_bundle=args.jm_bundle,resources=resources,
                      private_preview_limit_mib=args.private_proxy_limit_mib)
    if SOCKET.is_symlink():
        raise RuntimeError("Socket symlink forbidden")
    if SOCKET.exists():
        SOCKET.unlink()
    srv=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    owner_srv=None
    try:
        srv.bind(str(SOCKET))
        os.chmod(SOCKET,0o660)
        srv.listen(8)
        if args.owner_db_root:
            if (args.web_gid is None or args.web_uid<=0 or args.web_gid<=0
                or Path(args.owner_db_root).is_symlink()):
                raise ValueError("Invalid owner identity or readonly DB mount")
            if OWNER_SOCKET.parent.is_symlink():
                raise RuntimeError("Owner socket path linked")
            OWNER_SOCKET.parent.mkdir(mode=0o710,parents=True,exist_ok=True)
            os.chown(OWNER_SOCKET.parent,0,args.web_gid)
            os.chmod(OWNER_SOCKET.parent,0o710)
            if OWNER_SOCKET.is_symlink():
                raise RuntimeError("Owner socket symlink forbidden")
            OWNER_SOCKET.unlink(missing_ok=True)
            owner_srv=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
            owner_srv.bind(str(OWNER_SOCKET))
            os.chown(OWNER_SOCKET,0,args.web_gid)
            os.chmod(OWNER_SOCKET,0o660)
            owner_srv.listen(8)
        listeners=[srv]+([owner_srv] if owner_srv is not None else [])
        while True:
            ready,_,_=select.select(listeners,[],[])
            for listener in ready:
                conn,_=listener.accept()
                with conn:
                    conn.settimeout(6)
                    try:
                        if listener is srv:
                            reply=dispatch(conn,args.trusted_uid,args.web_uid,broker)
                        else:
                            reply=dispatch_owner(conn,args.web_uid,
                                Path(args.owner_db_root),broker)
                    except (ValueError,TypeError,PermissionError,BusyOwner,StaleJob,
                            UnverifiedTarget,RuntimeError,subprocess.SubprocessError,
                            TimeoutError,KeyError,sqlite3.Error,PrivateEngineRouteDenied) as exc:
                        reply={"ok":False,"error":type(exc).__name__}
                    try:
                        if isinstance(reply, EditorFdLease):
                            # Root passes only a connected kernel descriptor;
                            # the web process handles the media stream itself.
                            send_editor_fd(conn, reply)
                        else:
                            conn.sendall(json.dumps(reply,separators=(",",":")).encode()+b"\n")
                    except (BrokenPipeError,ConnectionResetError,OSError):
                        pass
    finally:
        srv.close()
        if owner_srv is not None:
            owner_srv.close()
            OWNER_SOCKET.unlink(missing_ok=True)
        SOCKET.unlink(missing_ok=True)


if __name__=="__main__":
    main()

