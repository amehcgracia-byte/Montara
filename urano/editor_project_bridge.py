"""Owner-scoped project choices for the ORIGINAL JM Stage / Push / Show editor.

Read-only adapter. No extra editor, global Engine routing or new catalog.
The session identity is obtained from the trusted existing SessionStore.
"""
from __future__ import annotations

from dataclasses import asdict

from flask import Blueprint, jsonify, request

from urano.project_catalog import ProjectCatalog, ProjectNotFound
from urano.session_auth import SESSION_COOKIE, SessionStore

MODES = frozenset({"stage", "push", "show"})


def project_mode(project) -> str | None:
    """Existing I28 recipe mode; legacy/unclassified projects remain untouched."""
    workspace = project.recipe.get("montara_beta_workspace")
    if not isinstance(workspace, dict):
        return None
    mode = workspace.get("mode")
    return mode if isinstance(mode, str) and mode in MODES else None


def editor_project_bridge_blueprint(
    catalog: ProjectCatalog, sessions: SessionStore, *, https_origin: str
) -> Blueprint:
    bp = Blueprint("urano_editor_project_bridge", __name__, url_prefix="/urano/v1/editor")

    @bp.before_request
    def verified_owner():
        if request.host_url.rstrip("/") != https_origin:
            return jsonify(error="Trusted HTTPS origin required"), 403
        session = sessions.verify(request.cookies.get(SESSION_COOKIE))
        if session is None:
            return jsonify(error="Authentication required"), 401
        request.environ["montara.editor.owner"] = session.owner_id

    def owner():
        return request.environ["montara.editor.owner"]

    def public(project):
        return {
            "id": project.id,
            "title": project.title,
            "mode": project_mode(project),
            "revision": project.revision,
            "updated_at": project.updated_at,
        }

    @bp.get("/projects")
    def choices():
        mode = request.args.get("mode", "")
        if mode not in MODES:
            return jsonify(error="Choose a Stage, Push or Show mode"), 400
        return jsonify(mode=mode, projects=[
            public(project) for project in catalog.list_for(owner())
            if project_mode(project) == mode
        ])

    @bp.get("/projects/<project_id>")
    def selected(project_id: str):
        mode = request.args.get("mode", "")
        if mode not in MODES:
            return jsonify(error="Choose a Stage, Push or Show mode"), 400
        try:
            project = catalog.get(owner(), project_id)
        except (ProjectNotFound, ValueError):
            return jsonify(error="Project not found"), 404
        if project_mode(project) != mode:
            return jsonify(error="Project not found"), 404
        return jsonify(project=public(project))

    @bp.after_request
    def private(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    return bp
