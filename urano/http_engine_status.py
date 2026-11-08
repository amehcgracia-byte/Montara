"""Owner-authorized, READ-ONLY Engine binding visibility for isolated URANO lab.

This is NOT an Engine proxy. No filesystem paths, project contents, media,
activation, render, upload, or arbitrary owner IDs are exposed to clients.
Only trusted server infrastructure may provision a binding separately.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from urano.engine_bindings import EngineProjectRegistry
from urano.project_catalog import ProjectNotFound
from urano.session_auth import SESSION_COOKIE, SessionStore


def owner_engine_status_blueprint(registry: EngineProjectRegistry,
                                  sessions: SessionStore) -> Blueprint:
    bp = Blueprint("urano_owner_engine_status", __name__,
                   url_prefix="/urano/v1/projects")

    @bp.get("/<project_id>/engine")
    def engine_binding_status(project_id: str):
        verified = sessions.verify(request.cookies.get(SESSION_COOKIE))
        if verified is None:
            return jsonify(error="Authentication required"), 401
        # No browser-supplied owner or filesystem path is consulted.
        try:
            registry.resolve_internal(verified.owner_id, project_id)
        except (ProjectNotFound, ValueError):
            # Unbound and foreign projects are deliberately indistinguishable.
            return jsonify(error="Project workspace unavailable"), 404
        response = jsonify(linked=True, status="linked_not_activated",
                           engine_access=False, render_access=False)
        response.headers["Cache-Control"] = "no-store"
        return response

    return bp
