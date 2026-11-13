"""I36: strict read-only Owner Stage admission inside the privileged broker.

The browser may send a generation but never an owner, target unit, Engine path
or machine-specific address. Session, CSRF, owner and project are reverified
from the broker's READ-ONLY private SQLite mount, independently of Flask.
"""
from __future__ import annotations

import json
import uuid

from urano.private_owner_admission import verify_owner_and_project, _read_db, OwnerAdmissionDenied
from urano.project_catalog import ProjectCatalog, ProjectNotFound


def verify_stage_owner_request(raw: bytes, *, owner_db_root):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 384:
        raise ValueError("Invalid private Stage read frame")
    try:
        packet = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Invalid private Stage read JSON") from exc
    if (not isinstance(packet, dict)
            or set(packet) != {"op", "session", "csrf", "project_id", "generation"}
            or packet["op"] != "stage_snapshot_owner"
            or type(packet["generation"]) is not int
            or not 1 <= packet["generation"] <= 2**31 - 1):
        raise ValueError("Unsupported private Stage read operation")
    # Reuse the exact established authenticated admission mechanism, preserving
    # its session expiry, rotated CSRF, symlink and project ownership checks.
    proof = {key: packet[key] for key in ("session", "csrf", "project_id")}
    proof["op"] = "open_owner"
    _, owner, project = verify_owner_and_project(
        json.dumps(proof, separators=(",", ":")).encode(),
        owner_db_root=owner_db_root,
    )
    return owner, project, packet["generation"]


class ReadOnlyOwnerCatalog:
    """A trusted owner catalog view with no schema creation or mutations."""

    def __init__(self, owner_db_root):
        from pathlib import Path
        self.db_path = Path(owner_db_root) / "projects.sqlite3"

    def get(self, owner_id, project_id):
        ProjectCatalog._principal(owner_id)
        ProjectCatalog._project_id(project_id)
        if self.db_path.is_symlink() or not self.db_path.is_file():
            raise ProjectNotFound("Private owner store unavailable")
        with _read_db(self.db_path) as db:
            row = db.execute(
                "SELECT * FROM urano_projects WHERE owner_id=? AND project_id=?",
                (owner_id, project_id),
            ).fetchone()
        if row is None:
            raise ProjectNotFound("Project not found")
        return ProjectCatalog._to_project(row)
