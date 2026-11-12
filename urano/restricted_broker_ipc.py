"""I25 Linux peer-authenticated stop protocol; no public/root daemon yet.

For root-owned AF_UNIX broker socket with separate trusted service account.
Socket listener/permissions and service are NOT installed here.
"""
from __future__ import annotations
import json
import re
import socket
import struct
from urano.job_recovery_ledger import JobRecoveryLedger, StaleJob
from urano.restricted_systemd_broker import RestrictedTargetControl, UnverifiedTarget

class UntrustedPeer(PermissionError):
    pass

def authenticate_peer(connection: socket.socket, *, trusted_uid: int,
                      web_uid: int) -> None:
    if (not isinstance(trusted_uid,int) or trusted_uid<=0 or
        trusted_uid==web_uid or not isinstance(web_uid,int)):
        raise ValueError("Trusted UID must differ from web and root")
    raw=connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,struct.calcsize("3i"))
    pid,uid,gid=struct.unpack("3i",raw)
    if pid<=0 or uid!=trusted_uid:
        raise UntrustedPeer("Unix peer is not trusted")

def parse_stop(payload: bytes)->tuple[str,int]:
    if not isinstance(payload,bytes) or len(payload)>256:
        raise ValueError("Invalid broker frame")
    request=json.loads(payload)
    if not isinstance(request,dict) or set(request)!={"op","job_id","generation"}:
        raise ValueError("Only job stop accepted")
    job=request["job_id"];gen=request["generation"]
    if (request["op"]!="stop" or not isinstance(job,str) or
        not re.fullmatch(r"job-[0-9a-f]{32}",job) or
        isinstance(gen,bool) or not isinstance(gen,int) or gen<=0):
        raise ValueError("Invalid job stop token")
    return job,gen

def stop_authenticated(connection: socket.socket,payload: bytes,*,
                       trusted_uid:int,web_uid:int,ledger:JobRecoveryLedger,
                       controller:RestrictedTargetControl)->bool:
    authenticate_peer(connection,trusted_uid=trusted_uid,web_uid=web_uid)
    job_id,generation=parse_stop(payload)
    current=ledger.get_trusted(job_id)
    if current is None or current.generation!=generation:
        raise StaleJob("Outdated or unknown job")
    if current.state in ("starting","running","orphaned"):
        current=ledger.request_stop(current)
    elif current.state!="stopping":
        raise StaleJob("Job already stopped")
    # On any exception or uncertain OS cleanup, keep owner fenced.
    if not controller.stop_verified(current):
        raise UnverifiedTarget("Cgroup not proven empty")
    ledger.confirm_stopped(current,verified_cgroup_empty=True)
    return True

