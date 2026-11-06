"""Opt-in lab signup/login routes; never registered on production application.

Authentication establishes the trusted identity consumed by U11 session routes.
Requires same-origin POST, and issues Secure/HttpOnly cookie only after password
registration or verification. Email possession is NOT verified in this lab.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from flask import Blueprint, jsonify, request

from urano.accounts import AccountStore, DuplicateAccount, LoginDenied
from urano.session_auth import SESSION_COOKIE, SessionStore, set_session_cookie


def auth_blueprint(accounts: AccountStore, sessions: SessionStore) -> Blueprint:
    bp = Blueprint("urano_lab_auth", __name__, url_prefix="/urano/v1")

    @bp.before_request
    def same_origin_post():
        if request.content_length is not None and request.content_length > 8_192:
            return jsonify(error="Payload too large"), 413
        # Browser mutation endpoint: require an explicit, matching Origin.
        # A reverse proxy must pass trusted Host/scheme, never arbitrary X-Forwarded-*.
        raw = request.headers.get("Origin", "")
        try:
            origin = urlsplit(raw)
        except ValueError:
            return jsonify(error="Same-origin request required"), 403
        if (not raw or origin.scheme != "https" or
            origin.netloc.lower() != request.host.lower() or
            origin.path or origin.query or origin.fragment):
            return jsonify(error="Same-origin HTTPS required"), 403

    @bp.post("/register")
    def register():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(error="JSON object required"), 400
        try:
            owner_id = accounts.register(body.get("email"), body.get("password"))
        except DuplicateAccount:
            return jsonify(error="Registration unavailable"), 409
        except ValueError:
            return jsonify(error="Invalid registration details"), 400
        issued = sessions.issue(owner_id)
        response = jsonify(csrf=issued.csrf, expires_at=issued.expires_at)
        response.status_code = 201
        response.headers["Cache-Control"] = "no-store"
        set_session_cookie(response, issued)
        return response

    @bp.post("/login")
    def login():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(error="JSON object required"), 400
        try:
            owner_id = accounts.verify(body.get("email"), body.get("password"))
        except LoginDenied:
            return jsonify(error="Invalid credentials"), 401
        issued = sessions.issue(owner_id)
        response = jsonify(csrf=issued.csrf, expires_at=issued.expires_at)
        response.headers["Cache-Control"] = "no-store"
        set_session_cookie(response, issued)
        return response

    @bp.post("/session/refresh")
    def refresh_session():
        """Restore page CSRF after reload; cookie alone authenticates this endpoint.

        Only a same-origin HTTPS request can trigger a rotation. The existing
        expiry is unchanged; older CSRF values become invalid.
        """
        token = request.cookies.get(SESSION_COOKIE)
        identity = sessions.verify(token)
        if identity is None:
            return jsonify(error="Authentication required"), 401
        csrf = sessions.rotate_csrf(token)
        if csrf is None:
            return jsonify(error="Authentication required"), 401
        response = jsonify(csrf=csrf, expires_at=identity.expires_at)
        response.headers["Cache-Control"] = "no-store"
        return response

    return bp
