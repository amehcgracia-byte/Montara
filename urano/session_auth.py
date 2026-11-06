"""Opaque, revocable server-side sessions for a future trusted login flow.

IMPORTANT: issue() is server-only. Never expose an unauthenticated endpoint that
allows visitors to select owner_id. The account/login provider is NOT included.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from urano.project_catalog import ProjectCatalog

SESSION_COOKIE = "__Host-montara-urano"
_TOKEN_RE = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class IssuedSession:
    token: str
    csrf: str
    expires_at: int


@dataclass(frozen=True)
class VerifiedSession:
    owner_id: str
    csrf_hash: str
    expires_at: int

    def matches_csrf(self, candidate: str | None) -> bool:
        if not isinstance(candidate, str) or not _TOKEN_RE.fullmatch(candidate):
            return False
        return hmac.compare_digest(self.csrf_hash, _digest(candidate))


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


class SessionStore:
    """DB-backed opaque sessions. Only SHA256 digests are stored at rest."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        if not self.db_path.parent.is_dir():
            raise ValueError("Session database parent must exist and be private")
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS urano_auth_sessions (
                token_hash TEXT PRIMARY KEY,
                csrf_hash TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                expires_at INTEGER NOT NULL
            )""")
            db.execute("""CREATE INDEX IF NOT EXISTS urano_auth_expiry
                       ON urano_auth_sessions(expires_at)""")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.db_path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def issue(self, verified_owner_id: str, *, ttl_seconds: int = 3600,
              now: int | None = None) -> IssuedSession:
        """Called ONLY after real login validates a user; not a public route."""
        owner_id = ProjectCatalog._principal(verified_owner_id)
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 86400:
            raise ValueError("Session TTL must be 1..86400 seconds")
        timestamp = int(time.time()) if now is None else now
        token, csrf = secrets.token_hex(32), secrets.token_hex(32)
        expires_at = timestamp + ttl_seconds
        with self._connect() as db:
            db.execute("""INSERT INTO urano_auth_sessions
                       (token_hash,csrf_hash,owner_id,expires_at) VALUES(?,?,?,?)""",
                       (_digest(token), _digest(csrf), owner_id, expires_at))
        return IssuedSession(token, csrf, expires_at)

    def verify(self, token: str | None, *, now: int | None = None) -> VerifiedSession | None:
        if not isinstance(token, str) or not _TOKEN_RE.fullmatch(token):
            return None
        timestamp = int(time.time()) if now is None else now
        with self._connect() as db:
            row = db.execute("""SELECT owner_id,csrf_hash,expires_at FROM urano_auth_sessions
                                WHERE token_hash=? AND expires_at>?""",
                             (_digest(token), timestamp)).fetchone()
        if row is None:
            return None
        return VerifiedSession(row["owner_id"], row["csrf_hash"], row["expires_at"])

    def rotate_csrf(self, token: str | None, *, now: int | None = None) -> str | None:
        """Refresh CSRF after a page reload without extending session lifetime."""
        if not isinstance(token, str) or not _TOKEN_RE.fullmatch(token):
            return None
        timestamp = int(time.time()) if now is None else now
        csrf = secrets.token_hex(32)
        with self._connect() as db:
            result = db.execute("""UPDATE urano_auth_sessions SET csrf_hash=?
                    WHERE token_hash=? AND expires_at>?""",
                    (_digest(csrf), _digest(token), timestamp))
        return csrf if result.rowcount == 1 else None

    def revoke(self, token: str | None) -> None:
        if not isinstance(token, str) or not _TOKEN_RE.fullmatch(token):
            return
        with self._connect() as db:
            db.execute("DELETE FROM urano_auth_sessions WHERE token_hash=?", (_digest(token),))


def set_session_cookie(response, session: IssuedSession) -> None:
    """Secure-only cookie; domain omitted to satisfy __Host- constraints."""
    response.set_cookie(SESSION_COOKIE, session.token, secure=True, httponly=True,
                        samesite="Lax", path="/", max_age=max(0, session.expires_at - int(time.time())))
