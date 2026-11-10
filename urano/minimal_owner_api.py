"""Small opt-in Google identity → EXISTING URANO project catalog API.

This is an API-only seam for the beta architecture, NOT a second editor,
a web-facing deployment command, a worker provisioner or a Google mock login.
The existing Montara app and its routes remain untouched.

The only way to establish owner_id is a Google ID token validated by the
trusted server-side Authorization Code + PKCE flow.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, jsonify, request

from urano.google_flow import OIDCSettings, GoogleProvider, PendingLogins, google_login_blueprint
from urano.google_owner import GoogleOwnerStore
from urano.owner_dashboard import owner_dashboard_blueprint
from urano.http_projects import project_blueprint
from urano.project_catalog import ProjectCatalog
from urano.session_auth import SESSION_COOKIE, SessionStore


def create_owner_api(private_dir: Path, *, settings: OIDCSettings,
                     provider: GoogleProvider | None = None,
                     enable_dashboard: bool = False) -> Flask:
    root = Path(private_dir).resolve()
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Existing private database directory required")
    app = Flask("montara-owner-only-api", static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 300_000
    session_store = SessionStore(root / "sessions.sqlite3")
    app.register_blueprint(google_login_blueprint(
        settings=settings,
        pending=PendingLogins(root / "pending.sqlite3"),
        owners=GoogleOwnerStore(root / "owners.sqlite3"),
        sessions=session_store,
        provider=provider,
        success_path="/urano/v1/dashboard" if enable_dashboard else "/urano/v1/projects",
    ))
    catalog = ProjectCatalog(root / "projects.sqlite3")
    app.register_blueprint(project_blueprint(catalog, session_store))
    url = urlsplit(settings.redirect_uri)
    allowed_origin = f"{url.scheme}://{url.netloc}"
    if enable_dashboard:
        app.register_blueprint(owner_dashboard_blueprint(session_store, https_origin=allowed_origin))

    @app.post("/urano/v1/session/refresh")
    def refresh_csrf():
        # Cross-site calls cannot retrieve a CSRF token from their cookie.
        if (request.host_url.rstrip("/") != allowed_origin
                or request.headers.get("Origin") != allowed_origin):
            return jsonify(error="Trusted HTTPS origin required"), 403
        token = request.cookies.get(SESSION_COOKIE)
        if session_store.verify(token) is None:
            return jsonify(error="Authentication required"), 401
        csrf = session_store.rotate_csrf(token)
        if csrf is None:
            return jsonify(error="Authentication required"), 401
        response = jsonify(csrf=csrf)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.after_request
    def private_cache(response):
        if request.path.startswith("/urano/v1/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    return app
