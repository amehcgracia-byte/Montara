"""Owner-project-bound JM full-session IDs.

The original Chema JM stores its sessions in the authenticated Owner's
StateDirectory. This small portal-side ledger further fences access to the
exact Stage project that created each session. No original media, paths,
personal filenames or backend sockets are stored here.
"""
from __future__ import annotations

import re
import sqlite3

from urano.project_catalog import ProjectCatalog

_ID = re.compile(r"[a-f0-9]{12}\Z")


class SessionOwnershipError(LookupError):
    """A JM session does not belong to this authenticated Stage."""


class OwnerSessionBindings:
    def __init__(self, catalog: ProjectCatalog):
        self.catalog=catalog
        with catalog._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS urano_owner_jm_sessions(
                session_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT
                    (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            )""")
            db.execute("""CREATE INDEX IF NOT EXISTS urano_owner_jm_session_scope
                ON urano_owner_jm_sessions(owner_id,project_id,created_at DESC)""")

    @staticmethod
    def _id(session_id: str) -> str:
        if not isinstance(session_id,str) or not _ID.fullmatch(session_id):
            raise ValueError("Invalid private session ID")
        return session_id

    def bind(self, owner_id: str, project_id: str, session_id: str) -> None:
        owner_id=ProjectCatalog._principal(owner_id)
        project_id=ProjectCatalog._project_id(project_id)
        session_id=self._id(session_id)
        # Catalog already checks the Owner before the operation reaches here.
        # This guard also protects future non-HTTP callers of the ledger.
        self.catalog.get(owner_id,project_id)
        with self.catalog._connect() as db:
            db.execute("""INSERT INTO urano_owner_jm_sessions
                (session_id,owner_id,project_id) VALUES(?,?,?)
                ON CONFLICT(session_id) DO NOTHING""",
                (session_id,owner_id,project_id))
            row=db.execute("""SELECT owner_id,project_id
                FROM urano_owner_jm_sessions WHERE session_id=?""",
                (session_id,)).fetchone()
            if row is None or (row["owner_id"],row["project_id"]) != (
                    owner_id,project_id):
                raise SessionOwnershipError("Session is already bound to another Stage")

    def require(self, owner_id: str, project_id: str, session_id: str) -> None:
        session_id=self._id(session_id)
        with self.catalog._connect() as db:
            row=db.execute("""SELECT 1 FROM urano_owner_jm_sessions
                WHERE session_id=? AND owner_id=? AND project_id=?""",
                (session_id,ProjectCatalog._principal(owner_id),
                 ProjectCatalog._project_id(project_id))).fetchone()
        if row is None:
            raise SessionOwnershipError("Session unavailable for this Stage")

    def latest(self, owner_id: str, project_id: str) -> str | None:
        with self.catalog._connect() as db:
            row=db.execute("""SELECT session_id FROM urano_owner_jm_sessions
                WHERE owner_id=? AND project_id=?
                ORDER BY created_at DESC, session_id DESC LIMIT 1""",
                (ProjectCatalog._principal(owner_id),
                 ProjectCatalog._project_id(project_id))).fetchone()
        return row["session_id"] if row else None
