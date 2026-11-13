"""Isolated Google Authorization Code + PKCE login for URANO LAB only.

Never mount this blueprint on the shared Engine or main Montara application.
Only the fixed Google endpoints are used in the real HTTP adapter. Tests inject
a synthetic provider; no live Google access or credentials are necessary.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

from flask import Blueprint, jsonify, redirect, request

from urano.google_oidc import GoogleIdentityDenied, verify_google_id_token
from urano.google_owner import GoogleOwnerStore
from urano.session_auth import SESSION_COOKIE, SessionStore, set_session_cookie

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
FLOW_COOKIE = "__Host-montara-oidc-flow"
FLOW_TTL = 600


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _new_pkce_verifier() -> str:
    return _b64(secrets.token_bytes(48))


def _https_redirect(uri: str) -> str:
    parsed = urlsplit(uri)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or not parsed.path.endswith("/google/callback")):
        raise ValueError("Exact HTTPS callback URI required")
    return uri


@dataclass(frozen=True)
class OIDCSettings:
    client_id: str
    client_secret: str
    redirect_uri: str
    allowed_emails: frozenset[str]

    def __post_init__(self):
        _https_redirect(self.redirect_uri)
        if not isinstance(self.client_id, str) or not self.client_id.strip():
            raise ValueError("Missing Google Client ID")
        if not isinstance(self.client_secret, str) or not self.client_secret.strip():
            raise ValueError("Missing Google client secret")
        if not isinstance(self.allowed_emails, frozenset) or not self.allowed_emails:
            raise ValueError("Explicit nonempty beta allowlist required")


class PendingLogins:
    """Persistent, atomic, one-time OAuth transaction store."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        if not self.db_path.parent.is_dir():
            raise ValueError("Private OAuth DB parent must exist")
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS urano_oidc_pending (
                state_hash TEXT PRIMARY KEY,
                binding_hash TEXT NOT NULL,
                verifier TEXT NOT NULL,
                nonce TEXT NOT NULL,
                expires_at INTEGER NOT NULL
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS urano_oidc_expiry ON urano_oidc_pending(expires_at)")

    def _connect(self):
        db = sqlite3.connect(str(self.db_path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def begin(self, binding: str, *, now: int | None = None):
        timestamp = int(time.time()) if now is None else now
        state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), _new_pkce_verifier()
        with self._connect() as db:
            db.execute("DELETE FROM urano_oidc_pending WHERE expires_at <= ?", (timestamp,))
            db.execute("INSERT INTO urano_oidc_pending VALUES (?,?,?,?,?)",
                       (_digest(state), _digest(binding), verifier, nonce, timestamp + FLOW_TTL))
        return state, nonce, verifier

    def consume(self, state: str, binding: str | None, *, now: int | None = None):
        if not isinstance(state, str) or not 24 <= len(state) <= 128:
            return None
        valid_binding = isinstance(binding, str) and 24 <= len(binding) <= 128
        timestamp = int(time.time()) if now is None else now
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM urano_oidc_pending WHERE state_hash=?",
                             (_digest(state),)).fetchone()
            # Consume even when binding does not match; never enable replay.
            db.execute("DELETE FROM urano_oidc_pending WHERE state_hash=?", (_digest(state),))
            if (row is None or row["expires_at"] <= timestamp
                    or not valid_binding
                    or not hmac.compare_digest(row["binding_hash"], _digest(binding))):
                return None
            return row["verifier"], row["nonce"]


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GoogleProvider:
    """Fixed Google HTTPS endpoints, bounded responses; no user-provided URLs."""

    @staticmethod
    def _json_from(url: str, *, data: bytes | None = None) -> dict:
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
        opener = build_opener(_NoRedirects())
        with opener.open(req, timeout=8) as response:
            if response.status != 200:
                raise GoogleIdentityDenied("Google identity provider rejected request")
            raw = response.read(262145)
        if len(raw) > 262144:
            raise GoogleIdentityDenied("Identity provider response too large")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise GoogleIdentityDenied("Invalid provider response")
        return result

    def exchange(self, code: str, verifier: str, settings: OIDCSettings) -> str:
        body = urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "client_id": settings.client_id,
            "client_secret": settings.client_secret,
            "redirect_uri": settings.redirect_uri,
            "code_verifier": verifier,
        }).encode("ascii")
        result = self._json_from(GOOGLE_TOKEN_URL, data=body)
        token = result.get("id_token")
        if not isinstance(token, str):
            raise GoogleIdentityDenied("Google did not provide an ID token")
        return token

    def jwks(self) -> dict:
        return self._json_from(GOOGLE_JWKS_URL)


