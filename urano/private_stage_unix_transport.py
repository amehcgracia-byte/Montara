"""I34 experimental real Unix-domain Stage snapshot transport.

Backend adapter for a Linux systemd DynamicUser worker, not Montara Core.
No TCP listener, HTTP proxy, provider dependency, browser-supplied unit or paths.
Do NOT deploy: service wiring and actual multi-user media still need validation.
"""
from __future__ import annotations

import json
import os
import socket
import stat
import struct
from pathlib import Path
from typing import Callable

from urano.private_engine_route_contract import PrivateEngineRouteDenied
from urano.restricted_systemd_broker import expected_cgroup


SOCKET_NAME = "stage-read.sock"
MAX_FRAME = 2048
STAGE_OP = "stage_snapshot"


def _peer(sock: socket.socket) -> tuple[int, int, int]:
    size = struct.calcsize("3i")
    return struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, size))


def _read_line(sock: socket.socket, limit: int) -> dict:
    data = bytearray()
    while len(data) <= limit:
        part = sock.recv(min(512, limit + 1 - len(data)))
        if not part:
            break
        data.extend(part)
        if b"\n" in part:
            break
    if len(data) > limit or not data.endswith(b"\n") or data.count(b"\n") != 1:
        raise PrivateEngineRouteDenied("Invalid private worker frame")
    try:
        result = json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise PrivateEngineRouteDenied("Invalid worker JSON") from exc
    if not isinstance(result, dict):
        raise PrivateEngineRouteDenied("Invalid worker packet")
    return result


def serve_stage_socket(
    directory: Path, *, project_id: str, generation: int,
    read_snapshot: Callable[[], dict], trusted_broker_uid: int = 0,
    max_requests: int | None = None,
) -> None:
    """Worker-side blocking loop, run only after isolated Engine project opens.

    Trusted broker credential is kernel SO_PEERCRED, never a client header.
    Caller controls lifetime with systemd cgroup termination (not HTTP).
    """
    directory = Path(directory)
    if (directory.is_symlink() or not directory.is_dir()
            or type(generation) is not int or generation < 1
            or type(trusted_broker_uid) is not int or trusted_broker_uid < 0):
        raise ValueError("Untrusted Stage socket configuration")
    path = directory / SOCKET_NAME
    if path.exists() or path.is_symlink():
        raise ValueError("Stage socket already exists")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(path))
        os.chmod(path, 0o600)
        server.listen(4)
        completed = 0
        try:
            while max_requests is None or completed < max_requests:
                conn, _ = server.accept()
                with conn:
                    conn.settimeout(3.0)
                    completed += 1
                    try:
                        pid, uid, _ = _peer(conn)
                        if pid <= 0 or uid != trusted_broker_uid:
                            raise PrivateEngineRouteDenied("Unauthorized broker")
                        packet = _read_line(conn, MAX_FRAME)
                        if (set(packet) != {"op", "project_id", "generation"}
                                or packet.get("op") != STAGE_OP
                                or packet.get("project_id") != project_id
                                or type(packet.get("generation")) is not int
                                or packet["generation"] != generation):
                            raise PrivateEngineRouteDenied("Worker binding mismatch")
                        result = read_snapshot()
                        if not isinstance(result, dict):
                            raise PrivateEngineRouteDenied("No Stage status")
                        response = result
                    except (PrivateEngineRouteDenied, ValueError, OSError):
                        response = {"ok": False, "error": "Stage unavailable"}
                    encoded = json.dumps(response, separators=(",", ":"), allow_nan=False).encode()
                    if len(encoded) > MAX_FRAME - 1:
                        encoded = b'{"ok":false,"error":"Stage unavailable"}'
                    try:
                        conn.sendall(encoded + b"\n")
                    except (BrokenPipeError, ConnectionResetError):
                        pass
        finally:
            path.unlink(missing_ok=True)


class SystemdUnixStageTransport:
    """Concrete adapter behind the provider-neutral PrivateSnapshotTransport.

    Systemd inspection is injected and must be root-broker trusted.
    No cgroup/UID selection or address is obtained from an HTTP caller.
    """

    def __init__(self, inspect: Callable[[str], dict], *,
                 runtime_root: Path = Path("/run"),
                 timeout: float = 3.0):
        self.inspect = inspect
        self.runtime_root = Path(runtime_root)
        if not 0.1 <= timeout <= 5.0:
            raise ValueError("Invalid private IPC timeout")
        self.timeout = timeout

    def _identity(self, target: str) -> tuple[int, int, Path]:
        expected = expected_cgroup(target)
        info = self.inspect(target)
        if (not isinstance(info, dict)
                or info.get("ActiveState") != "active"
                or info.get("ControlGroup") != expected):
            raise PrivateEngineRouteDenied("Private unit unavailable")
        try:
            pid = int(info.get("MainPID", "0"))
        except (ValueError, TypeError) as exc:
            raise PrivateEngineRouteDenied("No worker PID") from exc
        if pid <= 1:
            raise PrivateEngineRouteDenied("No live worker")
        directory = self.runtime_root / target
        path = directory / SOCKET_NAME
        if (self.runtime_root.is_symlink() or directory.is_symlink()
                or not directory.is_dir() or path.is_symlink()):
            raise PrivateEngineRouteDenied("Untrusted private socket path")
        try:
            st = path.stat()
        except OSError as exc:
            raise PrivateEngineRouteDenied("Worker socket unavailable") from exc
        if not stat.S_ISSOCK(st.st_mode) or (st.st_mode & 0o077):
            raise PrivateEngineRouteDenied("Worker socket access too broad")
        return pid, st.st_uid, path

    def attest(self, target: str, *, project_id: str, generation: int) -> bool:
        # The full owner/project/generation binding is verified by the caller
        # against the ledger; the socket process is checked again on every read.
        self._identity(target)
        return True

    def stage_snapshot(self, target: str, *, project_id: str, generation: int) -> dict:
        pid, uid, path = self._identity(target)
        packet = json.dumps({
            "op": STAGE_OP, "project_id": project_id, "generation": generation
        }, separators=(",", ":")).encode() + b"\n"
        if len(packet) > MAX_FRAME:
            raise PrivateEngineRouteDenied("Private request too large")
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(self.timeout)
                client.connect(str(path))
                peer_pid, peer_uid, _ = _peer(client)
                if peer_pid != pid or peer_uid != uid or peer_uid == 0:
                    raise PrivateEngineRouteDenied("Worker process identity changed")
                client.sendall(packet)
                result = _read_line(client, MAX_FRAME)
        except (OSError, TimeoutError) as exc:
            raise PrivateEngineRouteDenied("Private worker unavailable") from exc
        return result
