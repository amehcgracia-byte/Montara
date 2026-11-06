"""Lab-only password authentication for URANO; email is NOT verified.

This module never accepts a client-supplied owner identifier. Accounts are
generated server-side; passwords are salted and hashed with scrypt.
Production requires email verification, abuse controls and recovery design.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
import time
import uuid
from pathlib import Path

_EMAIL_RE = re.compile(r"^[a-z0-9][a-z0-9._+\-]{0,63}@[a-z0-9][a-z0-9.\-]{0,190}\.[a-z]{2,24}$")
_SALT_BYTES = 16
_N = 2**14
_R = 8
_P = 1
_MAX_FAILURES = 5
_LOCK_SECONDS = 15 * 60


class DuplicateAccount(ValueError):
    """Account already registered."""


class LoginDenied(ValueError):
    """Invalid credentials or temporarily locked account."""


def normalize_email(email: str) -> str:
    if not isinstance(email, str) or len(email) > 254:
        raise ValueError("Invalid email")
    value = email.strip().lower()
    if not _EMAIL_RE.fullmatch(value) or ".." in value:
        raise ValueError("Invalid email")
    return value


def check_password_shape(password: str) -> None:
    if not isinstance(password, str) or not (12 <= len(password) <= 256):
        raise ValueError("Password must contain 12-256 characters")
    if "\x00" in password:
        raise ValueError("Invalid password")


def _hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=32)


# Precomputed once per process to reduce obvious missing-account timing differences.
_DUMMY_SALT = b"montara-urano-v1"
_DUMMY_HASH = _hash_password("not-an-account-password", _DUMMY_SALT)


class AccountStore:
    """Persistent account/password verifier; separate from opaque sessions."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        if not self.db_path.parent.is_dir():
            raise ValueError("Account database parent must already exist")
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS urano_accounts (
                owner_id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_salt BLOB NOT NULL,
                password_hash BLOB NOT NULL,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until INTEGER NOT NULL DEFAULT 0
            )""")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.db_path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def register(self, email: str, password: str) -> str:
        email = normalize_email(email)
        check_password_shape(password)
        salt = secrets.token_bytes(_SALT_BYTES)
        digest = _hash_password(password, salt)
        owner_id = str(uuid.uuid4())
        try:
            with self._connect() as db:
                db.execute("""INSERT INTO urano_accounts
                         (owner_id,email,password_salt,password_hash) VALUES(?,?,?,?)""",
                           (owner_id, email, salt, digest))
        except sqlite3.IntegrityError as exc:
            raise DuplicateAccount("Email already registered") from exc
        return owner_id

    def verify(self, email: str, password: str, *, now: int | None = None) -> str:
        # Callers return generic errors; never report whether email exists.
        try:
            email = normalize_email(email)
        except ValueError as exc:
            raise LoginDenied("Invalid credentials") from exc
        if not isinstance(password, str) or len(password) > 256:
            raise LoginDenied("Invalid credentials")
        timestamp = int(time.time()) if now is None else now
        with self._connect() as db:
            # Transaction also serializes concurrent failure increments.
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM urano_accounts WHERE email=?", (email,)).fetchone()
            if row is None:
                hmac.compare_digest(_hash_password(password, _DUMMY_SALT), _DUMMY_HASH)
                raise LoginDenied("Invalid credentials")
            if row["locked_until"] > timestamp:
                raise LoginDenied("Invalid credentials")
            ok = hmac.compare_digest(_hash_password(password, row["password_salt"]), row["password_hash"])
            if not ok:
                failed = row["failed_attempts"] + 1
                lock_until = timestamp + _LOCK_SECONDS if failed >= _MAX_FAILURES else 0
                db.execute("""UPDATE urano_accounts SET failed_attempts=?,locked_until=?
                              WHERE owner_id=?""", (failed, lock_until, row["owner_id"]))
                raise LoginDenied("Invalid credentials")
            db.execute("""UPDATE urano_accounts SET failed_attempts=0,locked_until=0
                          WHERE owner_id=?""", (row["owner_id"],))
            return row["owner_id"]
