"""Trusted-only reconciliation of separately authenticated Montara owners.

This is a storage primitive, NOT an HTTP login, a mail verifier, or evidence
that matching email strings grant access. Only trusted auth components may
register verified identities or issue owner proof grants.  No API is mounted.
"""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
import time
from pathlib import Path

from urano.accounts import normalize_email
from urano.project_catalog import ProjectCatalog


class LinkDenied(ValueError):
    """Invalid, conflicting, expired or unproven ownership link."""


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


class OwnerIdentityLinks:
    """Reconcile proven old owner IDs in the SAME SQLite DB as their projects.

    Linking project rows and owner aliases in one transaction prevents a crash
    from orphaning project data. Provider identity bind is trusted-only; caller
    MUST have completed a genuine provider login / email-possession check.
    """

    def __init__(self, project_database: str | Path):
        self.path = Path(project_database)
        if not self.path.parent.is_dir():
            raise ValueError("Existing private project database parent required")
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS urano_verified_identities (
              provider TEXT NOT NULL, subject TEXT NOT NULL, owner_id TEXT NOT NULL,
              PRIMARY KEY (provider, subject)
            );
            CREATE INDEX IF NOT EXISTS urano_verified_identities_owner
              ON urano_verified_identities(owner_id);
            CREATE TABLE IF NOT EXISTS urano_verified_emails (
              owner_id TEXT NOT NULL, email TEXT NOT NULL,
              PRIMARY KEY (owner_id, email)
            );
            CREATE TABLE IF NOT EXISTS urano_owner_aliases (
              alias_id TEXT PRIMARY KEY, canonical_id TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS urano_link_grants (
              token_sha256 TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
              expires_at INTEGER NOT NULL
            );
            """)

    def _connect(self):
        db = sqlite3.connect(str(self.path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _owner(value):
        return ProjectCatalog._principal(value)

    @staticmethod
    def _identity(provider, subject):
        if provider not in ("google", "password") or not isinstance(subject, str):
            raise LinkDenied("Unsupported verified identity")
        if not 1 <= len(subject) <= 255 or not subject.isascii() or "\x00" in subject:
            raise LinkDenied("Invalid identity subject")
        return provider, subject

    @staticmethod
    def _canonical(db, owner_id):
        current, visited = owner_id, set()
        while True:
            if current in visited:
                raise LinkDenied("Owner identity cycle")
            visited.add(current)
            row = db.execute("SELECT canonical_id FROM urano_owner_aliases WHERE alias_id=?", (current,)).fetchone()
            if row is None:
                return current
            current = row["canonical_id"]

    def bind_verified_identity(self, owner_id: str, provider: str, subject: str,
                               *, verified_email: str | None = None) -> str:
        """Trusted server-only, AFTER authenticating provider or email password.

        Same email is recorded as a hint but is NEVER an automatic link.
        Existing provider subject cannot be rebound to another owner.
        """
        owner_id = self._owner(owner_id)
        provider, subject = self._identity(provider, subject)
        email = normalize_email(verified_email) if verified_email is not None else None
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            canonical = self._canonical(db, owner_id)
            existing = db.execute("SELECT owner_id FROM urano_verified_identities WHERE provider=? AND subject=?",
                                  (provider, subject)).fetchone()
            if existing and self._canonical(db, existing["owner_id"]) != canonical:
                raise LinkDenied("Provider identity belongs to another owner")
            if not existing:
                db.execute("INSERT INTO urano_verified_identities VALUES (?,?,?)", (provider, subject, canonical))
            if email is not None:
                db.execute("INSERT OR IGNORE INTO urano_verified_emails VALUES (?,?)", (canonical, email))
            return canonical

    def resolve(self, provider: str, subject: str) -> str | None:
        provider, subject = self._identity(provider, subject)
        with self._connect() as db:
            row = db.execute("SELECT owner_id FROM urano_verified_identities WHERE provider=? AND subject=?",
                             (provider, subject)).fetchone()
            return self._canonical(db, row["owner_id"]) if row else None

    def issue_link_grant(self, authenticated_owner_id: str, *, now: int | None = None) -> str:
        """Only call after recent independent login for THIS owner.

        Neither grant nor source/target owner is ever accepted from an
        unauthenticated browser. Grants are opaque, short-lived, one-use.
        """
        owner = self._owner(authenticated_owner_id)
        timestamp = int(time.time()) if now is None else int(now)
        token = secrets.token_hex(32)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if self._canonical(db, owner) != owner:
                raise LinkDenied("Reauthenticate with canonical owner")
            db.execute("DELETE FROM urano_link_grants WHERE expires_at<=?", (timestamp,))
            db.execute("INSERT INTO urano_link_grants VALUES (?,?,?)", (_digest(token), owner, timestamp+300))
        return token

    def link_proven_owners(self, canonical_owner_id: str, other_owner_id: str,
                           canonical_grant: str, other_grant: str,
                           *, now: int | None = None) -> str:
        """Trusted-only two-party link; migrate all project rows atomically.

        Caller is responsible for checking interactive user consent, fresh
        authentication for BOTH owner IDs, and revoking stale sessions after
        successful reconciliation. Titles are NOT deduplicated; UUIDs survive.
        """
        target, source = self._owner(canonical_owner_id), self._owner(other_owner_id)
        if target == source:
            raise LinkDenied("Two different owners required")
        grants = (canonical_grant, other_grant)
        if any(not isinstance(g, str) or len(g) != 64 or
               any(ch not in "0123456789abcdef" for ch in g) for g in grants):
            raise LinkDenied("Invalid proof")
        timestamp = int(time.time()) if now is None else int(now)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if self._canonical(db, target) != target or self._canonical(db, source) != source:
                raise LinkDenied("Already linked; reauthenticate")
            for owner, grant in ((target, canonical_grant), (source, other_grant)):
                found = db.execute("SELECT owner_id,expires_at FROM urano_link_grants WHERE token_sha256=?",
                                   (_digest(grant),)).fetchone()
                if not found or found["owner_id"] != owner or found["expires_at"] <= timestamp:
                    raise LinkDenied("Both fresh identity proofs are required")
            db.execute("DELETE FROM urano_link_grants WHERE token_sha256 IN (?,?)",
                       (_digest(canonical_grant), _digest(other_grant)))
            # Require ProjectCatalog to have already initialised its schema.
            db.execute("UPDATE urano_projects SET owner_id=? WHERE owner_id=?", (target, source))
            db.execute("UPDATE urano_verified_identities SET owner_id=? WHERE owner_id=?", (target, source))
            db.execute("INSERT OR IGNORE INTO urano_verified_emails(owner_id,email) SELECT ?,email FROM urano_verified_emails WHERE owner_id=?",
                       (target, source))
            db.execute("DELETE FROM urano_verified_emails WHERE owner_id=?", (source,))
            db.execute("UPDATE urano_owner_aliases SET canonical_id=? WHERE canonical_id=?", (target, source))
            db.execute("INSERT INTO urano_owner_aliases VALUES (?,?)", (source, target))
            db.execute("DELETE FROM urano_link_grants WHERE owner_id IN (?,?)", (target,source))
        return target
