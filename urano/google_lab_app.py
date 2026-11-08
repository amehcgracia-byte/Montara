"""Opt-in Google login + existing owner catalog, *not* the production Montara app.

Only invoke from a private loopback HTTPS test or an explicitly secured lab.
No password registration endpoints, no Engine endpoints, no uploaded media.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, jsonify, request, send_from_directory

from urano.google_flow import OIDCSettings, GoogleProvider, PendingLogins, google_login_blueprint
from urano.google_owner import GoogleOwnerStore
from urano.engine_bindings import EngineProjectRegistry
from urano.http_engine_status import owner_engine_status_blueprint
from urano.http_projects import project_blueprint
from urano.project_catalog import ProjectCatalog
from urano.session_auth import SESSION_COOKIE, SessionStore

_ASSETS = Path(__file__).resolve().parent / "google_lab_ui"


def create_google_lab_app(private_dir: Path, *, settings: OIDCSettings,
                          provider: GoogleProvider | None = None,
                          engine_data_root: Path | None = None) -> Flask:
    root = Path(private_dir).resolve()
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Private laboratory data directory must already exist")
    app = Flask("urano-google-isolated", static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 300_000
    sessions = SessionStore(root / "sessions.sqlite3")
    app.register_blueprint(google_login_blueprint(
        settings=settings, pending=PendingLogins(root / "pending.sqlite3"),
        owners=GoogleOwnerStore(root / "owners.sqlite3"), sessions=sessions,
        provider=provider, success_path="/urano-google-lab/"))
    catalog = ProjectCatalog(root / "projects.sqlite3")
    app.register_blueprint(project_blueprint(catalog, sessions))
    if engine_data_root is not None:
        # Operator-only opt-in. Never read this location from HTTP requests or
        # reuse the global JM/FER Engine root for customer isolation.
        registry = EngineProjectRegistry(root / "engine_bindings.sqlite3",
                                         engine_data_root, catalog)
        app.register_blueprint(owner_engine_status_blueprint(registry, sessions))
    expected = urlsplit(settings.redirect_uri)
    origin = f"{expected.scheme}://{expected.netloc}"

    @app.post("/urano-google-lab/session/refresh")
    def refresh():
        # A CSRF token is issued only to the *same-origin* page; a cross-origin
        # request cannot obtain it, even if a cookie is sent.
        if request.host_url.rstrip("/") != origin or request.headers.get("Origin") != origin:
            return jsonify(error="Same-origin HTTPS required"), 403
        token = request.cookies.get(SESSION_COOKIE)
        if sessions.verify(token) is None:
            return jsonify(error="Authentication required"), 401
        csrf = sessions.rotate_csrf(token)
        if csrf is None:
            return jsonify(error="Authentication required"), 401
        response = jsonify(csrf=csrf)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/urano-google-lab/")
    def home():
        response = send_from_directory(_ASSETS, "index.html")
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self'; form-action 'self'; "
            "base-uri 'none'; frame-ancestors 'none'")
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/urano-google-lab/<path:filename>")
    def static_asset(filename: str):
        if filename not in {"lab.js", "lab.css"}:
            return "", 404
        response = send_from_directory(_ASSETS, filename)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    return app
