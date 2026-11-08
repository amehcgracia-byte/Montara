"""Opt-in activation of the verified owner's pre-provisioned private Engine.

This is a lab-only control plane. Never proxy arbitrary Engine HTTP endpoints
or expose filesystem, Docker, local Companion, render or source media here.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from flask import Blueprint, jsonify, request

from urano.owner_runtime_controller import OwnerRuntimeController
from urano.private_worker_supervisor import WorkerFailure
from urano.project_catalog import ProjectNotFound
from urano.runtime_activation import RuntimeBusy, StaleActivation
from urano.session_auth import SESSION_COOKIE, SessionStore


def owner_runtime_blueprint(controller: OwnerRuntimeController,
                            sessions: SessionStore, *, https_origin: str) -> Blueprint:
    origin = urlsplit(https_origin)
    if (origin.scheme != "https" or not origin.netloc
            or origin.path or origin.query or origin.fragment
            or origin.username or origin.password):
        raise ValueError("Require exact HTTPS origin without credentials or paths")
    expected = f"https://{origin.netloc}"
    if expected != https_origin:
        raise ValueError("Require canonical HTTPS origin")
    bp = Blueprint("urano_owner_private_runtime", __name__,
                   url_prefix="/urano/v1/runtime")

    def identity(write: bool):
        session = sessions.verify(request.cookies.get(SESSION_COOKIE))
        if session is None:
            return None, (jsonify(error="Authentication required"), 401)
        if (request.host_url.rstrip("/") != expected
                or (write and request.headers.get("Origin") != expected)):
            return None, (jsonify(error="HTTPS same-origin required"), 403)
        if write and not session.matches_csrf(request.headers.get("X-Urano-CSRF")):
            return None, (jsonify(error="Invalid CSRF token"), 403)
        if write and ((request.content_length or 0) > 0 or request.is_json):
            return None, (jsonify(error="No request payload accepted"), 400)
        return session, None

    def protected(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @bp.get("/state")
    def state():
        session, error = identity(False)
        if error is not None:
            return error
        try:
            current = controller.state(session.owner_id)
        except (ProjectNotFound, ValueError):
            return jsonify(error="Private worker unavailable"), 404
        return protected(jsonify(state=current, render_access=False,
                                 companion_access=False))

    @bp.post("/projects/<project_id>/activate")
    def activate(project_id: str):
        session, error = identity(True)
        if error is not None:
            return error
        try:
            controller.activate(session.owner_id, project_id)
        except (ProjectNotFound, ValueError):
            # Project foreign, unbound and worker missing are indistinguishable.
            return jsonify(error="Project workspace unavailable"), 404
        except (WorkerFailure, RuntimeBusy, StaleActivation, OSError):
            return jsonify(error="Private worker not ready"), 409
        return protected(jsonify(state="ready", render_access=False,
                                 companion_access=False))

    @bp.post("/close")
    def close():
        session, error = identity(True)
        if error is not None:
            return error
        try:
            controller.close(session.owner_id)
        except (ProjectNotFound, ValueError):
            return jsonify(error="Private worker unavailable"), 404
        except (WorkerFailure, RuntimeBusy, StaleActivation, OSError):
            return jsonify(error="Worker shutdown not confirmed"), 409
        return protected(jsonify(state="idle", render_access=False,
                                 companion_access=False))

    return bp
