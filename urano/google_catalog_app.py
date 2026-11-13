"""Opt-in Google Owner + existing SQLite catalog; no editor, worker or shared app.

This factory is inert until an operator explicitly mounts it on a separate
HTTPS origin. It MUST NOT be registered on the legacy Montara application.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, jsonify, redirect, request

from urano.google_flow import (
    OIDCSettings, GoogleProvider, PendingLogins, google_login_blueprint,
)
from urano.google_owner import GoogleOwnerStore
from urano.http_projects import project_blueprint
from urano.project_catalog import ProjectCatalog
from urano.session_auth import SESSION_COOKIE, SessionStore


def create_google_owner_catalog(private_dir: str | Path, *, settings: OIDCSettings,
                                provider: GoogleProvider | None = None) -> Flask:
    root = Path(private_dir)
    if root.is_symlink() or not root.is_dir() or (root.stat().st_mode & 0o077):
        raise ValueError("Pre-existing private Owner directory with mode 0700 required")
    root = root.resolve(strict=True)
    if hasattr(root.stat(), "st_uid"):
        import os
        if root.stat().st_uid != os.getuid():
            raise ValueError("Private Owner directory must belong to serving user")
    origin = urlsplit(settings.redirect_uri)
    expected_origin = f"{origin.scheme}://{origin.netloc}"

    app = Flask("montara-google-owner-catalog", static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 300_000
    sessions = SessionStore(root / "sessions.sqlite3")
    catalog = ProjectCatalog(root / "projects.sqlite3")

    @app.before_request
    def exact_host():
        # A reverse proxy must set the *trusted* HTTPS origin, not trust
        # forwarded host supplied by clients.
        if request.host_url.rstrip("/") != expected_origin:
            return jsonify(error="Untrusted Owner origin"), 403
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("Origin") != expected_origin:
                return jsonify(error="Invalid Owner origin"), 403

    app.register_blueprint(google_login_blueprint(
        settings=settings, pending=PendingLogins(root / "pending.sqlite3"),
        owners=GoogleOwnerStore(root / "owners.sqlite3"),
        sessions=sessions, provider=provider,
        success_path="/urano/v1/projects",
    ))
    app.register_blueprint(project_blueprint(catalog, sessions))

    @app.get("/")
    def entry():
        if sessions.verify(request.cookies.get(SESSION_COOKIE)) is None:
            return redirect("/urano/v1/google/start", code=302)
        return redirect("/urano/v1/projects", code=302)

    @app.post("/urano/v1/session/refresh")
    def refresh_csrf():
        token = request.cookies.get(SESSION_COOKIE)
        if sessions.verify(token) is None:
            return jsonify(error="Authentication required"), 401
        csrf = sessions.rotate_csrf(token)
        if csrf is None:
            return jsonify(error="Authentication required"), 401
        response = jsonify(csrf=csrf)
        response.headers["Cache-Control"] = "no-store"
        return response

    return app
