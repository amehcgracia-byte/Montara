"""I40: original JM Flask app over a private Linux Unix socket.

NOT a public HTTP endpoint, not a broker, and not an authorization service.
Run only inside the already-isolated per-owner worker; the broker must verify
session, project, ledger lease, unit and worker UID before forwarding anything.
A Unix WSGI socket itself DOES NOT authenticate users.
"""
from __future__ import annotations

import os
import socket
import stat
import struct
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlsplit


SOCKET_FILE = "jm-editor-http.sock"
_INITIAL_SAFE_GETS = frozenset({
    "/", "/montara/version", "/api/v1/wizard/status", "/api/v1/project",
})


def create_private_jm_wsgi_server(app, directory: Path):
    """Prepare a local original JM WSGI server; no TCP or public listener."""
    from werkzeug.serving import make_server

    directory = Path(directory)
    if (directory.is_symlink() or not directory.is_dir()
            or directory.stat().st_mode & 0o077):
        raise ValueError("Private 0700 worker directory required")
    path = directory / SOCKET_FILE
    if path.exists() or path.is_symlink():
        raise ValueError("Private JM socket already present")
    server = make_server("unix://" + str(path), 0, app, threaded=True)
    os.chmod(path, 0o600)
    return server, path


class VerifiedJMUnixConnection(HTTPConnection):
    """Test/transport-level PID+UID pinning. Broker authorizes owner separately."""

    def __init__(self, path: Path, *, expected_pid: int,
                 expected_uid: int, timeout: float = 5.0):
        if (type(expected_pid) is not int or expected_pid <= 1
                or type(expected_uid) is not int or expected_uid < 0
                or type(timeout) not in (int, float) or not 0 < timeout <= 10):
            raise ValueError("Unverified worker identity or timeout")
        self._socket_path = Path(path)
        self._expected_pid = expected_pid
        self._expected_uid = expected_uid
        super().__init__("localhost", timeout=timeout)

    def connect(self):
        path = self._socket_path
        if path.is_symlink() or path.parent.is_symlink():
            raise PermissionError("Linked JM socket rejected")
        details = path.stat()
        if not stat.S_ISSOCK(details.st_mode) or (details.st_mode & 0o077):
            raise PermissionError("Untrusted JM socket permissions")
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            connection.settimeout(self.timeout)
            connection.connect(str(path))
            peer = connection.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
            pid, uid, _ = struct.unpack("3i", peer)
            if pid != self._expected_pid or uid != self._expected_uid:
                raise PermissionError("JM worker identity changed")
            self.sock = connection
        except BaseException:
            connection.close()
            raise

    def get_safe_read(self, path: str):
        # This first bridge deliberately does not tunnel mutating JM requests,
        # media uploads, previews or arbitrary paths. Add reviewed policies
        # only behind the authorized root broker, never in the web app.
        if type(path) is not str or path not in _INITIAL_SAFE_GETS:
            raise PermissionError("JM editor read not authorized")
        self.request("GET", path, headers={"Cache-Control": "no-store"})
        response = self.getresponse()
        body = response.read(1_000_001)
        if len(body) > 1_000_000:
            raise ValueError("Unbounded private JM response")
        return response.status, response.getheader("Content-Type"), body
