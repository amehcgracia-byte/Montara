"""Private C8 Google owner UI entrypoint.

This is the *real* C1 Google OIDC / verified-owner catalog and dashboard,
not the single-user classic editor on port 8114. It starts without any Engine
worker until infrastructure registers it through the trusted-only controller.
No mock login, fake users or public project creation.

A separate, authorized HTTPS reverse proxy must set a verified WSGI HTTPS
scheme. This module does not trust arbitrary X-Forwarded-* request headers.
"""
from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify, redirect, request

from urano.c6_beta_preflight import validate_beta_settings
from urano.minimal_owner_api import create_owner_api
from urano.session_auth import SESSION_COOKIE, SessionStore


def create_private_owner_beta(
    env: dict[str, str] | None = None,
    *,
    provider=None,
    runtime_controller=None,
    stage_provenance=None,
    proxy_staging_root=None,
    receipt_verifier=None,
) -> Flask:
    """Build an opt-in Google-only owner portal, never a global Engine app."""
    config = dict(os.environ) if env is None else dict(env)
    preflight = validate_beta_settings(config)
    root = Path(config.get("MONTARA_OWNER_PRIVATE_DIR", ""))
    if (not root.is_absolute() or root.is_symlink() or not root.is_dir()
            or root == Path("/") or root.stat().st_mode & 0o077):
        raise ValueError("Operator must provision a private 0700 owner data root")
    if hasattr(os, "getuid") and root.stat().st_uid != os.getuid():
        raise ValueError("Private owner storage belongs to another process account")
    # I3 deliberately does not provision Engine or proxy ingestion. The actual
    # multi-owner worker/provenance integration is a later, separate reviewed PR.
    if (runtime_controller is not None or proxy_staging_root is not None
            or receipt_verifier is not None or stage_provenance is not None):
        raise ValueError("Private Engine and proxy inbox require a later trusted integration")

    app = create_owner_api(
        root, settings=preflight.settings, provider=provider,
        enable_dashboard=True,
    )
    origin = preflight.origin

    @app.before_request
    def owner_portal_origin():
        # Never infer authority from X-Forwarded-* supplied by a browser.
        # The operator must terminate TLS in a trusted reverse proxy and
        # provide scheme/Host as actual WSGI properties, not raw headers.
        if request.host_url.rstrip("/") != origin:
            return jsonify(error="Trusted HTTPS beta origin required"), 403
        if request.headers.get("X-Forwarded-Host") or request.headers.get("X-Forwarded-Proto"):
            return jsonify(error="Untrusted forwarding metadata"), 403

    @app.get("/")
    def owner_home():
        session = SessionStore(root / "sessions.sqlite3").verify(
            request.cookies.get(SESSION_COOKIE))
        return redirect("/urano/v1/dashboard" if session else
                        "/urano/v1/google/start", code=303)

    @app.get("/healthz")
    def owner_healthz():
        # This does not disclose owner IDs, Google settings or Engine state.
        return jsonify(service="montara-owner-beta", authenticated=False,
                       engine_provisioned=False,
                       public_multiuser_ready=False)

    @app.after_request
    def no_cache_owner_beta(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    return app


def main() -> None:
    """For deployment use a reviewed TLS proxy and Gunicorn factory only."""
    raise SystemExit("Use a reviewed TLS reverse proxy and WSGI factory; no embedded dev server")


# Importing this module never reads secrets or starts a public listener.