def google_login_blueprint(*, settings: OIDCSettings, pending: PendingLogins,
                           owners: GoogleOwnerStore, sessions: SessionStore,
                           provider: GoogleProvider | None = None,
                           success_path: str = "/urano/v1/projects") -> Blueprint:
    """Opt-in only; mount in a distinct lab app behind trusted HTTPS origin."""
    provider = GoogleProvider() if provider is None else provider
    # Do not accept a target from a browser/query string or arbitrary URL.
    if not isinstance(success_path, str) or not success_path.startswith("/") or success_path.startswith("//") or "\\\\" in success_path or "?" in success_path or "#" in success_path:
        raise ValueError("Local fixed success path required")
    bp = Blueprint("urano_google_oidc_lab", __name__, url_prefix="/urano/v1/google")
    callback = settings.redirect_uri
    expected_origin = f"{urlsplit(callback).scheme}://{urlsplit(callback).netloc}"

    @bp.before_request
    def require_exact_origin():
        # No spoofable X-Forwarded-Host/Proto values accepted. Reverse proxy must
        # explicitly define trusted Host/scheme before this app is ever exposed.
        if request.host_url.rstrip("/") != expected_origin:
            return jsonify(error="Incorrect laboratory origin"), 403
        if request.content_length is not None and request.content_length > 4096:
            return jsonify(error="Payload too large"), 413

    @bp.get("/start")
    def start():
        # Fresh binding per attempt prevents login CSRF and avoids stale attempts.
        binding = secrets.token_urlsafe(32)
        state, nonce, verifier = pending.begin(binding)
        challenge = _b64(hashlib.sha256(verifier.encode("ascii")).digest())
        params = {
            "response_type": "code", "client_id": settings.client_id,
            "redirect_uri": callback, "scope": "openid email",
            "state": state, "nonce": nonce,
            "code_challenge": challenge, "code_challenge_method": "S256",
            # On the private beta always show Google's account chooser. It
            # prevents Chrome's currently active, non-allowlisted account
            # being silently selected. This does not bypass OAuth allowlists.
            "prompt": "select_account",
        }
        response = redirect(GOOGLE_AUTH_URL + "?" + urlencode(params), code=302)
        response.set_cookie(FLOW_COOKIE, binding, secure=True, httponly=True,
                            samesite="Lax", path="/", max_age=FLOW_TTL)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @bp.get("/callback")
    def callback_handler():
        # Reject duplicated/ambiguous query parameters. State is consumed once
        # before the token exchange and irrespective of verification success.
        state = request.args.getlist("state")
        code = request.args.getlist("code")
        binding = request.cookies.get(FLOW_COOKIE)
        result = None
        if len(state) == 1:
            result = pending.consume(state[0], binding)
        if len(state) != 1 or len(code) != 1 or not code[0] or len(code[0]) > 4096 or result is None:
            response = jsonify(error="Login authorization rejected")
            response.status_code = 401
        else:
            verifier, nonce = result
            try:
                token = provider.exchange(code[0], verifier, settings)
                identity = verify_google_id_token(
                    token, client_id=settings.client_id, expected_nonce=nonce,
                    jwks=provider.jwks(),
                )
                owner_id = owners.resolve_beta_owner(identity, allowed_emails=settings.allowed_emails)
                # H4 private beta: owner-requested ten-day sessions for iterative
                # testing. Sessions remain revocable, HttpOnly, SameSite=Lax.
                issued = sessions.issue(owner_id, ttl_seconds=10*86400)
            except (GoogleIdentityDenied, ValueError, KeyError, HTTPError, URLError,
                    TimeoutError, UnicodeError, json.JSONDecodeError):
                response = jsonify(error="Google authentication unavailable or denied")
                response.status_code = 401
            else:
                old_session = request.cookies.get(SESSION_COOKIE)
                response = redirect(success_path, code=303)
                set_session_cookie(response, issued)
                sessions.revoke(old_session)
        response.delete_cookie(FLOW_COOKIE, secure=True, httponly=True, samesite="Lax", path="/")
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    return bp
