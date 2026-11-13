"""I47 strict Owner+generation proof before root grants a JM HTTP socket FD."""
from __future__ import annotations

import json

from urano.private_owner_admission import verify_owner_and_project


def verify_editor_connect_request(raw: bytes, *, owner_db_root):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 384:
        raise ValueError("Invalid Owner JM connect frame")
    try:
        packet = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Invalid Owner JM connect JSON") from exc
    if (not isinstance(packet, dict)
            or set(packet) != {"op", "session", "csrf", "project_id", "generation"}
            or packet.get("op") != "connect_editor"
            or type(packet.get("generation")) is not int
            or not 1 <= packet["generation"] <= 2**31 - 1):
        raise ValueError("Unsupported Owner JM descriptor request")
    # Exact I27 validation: independent SQLite session expiry, hashed CSRF,
    # canonical UUID and verified owner/project mapping. Never trust a caller
    # supplied owner, target unit, socket name or filesystem path.
    proof = {field: packet[field]
             for field in ("session", "csrf", "project_id")}
    proof["op"] = "ensure_owner"
    _, owner, project = verify_owner_and_project(
        json.dumps(proof, separators=(",", ":")).encode(),
        owner_db_root=owner_db_root,
    )
    return owner, project, packet["generation"]
