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

_STATIC_EXTENSIONS = frozenset({".js", ".css", ".svg", ".png", ".webp",
                                ".jpg", ".jpeg", ".ico", ".woff2"})


def pinned_jm_static_assets(web_root: Path) -> frozenset[str]:
    """Exact static routes from a reviewed and immutable JM web bundle.

    Static manifest is constructed by trusted deployment code, NOT from a
    browser parameter. Never accept hidden, linked or user-uploaded assets.
    """
    root = Path(web_root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Reviewed JM web root unavailable")
    allowed = set()
    for candidate in root.rglob("*"):
        if candidate.is_symlink():
            raise ValueError("Linked JM UI asset forbidden")
        if not candidate.is_file():
            continue
        relative = candidate.relative_to(root)
        if (len(relative.parts) > 3
                or any(part.startswith(".") for part in relative.parts)
                or candidate.suffix.lower() not in _STATIC_EXTENSIONS):
            continue
        allowed.add("/" + relative.as_posix())
    return frozenset(allowed)


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
                 expected_uid: int, timeout: float = 5.0,
                 approved_assets: frozenset[str] = frozenset()):
        if (type(expected_pid) is not int or expected_pid <= 1
                or type(expected_uid) is not int or expected_uid < 0
                or type(timeout) not in (int, float) or not 0 < timeout <= 10):
            raise ValueError("Unverified worker identity or timeout")
        self._socket_path = Path(path)
        self._expected_pid = expected_pid
        self._expected_uid = expected_uid
        if (not isinstance(approved_assets, frozenset)
                or any(not isinstance(a, str) or not a.startswith("/")
                       for a in approved_assets)):
            raise ValueError("Static routes must be trusted manifest")
        self._approved_assets = approved_assets
        super().__init__("localhost", timeout=timeout)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

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

    def post_first_stage_json(self, path: str, body: dict):
        """Initially only the original JM first Stage wizard handoff.

        Still requires *outer* verified Owner, project and active generation.
        Videos must already be vetted proxy paths inside this worker's root.
        Never accept a client-supplied worker address or arbitrary JM route.
        """
        if path not in ("/api/v1/wizard/projects/new", "/api/v1/wizard/draft"):
            raise PermissionError("JM mutation not admitted")
        if not isinstance(body, dict):
            raise ValueError("Invalid Stage draft payload")
        import json
        try:
            encoded = json.dumps(
                body, separators=(",", ":"), allow_nan=False).encode()
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid JM editor JSON") from exc
        if len(encoded) > 256_000:
            raise ValueError("Stage draft metadata too large")
        self.request("POST", path, body=encoded, headers={
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
        })
        response = self.getresponse()
        data = response.read(1_000_001)
        if len(data) > 1_000_000:
            raise ValueError("Unbounded private JM response")
        return response.status, response.getheader("Content-Type"), data

    def get_safe_read(self, path: str):
        # This first bridge deliberately does not tunnel mutating JM requests,
        # media uploads, previews or arbitrary paths. Add reviewed policies
        # only behind the authorized root broker, never in the web app.
        if (type(path) is not str
                or path not in _INITIAL_SAFE_GETS
                   and path not in self._approved_assets):
            raise PermissionError("JM editor read not authorized")
        self.request("GET", path, headers={"Cache-Control": "no-store"})
        response = self.getresponse()
        body = response.read(1_000_001)
        if len(body) > 1_000_000:
            raise ValueError("Unbounded private JM response")
        return response.status, response.getheader("Content-Type"), body
