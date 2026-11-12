"""Opt-in Owner API that displays ONLY Chema's original complete page.

This is a SMALL composition of existing Google PKCE/OIDC, Owner sessions,
catalog, root-broker gateway and pinned Chema web bundle. No dashboard,
project-picker, synthetic editor or new OAuth mechanism.

Operator must separately pin the worker launcher, source/secret storage,
Cloudflare origin and the exact JM/Engine bundles. Merely importing this
factory never changes the installed beta or starts any Engine process.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, jsonify, redirect, request

from urano.google_flow import (
    OIDCSettings, GoogleProvider, PendingLogins, google_login_blueprint,
)
from urano.google_owner import GoogleOwnerStore
from urano.native_owner_browser_surface import native_owner_browser_blueprint
from urano.native_owner_web_gateway import native_owner_gateway_blueprint
from urano.native_owner_workspace_registry import NativeOwnerWorkspaceRegistry
from urano.project_catalog import ProjectCatalog
from urano.session_auth import SESSION_COOKIE, SessionStore


def create_native_owner_api(private_dir: Path, *, settings: OIDCSettings,
                            chema_web_root: Path,
                            provider: GoogleProvider | None = None,
                            ensure_worker=None,
                            connect_worker=None) -> Flask:
    root=Path(private_dir)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Existing private Owner SQLite directory required")
    root=root.resolve(strict=True)
    web=Path(chema_web_root)
    if web.is_symlink() or not web.is_dir():
        raise ValueError("Exact original Chema web directory required")
    web=web.resolve(strict=True)
    origin_uri=urlsplit(settings.redirect_uri)
    origin=f"{origin_uri.scheme}://{origin_uri.netloc}"
    app=Flask("montara-native-chema-owner",static_folder=None)
    app.config["MAX_CONTENT_LENGTH"]=300_000
    sessions=SessionStore(root/"sessions.sqlite3")
    catalog=ProjectCatalog(root/"projects.sqlite3")
    registry=NativeOwnerWorkspaceRegistry(catalog)
    app.register_blueprint(google_login_blueprint(
        settings=settings,
        pending=PendingLogins(root/"pending.sqlite3"),
        owners=GoogleOwnerStore(root/"owners.sqlite3"),
        sessions=sessions,provider=provider,
        success_path="/urano/v1/native/"))
    app.register_blueprint(native_owner_browser_blueprint(
        sessions,https_origin=origin,web_root=web))
    bridge={}
    if ensure_worker is not None:
        bridge["ensure_worker"]=ensure_worker
    if connect_worker is not None:
        bridge["connect_worker"]=connect_worker
    app.register_blueprint(native_owner_gateway_blueprint(
        sessions,registry,https_origin=origin,**bridge))

    @app.post("/urano/v1/session/refresh")
    def refresh_csrf():
        if (request.host_url.rstrip("/")!=origin
                or request.headers.get("Origin")!=origin):
            return jsonify(error="Trusted HTTPS origin required"),403
        token=request.cookies.get(SESSION_COOKIE)
        if sessions.verify(token) is None:
            return jsonify(error="Authentication required"),401
        csrf=sessions.rotate_csrf(token)
        if csrf is None:
            return jsonify(error="Authentication required"),401
        response=jsonify(csrf=csrf)
        response.headers["Cache-Control"]="no-store"
        response.headers["X-Content-Type-Options"]="nosniff"
        return response

    @app.get("/")
    def front():
        if request.host_url.rstrip("/")!=origin:
            return jsonify(error="Trusted HTTPS origin required"),403
        if sessions.verify(request.cookies.get(SESSION_COOKIE)):
            return redirect("/urano/v1/native/",code=302)
        return redirect("/urano/v1/google/start",code=302)

    @app.get("/healthz")
    def health():
        # Liveness, not a claim that the private broker is healthy or that
        # Stage/Mixer/Companion E2E is certified.
        return jsonify(ok=True,component="native-owner-portal")

    @app.after_request
    def no_private_cache(response):
        if request.path.startswith("/urano/v1/"):
            response.headers["Cache-Control"]="private, no-store"
            response.headers["X-Content-Type-Options"]="nosniff"
        return response

    return app
