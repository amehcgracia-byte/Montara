"""Server-side mapping from verified Google sub to URANO's existing owner IDs.

Opt-in beta only. Never map a Google login to a password account by email.
Email allowlisting is checked at every login and does not prove data ownership.
"""
from __future__ import annotations

import hmac
import sqlite3
import uuid
from pathlib import Path

from urano.accounts import normalize_email
from urano.google_oidc import GoogleIdentity, GoogleIdentityDenied


class GoogleOwnerStore:
    """Persistent provider-sub mapping; no media, OAuth tokens or email stored."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        if not self.db_path.parent.is_dir():
            raise ValueError("Create a private database parent first")
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS urano_google_owners (
                google_sub TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL UNIQUE
            )""")

    def _connect(self):
        db = sqlite3.connect(str(self.db_path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def resolve_beta_owner(self, identity: GoogleIdentity, *,
                           allowed_emails: frozenset[str]) -> str:
        """Called ONLY with a verified ID token and an operator allowlist.

        The allowlist must come from private server configuration. In particular,
        the browser may not submit `allowed_emails`, `google_sub`, or `owner_id`.
        """
        if not isinstance(identity, GoogleIdentity):
            raise GoogleIdentityDenied("Verified Google identity required")
        try:
            email = normalize_email(identity.email)
        except ValueError as exc:
            raise GoogleIdentityDenied("Invalid verified Google email") from exc
        if not isinstance(allowed_emails, frozenset) or not any(
                isinstance(item, str) and hmac.compare_digest(email, item)
                for item in allowed_emails):
            raise GoogleIdentityDenied("This Google account is not enabled for beta")
        if not isinstance(identity.sub, str) or not 1 <= len(identity.sub) <= 255 or not identity.sub.isascii():
            raise GoogleIdentityDenied("Invalid verified Google subject")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT owner_id FROM urano_google_owners WHERE google_sub=?",
                             (identity.sub,)).fetchone()
            if row:
                return str(row["owner_id"])
            owner = str(uuid.uuid4())
            db.execute("INSERT INTO urano_google_owners(google_sub,owner_id) VALUES(?,?)",
                       (identity.sub, owner))
            return owner
