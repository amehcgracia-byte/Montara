"""Opt-in original Chema FULL JM app inside an already-isolated owner worker.

Linux/runtime adapter only. No public HTTP/TCP. Requires a root-pinned JM
bundle and an exact matching root-pinned Engine submodule. Never starts a
second Flask Engine: the original JM app creates its own genuine Engine state.

The root broker owns the lifecycle, worker UID/cgroup, auth and project fence.
This module is NOT a public server and must never be run in the shared editor.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

from urano.owner_first_stage_wizard import OwnerFirstStageWizard
from urano.private_jm_wsgi_socket import create_private_jm_wsgi_server
from urano.private_stage_payload import private_stage_snapshot
from urano.private_stage_unix_transport import serve_stage_socket


def serve_original_jm_worker(
    *, engine_root: Path, jm_root: Path, data_root: Path,
    project_id: str, generation: int, on_ready,
):
    """Blocking private WSGI worker; invoked only after root-broker launch."""
    engine_root = Path(engine_root).resolve(strict=True)
    jm_root = Path(jm_root).resolve(strict=True)
    data_root = Path(data_root).resolve(strict=True)
    if (type(generation) is not int or generation < 1
            or jm_root.is_symlink() or data_root.is_symlink()
            or (data_root.stat().st_mode & 0o077)
            or (jm_root / "engine").resolve(strict=True)
                 != (engine_root / "engine").resolve(strict=True)):
        raise ValueError("Untrusted JM/Engine runtime configuration")
    if not callable(on_ready) or not (jm_root / "app.py").is_file():
        raise ValueError("Original JM app or ready callback unavailable")
    # The worker is a fresh Python process. JM's native product modules are
    # imported only from its reviewed immutable bundle, not from main/global.
    if str(jm_root) not in sys.path:
        sys.path.insert(0, str(jm_root))
    # Treat this cloud-managed private worker as a remote JM runtime,
    # not an unrestricted desktop installation. The ORIGINAL JM uploader
    # applies its 256 MiB remote file ceiling when this marker exists.
    # Generate a per-worker nonreusable token, never accept one from HTTP.
    import secrets
    os.environ["MONTARA_SESSION_TOKEN"] = secrets.token_hex(32)
    from app import create_montara_app

    folder = data_root / "Projects" / project_id
    if folder.is_symlink() or not (folder / "project.json").is_file():
        raise ValueError("Uninitialized Owner project")
    app = create_montara_app(data_root, samples=False)
    with app.test_client() as client:
        opened = client.post(
            "/api/v1/wizard/projects/open", json={"path": str(folder)})
        verified = client.get("/api/v1/project")
        state = app.config.get("ZUCKER_STATE")
        current = getattr(getattr(state, "project", None), "folder", None)
        if (opened.status_code != 200 or verified.status_code != 200
                or not isinstance(current, (str, Path))
                or Path(current).resolve(strict=True) != folder.resolve()):
            raise RuntimeError("Original JM Engine did not open Owner project")

    # All original UI/Engine routes stay inside this process. The broker hands
    # the authorized gateway one connected descriptor per request.
    app_wsgi = OwnerFirstStageWizard(app, owner_project_folder=folder)
    server, sock_path = create_private_jm_wsgi_server(app_wsgi, data_root)
    status_ready = threading.Event()
    status_errors = []

    def status_server():
        try:
            serve_stage_socket(
                data_root, project_id=project_id, generation=generation,
                trusted_broker_uid=0,
                read_snapshot=lambda: private_stage_snapshot(
                    app.test_client(), folder),
                on_listening=status_ready.set,
            )
        except BaseException as exc:
            status_errors.append(type(exc).__name__)

    thread = threading.Thread(target=status_server, daemon=True)
    thread.start()
    try:
        if not status_ready.wait(timeout=10) or status_errors:
            raise RuntimeError("Private JM Stage-status listener failed")
        if not sock_path.is_socket():
            raise RuntimeError("Private JM HTTP listener not bound")
        on_ready()
        server.serve_forever()
    finally:
        server.server_close()
        sock_path.unlink(missing_ok=True)
