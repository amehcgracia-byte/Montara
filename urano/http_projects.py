"""Owner-protected HTTP catalog API. Not mounted on the existing Montara app.

Only the opaque session cookie authenticates; owner/client headers are ignored.
Issue sessions from a trusted login provider, never from request JSON.
"""
from __future__ import annotations

from dataclasses import asdict

from flask import Blueprint, jsonify, request

from urano.project_catalog import ProjectCatalog, ProjectConflict, ProjectNotFound
from urano.session_auth import SESSION_COOKIE, SessionStore


def project_blueprint(catalog: ProjectCatalog, sessions: SessionStore) -> Blueprint:
    bp = Blueprint("urano_project_contract", __name__, url_prefix="/urano/v1")

    @bp.before_request
    def verified_request():
        if request.content_length is not None and request.content_length > 300_000:
            return jsonify(error="Payload too large"), 413
        token = request.cookies.get(SESSION_COOKIE)
        identity = sessions.verify(token)
        if identity is None:
            return jsonify(error="Authentication required"), 401
        # Cross-site HTML forms and forged cross-origin requests must not mutate.
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if not identity.matches_csrf(request.headers.get("X-Urano-CSRF")):
                return jsonify(error="Invalid CSRF token"), 403
        request.environ["montara.urano.principal"] = identity.owner_id

    def owner() -> str:
        return request.environ["montara.urano.principal"]

    @bp.get("/projects")
    def list_projects():
        return jsonify(projects=[asdict(p) for p in catalog.list_for(owner())])

    @bp.post("/projects")
    def create_project():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(error="JSON object required"), 400
        try:
            created = catalog.create(owner(), body.get("title"))
        except ValueError:
            return jsonify(error="Invalid project title"), 400
        return jsonify(project=asdict(created)), 201

    @bp.get("/projects/<project_id>")
    def get_project(project_id: str):
        try:
            return jsonify(project=asdict(catalog.get(owner(), project_id)))
        except (ProjectNotFound, ValueError):
            return jsonify(error="Project not found"), 404

    @bp.put("/projects/<project_id>/recipe")
    def save_recipe(project_id: str):
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(error="JSON object required"), 400
        try:
            project = catalog.save_recipe(owner(), project_id, body.get("recipe"),
                                         expected_revision=body.get("expected_revision"))
        except (ProjectNotFound, ValueError) as exc:
            if isinstance(exc, ProjectNotFound) or "project identifier" in str(exc).lower():
                return jsonify(error="Project not found"), 404
            return jsonify(error="Invalid recipe or revision"), 400
        except ProjectConflict:
            return jsonify(error="Project was updated elsewhere"), 409
        return jsonify(project=asdict(project))

    @bp.post("/logout")
    def logout():
        sessions.revoke(request.cookies.get(SESSION_COOKIE))
        response = jsonify(ok=True)
        response.delete_cookie(SESSION_COOKIE, secure=True, httponly=True, samesite="Lax", path="/")
        return response

    return bp
