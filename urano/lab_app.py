"""Isolated U12b browser demonstration. NOT plugged into existing Montara app.

Explicitly lab-only: server operators must expose this solely on local loopback,
with HTTPS at a trusted test proxy if conducting browser tests. The test factory
uses Flask test_client, not an Internet-facing deployment.
"""
from __future__ import annotations

from pathlib import Path

from flask import Flask, send_from_directory

from urano.accounts import AccountStore
from urano.http_auth import auth_blueprint
from urano.http_projects import project_blueprint
from urano.project_catalog import ProjectCatalog
from urano.session_auth import SessionStore

_UI = Path(__file__).resolve().parent / "lab_ui"


def create_isolated_lab_app(private_data_dir: Path) -> Flask:
    """Opt-in factory; never call from app.py, sandbox_entry or public Vercel."""
    root = Path(private_data_dir).resolve()
    if not root.is_dir():
        raise ValueError("Create a private lab data directory first")
    app = Flask("urano-u12b-isolated", static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 300_000
    app.register_blueprint(auth_blueprint(AccountStore(root / "accounts.sqlite3"),
                                           SessionStore(root / "sessions.sqlite3")))
    app.register_blueprint(project_blueprint(ProjectCatalog(root / "projects.sqlite3"),
                                              SessionStore(root / "sessions.sqlite3")))

    @app.get("/urano-lab/")
    def lab_index():
        response = send_from_directory(_UI, "index.html")
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self'; base-uri 'none'; "
            "form-action 'self'; frame-ancestors 'none'")
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/urano-lab/<path:filename>")
    def lab_asset(filename: str):
        if filename not in {"lab.js", "lab.css"}:
            return "", 404
        response = send_from_directory(_UI, filename)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    return app
