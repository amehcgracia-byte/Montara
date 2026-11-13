"""I27: independently authorize a verified Owner session/project inside broker.

This is a privileged LOCAL authorization boundary, not an HTTP endpoint.
Root broker mounts only the C8 owner-private SQLite directory read-only.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import sqlite3
import time
import uuid
from pathlib import Path

_TOKEN = re.compile(r"[a-f0-9]{64}\Z")
_OWNEROPS = frozenset({"open_owner", "close_owner", "ensure_owner", "status_owner"})


class OwnerAdmissionDenied(PermissionError):
    """No session, no CSRF or foreign project. Never disclose owner IDs."""


def parse_owner_request(raw: bytes) -> tuple[str,str,str,str]:
    if not isinstance(raw,bytes) or len(raw)>384 or not raw:
        raise ValueError("Invalid request size")
    value=json.loads(raw)
    if (not isinstance(value,dict) or set(value)!={"op","session","csrf","project_id"}
        or value["op"] not in _OWNEROPS
        or not isinstance(value["session"],str) or not _TOKEN.fullmatch(value["session"])
        or not isinstance(value["csrf"],str) or not _TOKEN.fullmatch(value["csrf"])
        or not isinstance(value["project_id"],str)):
        raise ValueError("Invalid private owner operation")
    try:
        project=uuid.UUID(value["project_id"])
    except (ValueError,AttributeError,TypeError) as exc:
        raise ValueError("Invalid project UUID") from exc
    if str(project)!=value["project_id"]:
        raise ValueError("Noncanonical project UUID")
    return value["op"],value["session"],value["csrf"],value["project_id"]


def _read_db(path: Path):
    # No schema changes or SQL writes to the Owner database.
    uri="file:"+str(path)+"?mode=ro"
    connection=sqlite3.connect(uri,uri=True,timeout=4)
    connection.row_factory=sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def verify_owner_and_project(raw: bytes, *, owner_db_root: Path,
                             now: int | None=None) -> tuple[str,str,str]:
    op,session,csrf,project_id=parse_owner_request(raw)
    root=Path(owner_db_root)
    if (not root.is_dir() or root.is_symlink()
        or (root/"sessions.sqlite3").is_symlink()
        or (root/"projects.sqlite3").is_symlink()):
        raise OwnerAdmissionDenied("Owner store unavailable")
    token_hash=hashlib.sha256(session.encode("ascii")).hexdigest()
    csrf_hash=hashlib.sha256(csrf.encode("ascii")).hexdigest()
    clock=int(time.time()) if now is None else now
    with _read_db(root/"sessions.sqlite3") as conn:
        identity=conn.execute("""SELECT owner_id,csrf_hash
            FROM urano_auth_sessions WHERE token_hash=? AND expires_at>?""",
            (token_hash,clock)).fetchone()
    if (identity is None or not hmac.compare_digest(identity["csrf_hash"],csrf_hash)):
        raise OwnerAdmissionDenied("Session unavailable")
    with _read_db(root/"projects.sqlite3") as conn:
        project=conn.execute("""SELECT 1 FROM urano_projects
            WHERE owner_id=? AND project_id=?""",
            (identity["owner_id"],project_id)).fetchone()
    if project is None:
        raise OwnerAdmissionDenied("Project unavailable")
    return op,identity["owner_id"],project_id

