"""Trusted web adapter for one broker-authorized private JM HTTP connection.

No public route is registered. The outer Flask gateway MUST authenticate Owner,
CSRF, same-site request and project context before calling. The root broker
independently repeats session/CSRF/owner/project/generation validation.

No original-media bytes traverse this broker control channel.
"""
from __future__ import annotations

import json
import socket
from http.client import HTTPConnection
from pathlib import Path

from urano.private_editor_fd_handoff import recv_editor_fd


BROKER_SOCKET = Path("/run/montara-i27-admission/control.sock")


def authenticated_private_jm_connection(
    session: str, csrf: str, project_id: str, generation: int, *,
    control_socket: Path = BROKER_SOCKET, broker_uid: int = 0,
    timeout: float = 6.0,
) -> HTTPConnection:
    """Obtain one already-connected JM HTTP stream. All IDs are broker-checked."""
    if (not all(isinstance(item, str) and item for item in
                (session, csrf, project_id))
            or type(generation) is not int or generation < 1):
        raise ValueError("Invalid authenticated JM request")
    frame = json.dumps({
        "op": "connect_editor", "session": session,
        "csrf": csrf, "project_id": project_id, "generation": generation,
    }, separators=(",", ":")).encode()
    if len(frame) > 384:
        raise ValueError("JM authorization frame too large")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as broker:
        broker.settimeout(timeout)
        broker.connect(str(control_socket))
        broker.sendall(frame)
        worker = recv_editor_fd(
            broker, expected_broker_uid=broker_uid,
            project_id=project_id, generation=generation,
        )
    # The connected worker descriptor is owned by the HTTPConnection. It can
    # stream large requests/responses directly; no video buffering in root.
    connection = HTTPConnection("localhost", timeout=timeout)
    connection.sock = worker
    return connection
