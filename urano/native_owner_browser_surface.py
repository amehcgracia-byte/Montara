"""Owner-authenticated Chema ORIGINAL page, with no alternative navigation.

The page is the exact pinned Chema HTML with ONE removable control-plane
script before its own scripts. Music/Video, Stage/Push/Show, New and Latest
stay in their original positions. The public service must independently
configure real Google sessions and the explicit private RPC bridge.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from flask import Blueprint, Response, abort, make_response, request

from urano.private_jm_wsgi_socket import pinned_jm_static_assets
from urano.session_auth import SESSION_COOKIE, SessionStore


def native_owner_browser_blueprint(sessions: SessionStore, *,
                                   https_origin: str, web_root: Path) -> Blueprint:
    root = Path(web_root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Reviewed original Chema web root required")
    root = root.resolve(strict=True)
    original = root / "index.html"
    if original.is_symlink() or not original.is_file():
        raise ValueError("Reviewed Chema index missing")
    manifest = pinned_jm_static_assets(root)
    anchor = '<script src="mix-levels.js"></script>'
    html = original.read_text(encoding="utf-8")
    if (html.count(anchor) != 1 or
            html.count('id="newVideo" data-go="mode"') != 1 or
            html.count('id="sessionResume"') != 1 or
            html.count('data-platform="youtube"') != 1 or
            html.count('data-platform="reel"') != 1 or
            html.count('data-platform="show"') != 1):
        raise ValueError("Pinned Chema UX anchors changed; re-audit required")

    # One external adapter only. No owner header, dashboard, project picker,
    # modified New/Latest controls, shortcut Stage, or HTML fragments.
    edited = html.replace(anchor,
        '<script src="owner-bridge.js"></script>\n' + anchor, 1)
    digests = {
        name: hashlib.sha256((root / name.lstrip("/")).read_bytes()).digest()
        for name in manifest
    }
    original_digest = hashlib.sha256(original.read_bytes()).digest()
    bp = Blueprint("urano_native_owner_browser", __name__,
                   url_prefix="/urano/v1/native")

    @bp.before_request
    def private_owner_only():
        if request.host_url.rstrip("/") != https_origin:
            abort(403)
        if sessions.verify(request.cookies.get(SESSION_COOKIE)) is None:
            abort(401)

    def safe_response(data: bytes | str, mimetype: str):
        response = Response(data, mimetype=mimetype)
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @bp.get("/")
    def original_chema_page():
        if hashlib.sha256(original.read_bytes()).digest() != original_digest:
            abort(503)
        return safe_response(edited, "text/html")

    @bp.get("/owner-bridge.js")
    def owner_adapter():
        # This file is the ONLY new browser behavior and never changes the
        # global original JM source or any private Owner project files.
        path = Path(__file__).with_name("native_owner_browser_bridge.js")
        if path.is_symlink() or not path.is_file():
            abort(503)
        return safe_response(path.read_bytes(), "application/javascript")

    @bp.get("/<path:filename>")
    def original_chema_asset(filename: str):
        selected = "/" + filename
        if selected not in manifest:
            abort(404)
        path = root / filename
        if (path.is_symlink() or not path.is_file()
                or path.resolve(strict=True) != root / filename
                or hashlib.sha256(path.read_bytes()).digest() != digests[selected]):
            abort(503)
        suffix = path.suffix.lower()
        types = {
            ".js": "application/javascript", ".css": "text/css",
            ".svg": "image/svg+xml", ".png": "image/png",
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".ico": "image/x-icon",
            ".woff2": "font/woff2",
        }
        mimetype = types.get(suffix)
        if mimetype is None:
            abort(404)
        return safe_response(path.read_bytes(), mimetype)

    return bp
