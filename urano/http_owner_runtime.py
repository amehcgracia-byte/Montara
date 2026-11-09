"""Opt-in activation of the verified owner's pre-provisioned private Engine.

This is a lab-only control plane. Never proxy arbitrary Engine HTTP endpoints
or expose filesystem, Docker, local Companion, render or source media here.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from flask import Blueprint, jsonify, request

from urano.owner_runtime_controller import OwnerRuntimeController
from urano.companion_handoff import project_handoff, UnsafeCompanionPlan, validate_cut_list
from urano.project_catalog import ProjectCatalog, ProjectConflict
from urano.private_worker_supervisor import WorkerFailure
from urano.project_catalog import ProjectNotFound
from urano.runtime_activation import RuntimeBusy, StaleActivation
from urano.session_auth import SESSION_COOKIE, SessionStore
from urano.stage_source_provenance import StageSourceProvenance, UnverifiedSources


def owner_runtime_blueprint(controller: OwnerRuntimeController,
                            sessions: SessionStore, *, https_origin: str,
                            catalog: ProjectCatalog | None = None,
                            stage_provenance: StageSourceProvenance | None = None) -> Blueprint:
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

    @bp.get("/projects/<project_id>/state")
    def project_state(project_id: str):
        session, error = identity(False)
        if error is not None:
            return error
        try:
            current = controller.project_state(session.owner_id, project_id)
        except (ProjectNotFound, ValueError):
            return jsonify(error="Project workspace unavailable"), 404
        except (WorkerFailure, RuntimeBusy, StaleActivation, OSError):
            return jsonify(error="Private worker not ready"), 409
        return protected(jsonify(**current, render_access=False,
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

    @bp.post("/projects/<project_id>/ingest")
    def ingest_start(project_id: str):
        session, error = identity(True)
        if error is not None:
            return error
        try:
            controller.ingest_start(session.owner_id, project_id)
        except (ProjectNotFound, ValueError):
            return jsonify(error="Project workspace unavailable"), 404
        except (WorkerFailure, RuntimeBusy, StaleActivation, OSError):
            return jsonify(error="Stage Ingest unavailable"), 409
        return protected(jsonify(stage="ingest", status="accepted",
                                 render_access=False, companion_access=False)), 202

    @bp.get("/projects/<project_id>/ingest")
    def ingest_status(project_id: str):
        session, error = identity(False)
        if error is not None:
            return error
        try:
            status = controller.ingest_status(session.owner_id, project_id)
        except (ProjectNotFound, ValueError):
            return jsonify(error="Project workspace unavailable"), 404
        except (WorkerFailure, RuntimeBusy, StaleActivation, OSError):
            return jsonify(error="Stage Ingest unavailable"), 409
        return protected(jsonify(stage="ingest", status=status,
                                 render_access=False, companion_access=False))

    if catalog is not None:
        @bp.put("/projects/<project_id>/edits")
        def save_private_edits(project_id: str):
            # Strictly metadata-only, owner-verified; no raw media, paths or
            # arbitrary Engine commands enter the server over this endpoint.
            session = sessions.verify(request.cookies.get(SESSION_COOKIE))
            if session is None:
                return jsonify(error="Authentication required"), 401
            if (request.host_url.rstrip("/") != expected
                    or request.headers.get("Origin") != expected):
                return jsonify(error="HTTPS same-origin required"), 403
            if not session.matches_csrf(request.headers.get("X-Urano-CSRF")):
                return jsonify(error="Invalid CSRF token"), 403
            if request.content_length is None or request.content_length > 100000:
                return jsonify(error="Invalid edit payload size"), 413
            body = request.get_json(silent=True)
            if not isinstance(body, dict) or set(body) != {"cuts", "expected_revision"}:
                return jsonify(error="Invalid edit payload"), 400
            revision = body["expected_revision"]
            if type(revision) is not int or revision < 0:
                return jsonify(error="Invalid revision"), 400
            try:
                cuts = validate_cut_list(body["cuts"], require_nonempty=True)
                current = catalog.get(session.owner_id, project_id)
                if current.recipe and set(current.recipe) - {"urano_edits_v1", "notes"}:
                    return jsonify(error="Unsupported existing edit schema"), 409
                recipe = {"urano_edits_v1": {"cuts": cuts}}
                if isinstance(current.recipe.get("notes"), str):
                    recipe["notes"] = current.recipe["notes"]
                saved = catalog.save_recipe(session.owner_id, project_id, recipe,
                                            expected_revision=revision)
            except UnsafeCompanionPlan:
                return jsonify(error="Invalid cuts"), 400
            except (ProjectNotFound, ValueError):
                return jsonify(error="Project workspace unavailable"), 404
            except ProjectConflict:
                return jsonify(error="Project was updated elsewhere"), 409
            return protected(jsonify(project_id=saved.id, revision=saved.revision,
                                    cuts=cuts, render_ready=False))

        @bp.get("/projects/<project_id>/companion-handoff")
        def companion_handoff(project_id: str):
            session, error = identity(False)
            if error is not None:
                return error
            try:
                plan = project_handoff(catalog, session.owner_id, project_id)
            except UnsafeCompanionPlan:
                return jsonify(error="No safe Companion edit descriptor available"), 409
            except (ProjectNotFound, ValueError):
                return jsonify(error="Project workspace unavailable"), 404
            return protected(jsonify(plan=plan))

    if catalog is not None:
        @bp.get("/projects/<project_id>/verified-sources")
        def verified_sources(project_id: str):
            session, error = identity(False)
            if error is not None:
                return error
            try:
                project = catalog.get(session.owner_id, project_id)
                cuts = validate_cut_list(project.recipe.get("urano_edits_v1", {}).get("cuts"),
                                         require_nonempty=True)
                if stage_provenance is None:
                    raise UnverifiedSources("No attested Stage provenance")
                certificate = stage_provenance.verified(
                    session.owner_id, project_id,
                    source_slots={entry["source_slot"] for entry in cuts})
            except (ProjectNotFound, ValueError):
                return jsonify(error="Verified Stage sources unavailable"), 409
            return protected(jsonify(project_revision=project.revision,
                                     stage_revision=certificate["stage_revision"],
                                     sources=certificate["sources"]))

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
