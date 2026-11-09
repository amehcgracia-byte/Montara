"""C6 beta preflight: explicit HTTPS origin, real Google OIDC configuration.

Pure validation, never starts a listener, provisions a VM or calls Google.
Secrets are read only from an operator-owned private file, not web headers,
browser inputs or logs. Deploying remains a separately authorized C7 step.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from urano.google_flow import OIDCSettings

_EMAIL = re.compile(r"^[^\s@,]+@[^\s@,.]+(?:\.[^\s@,.]+)+$")
_CLIENT = re.compile(r"^[0-9]+-[a-zA-Z0-9_-]+\.apps\.googleusercontent\.com$")


@dataclass(frozen=True)
class BetaPreflight:
    origin: str
    settings: OIDCSettings


def validate_beta_origin(origin: str) -> str:
    """Canonical public HTTPS origin; no wildcard, path, query or credentials."""
    if not isinstance(origin, str) or len(origin) > 255 or origin != origin.strip():
        raise ValueError("A single canonical HTTPS beta origin is required")
    parsed = urlsplit(origin)
    if (parsed.scheme != "https" or not parsed.hostname or not parsed.netloc
            or parsed.username or parsed.password or parsed.path
            or parsed.query or parsed.fragment or parsed.hostname in
            {"localhost", "127.0.0.1"} or parsed.hostname.endswith(".localhost")
            or "*" in origin or chr(92) in origin or parsed.hostname.endswith(".")):
        raise ValueError("Public exact HTTPS hostname required")
    if parsed.port not in (None, 443):
        raise ValueError("Only standard HTTPS port is allowed for beta")
    if parsed.port == 443:
        raise ValueError("Write canonical HTTPS origins without explicit port 443")
    return origin


def validate_beta_settings(env: dict[str, str]) -> BetaPreflight:
    origin = validate_beta_origin(env.get("MONTARA_BETA_ORIGIN", ""))
    if env.get("MONTARA_COMPANION_BETA_ORIGIN") != origin:
        raise ValueError("Companion must have exactly the same paired HTTPS origin")
    client = env.get("MONTARA_GOOGLE_CLIENT_ID", "")
    if not _CLIENT.fullmatch(client):
        raise ValueError("Google OAuth web client ID is missing or malformed")
    emails = env.get("MONTARA_BETA_ALLOWED_EMAILS", "")
    allow = emails.split(",") if emails else []
    if (not allow or len(allow) > 25 or any(
            not _EMAIL.fullmatch(v) or v != v.strip() or v.lower() != v
            for v in allow) or len(set(allow)) != len(allow)):
        raise ValueError("Explicit lower-case beta email allowlist required")
    file_name = env.get("MONTARA_GOOGLE_SECRET_FILE", "")
    if not file_name or not Path(file_name).is_absolute():
        raise ValueError("Google secret must come from an absolute private file")
    secret_path = Path(file_name)
    if secret_path.is_symlink() or not secret_path.is_file():
        raise ValueError("Google secret file unavailable")
    if os.name != "nt" and secret_path.stat().st_mode & 0o077:
        raise ValueError("Google secret file must not be group/world-readable")
    if secret_path.stat().st_size > 4096:
        raise ValueError("Google secret file is unexpectedly large")
    secret = secret_path.read_text(encoding="utf-8").strip()
    if not secret or len(secret) > 4096 or any(ch.isspace() for ch in secret):
        raise ValueError("Invalid Google OAuth client secret")
    settings = OIDCSettings(
        client_id=client,
        client_secret=secret,
        redirect_uri=origin + "/urano/v1/google/callback",
        allowed_emails=frozenset(allow),
    )
    return BetaPreflight(origin=origin, settings=settings)
