"""Provider-neutral authorization plus Linux AF_UNIX FD handoff for JM media.

The privileged broker authorizes a verified Owner+project+generation, checks
the actual isolated worker identity, connects once to its private HTTP socket,
and passes that *already connected* file descriptor to the trusted web gateway.

The broker NEVER reads, buffers or proxies media bytes. The gateway forwards
HTTP on the handed-off socket. No arbitrary paths, worker IDs, URLs or hosts
are accepted from browsers. Linux/systemd-specific checks are isolated here.
"""
from __future__ import annotations

import array
import json
import os
import socket
import stat
import struct
from dataclasses import dataclass
from pathlib import Path

from urano.job_recovery_ledger import JobRecoveryLedger
from urano.private_engine_route_contract import PrivateEngineRouteDenied
from urano.restricted_systemd_broker import expected_cgroup
from urano.private_jm_wsgi_socket import SOCKET_FILE


MAX_REPLY = 512


@dataclass
class EditorFdLease:
    """Broker-owned connected worker socket. Must be closed after sendmsg."""

    project_id: str
    generation: int
    connection: socket.socket

    def close(self) -> None:
        self.connection.close()


def open_verified_editor_socket(
    ledger: JobRecoveryLedger, inspect_unit, *,
    owner_id: str, project_id: str, generation: int,
    runtime_root: Path = Path("/run"), timeout: float = 4.0,
) -> EditorFdLease:
    """Fail closed before root connects to a worker's private JM HTTP socket."""
    if type(generation) is not int or generation < 1:
        raise PrivateEngineRouteDenied("Invalid Owner worker generation")
    leases = ledger.unverified_for_owner(owner_id)
    if (len(leases) != 1 or leases[0].state != "running"
            or leases[0].project_id != project_id
            or leases[0].generation != generation):
        raise PrivateEngineRouteDenied("No matching private JM worker")
    unit = ledger.target_for_trusted(leases[0])
    if unit is None:
        raise PrivateEngineRouteDenied("Unreserved JM worker")
    expected = expected_cgroup(unit)
    details = inspect_unit(unit)
    if (not isinstance(details, dict)
            or details.get("ActiveState") != "active"
            or details.get("ControlGroup") != expected):
        raise PrivateEngineRouteDenied("Private JM worker not active")
    try:
        main_pid = int(details.get("MainPID", "0"))
    except (TypeError, ValueError) as exc:
        raise PrivateEngineRouteDenied("Unverified worker PID") from exc
    if main_pid <= 1:
        raise PrivateEngineRouteDenied("Unverified worker PID")
    root = Path(runtime_root)
    directory = root / unit
    path = directory / SOCKET_FILE
    if (root.is_symlink() or directory.is_symlink()
            or path.is_symlink() or not directory.is_dir()):
        raise PrivateEngineRouteDenied("Untrusted worker runtime path")
    try:
        info = path.stat()
        directory_info = directory.stat()
    except OSError as exc:
        raise PrivateEngineRouteDenied("Private JM socket missing") from exc
    if (not stat.S_ISSOCK(info.st_mode)
            or (info.st_mode & 0o077)
            or (directory_info.st_mode & 0o077)
            or info.st_uid == 0):
        raise PrivateEngineRouteDenied("Private JM socket permissions invalid")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.settimeout(timeout)
        sock.connect(str(path))
        raw = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED,
                              struct.calcsize("3i"))
        pid, uid, _ = struct.unpack("3i", raw)
        if pid != main_pid or uid != info.st_uid or uid == 0:
            raise PrivateEngineRouteDenied("JM worker identity mismatch")
        return EditorFdLease(project_id, generation, sock)
    except BaseException:
        sock.close()
        raise


def send_editor_fd(control: socket.socket, lease: EditorFdLease) -> None:
    """Single small JSON+SCM_RIGHTS frame; payload never contains media."""
    frame = json.dumps({
        "ok": True, "project_id": lease.project_id,
        "generation": lease.generation, "fd": True,
    }, separators=(",", ":")).encode() + b"\n"
    if len(frame) > MAX_REPLY:
        raise ValueError("Editor FD frame too large")
    anc = [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
            array.array("i", [lease.connection.fileno()]).tobytes())]
    try:
        written = control.sendmsg([frame], anc)
        if written != len(frame):
            raise OSError("Partial private JM descriptor response")
    finally:
        lease.close()


def recv_editor_fd(control: socket.socket, *, expected_broker_uid: int,
                   project_id: str, generation: int) -> socket.socket:
    """Trusted gateway receives one connected worker FD from known root broker.

    Caller MUST have independently authorized the browser session and ensure
    the exact project before calling; the broker repeats those checks.
    """
    raw = control.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED,
                             struct.calcsize("3i"))
    broker_pid, broker_uid, _ = struct.unpack("3i", raw)
    if (broker_pid <= 0 or broker_uid != expected_broker_uid
            or type(generation) is not int or generation < 1):
        raise PrivateEngineRouteDenied("Untrusted broker peer")
    data, ancillary, flags, _ = control.recvmsg(
        MAX_REPLY, socket.CMSG_SPACE(struct.calcsize("i") * 4),
        getattr(socket, "MSG_CMSG_CLOEXEC", 0))
    received = []
    for level, kind, cmsg_data in ancillary:
        if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
            numbers = array.array("i")
            numbers.frombytes(cmsg_data[:len(cmsg_data) -
                                       len(cmsg_data) % numbers.itemsize])
            received.extend(numbers)
    try:
        if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
            raise PrivateEngineRouteDenied("Truncated broker response")
        if len(received) != 1 or not data.endswith(b"\n"):
            raise PrivateEngineRouteDenied("Missing or excessive JM descriptors")
        frame = json.loads(data)
        if (not isinstance(frame, dict)
                or set(frame) != {"ok", "project_id", "generation", "fd"}
                or frame["ok"] is not True or frame["fd"] is not True
                or frame["project_id"] != project_id
                or type(frame["generation"]) is not int
                or frame["generation"] != generation):
            raise PrivateEngineRouteDenied("Wrong private JM descriptor binding")
        return socket.socket(fileno=received.pop())
    except (ValueError, TypeError, UnicodeError) as exc:
        raise PrivateEngineRouteDenied("Malformed broker descriptor") from exc
    finally:
        for fd in received:
            os.close(fd)
