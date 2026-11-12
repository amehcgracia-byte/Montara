"""Native Chema app over the EXISTING private Owner Unix transports.

This is an opt-in worker-side seam, not a new broker, UI or web server.
An authorized systemd worker supplies the immutable app_factory, the
private WSGI socket server and the root-credentialled Stage status listener.
The browser can neither call this function nor select the workspace ID.

The body reuses the tested app mount, native New/Latest and runtime IPC.
There is intentionally no pre-opened UUID-shaped Chema project.
"""
from __future__ import annotations

import socket
import stat
import threading
from pathlib import Path
from typing import Callable

from urano.native_owner_worker_binding import bind_native_owner_application


class NativeOwnerSocketUnavailable(RuntimeError):
    """The private Unix transport is not ready to accept owner requests."""


def serve_native_owner_workspace(
    *, app_factory: Callable,
    data_root: Path,
    runtime_root: Path,
    workspace_id: str,
    generation: int,
    make_private_server: Callable,
    serve_stage_socket: Callable,
    on_ready: Callable,
    ready_timeout: float = 10,
) -> None:
    """Serve Chema over private Unix sockets until root-broker stops the unit.

    Existing implementations are passed as make_private_server and
    serve_stage_socket by the reviewed full JM worker; do not copy them.
    """
    runtime = Path(runtime_root)
    if (runtime.is_symlink() or not runtime.is_dir()
            or runtime.stat().st_mode & 0o077):
        raise NativeOwnerSocketUnavailable("Private runtime directory required")
    if (type(generation) is not int or generation < 1
            or not callable(make_private_server)
            or not callable(serve_stage_socket)
            or not callable(on_ready)
            or not 0.1 <= ready_timeout <= 30):
        raise NativeOwnerSocketUnavailable("Unverified worker lifecycle")
    runtime = runtime.resolve(strict=True)
    app, read_snapshot = bind_native_owner_application(
        app_factory=app_factory, data_root=data_root,
        workspace_id=workspace_id,
    )

    server, socket_path = make_private_server(app, runtime)
    socket_path = Path(socket_path)
    ready = threading.Event()
    errors: list[str] = []

    def listen() -> None:
        try:
            serve_stage_socket(
                runtime, project_id=workspace_id, generation=generation,
                read_snapshot=read_snapshot, trusted_broker_uid=0,
                on_listening=ready.set,
            )
        except BaseException as exc:
            errors.append(type(exc).__name__)
            ready.set()

    thread = threading.Thread(
        target=listen, daemon=True, name="montara-private-stage-status",
    )
    thread.start()
    try:
        if not ready.wait(timeout=ready_timeout) or errors or not thread.is_alive():
            raise NativeOwnerSocketUnavailable("Private Stage status unavailable")
        stage_socket = runtime / "stage-read.sock"
        for path in (socket_path, stage_socket):
            if (path.parent != runtime or path.is_symlink()
                    or not path.is_socket()
                    or not stat.S_ISSOCK(path.stat().st_mode)
                    or path.stat().st_mode & 0o077):
                raise NativeOwnerSocketUnavailable("Unverified private worker socket")
        # Only the root-broker-supervised caller can publish ready.json;
        # it does so after *both* private transports have been verified.
        on_ready()
        server.serve_forever()
    finally:
        server.server_close()
        socket_path.unlink(missing_ok=True)
