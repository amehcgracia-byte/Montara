"""Verified Montara project -> private Engine admission boundary.

The authenticated caller supplies ONLY the project UUID.  The trusted
provisioner resolves a dedicated isolated runtime, the registry validates a
physical Engine binding, and a private executor performs the actual opening.
Never mount this blueprint until the deployment has an isolation-verified
executor. No Docker, OS provider, filesystem path or worker ID crosses HTTP.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from flask import Blueprint, jsonify, request

from urano.project_catalog import ProjectCatalog, ProjectNotFound
from urano.runtime_activation import (ActivationTicket, RuntimeActivationGuard,
                                      RuntimeBusy, StaleActivation)
from urano.session_auth import SESSION_COOKIE, SessionStore


class ExecutorUnavailable(RuntimeError):
    """No verified private executor can accept this owner's project."""


class PrivateExecutor(Protocol):
    """Trusted implementation, never obtained from the HTTP request.

    `open_verified` MUST verify active Engine folder and belong to the isolated
    owner runtime. If unsuccessful or uncertain, `abort` MUST stop/reap it.
    """
    def runtime_for_owner(self, owner_id: str) -> str | None: ...
    def open_verified(self, owner_id: str, ticket: ActivationTicket) -> bool: ...
    def abort(self, owner_id: str, runtime_id: str) -> None: ...


@dataclass(frozen=True)
class OpenResult:
    project_id: str
    state: str
    generation: int


class OwnerEngineGateway:
    """Fail-closed, provider-neutral trusted Engine adapter.

    Does NOT itself provide OS isolation. Only construct with a provisioner
    that verifies UID/container boundaries, limits and project-local storage.
    """

    def __init__(self, catalog: ProjectCatalog, guard: RuntimeActivationGuard,
                 executor: PrivateExecutor):
        self.catalog, self.guard, self.executor = catalog, guard, executor

    def open_verified_owner_project(self, owner_id: str, project_id: str) -> OpenResult:
        # Check owner, including deleted / foreign projects, BEFORE looking up
        # any runtime, even if the executor claims one exists.
        self.catalog.get(owner_id, project_id)
        try:
            runtime_id = self.executor.runtime_for_owner(owner_id)
        except Exception as exc:
            raise ExecutorUnavailable("Private Engine provisioner unavailable") from exc
        if not runtime_id:
            raise ExecutorUnavailable("No private Engine worker provisioned")
        ticket = self.guard.request_open(owner_id, runtime_id, project_id)
        try:
            result = self.executor.open_verified(owner_id, ticket)
            if result is not True:
                raise ExecutorUnavailable("Private Engine did not verify opening")
        except Exception as exc:
            # No acknowledgement until the backend has conclusively torn down
            # all processes. A failed abort leaves `switching` (safe) and
            # cannot accidentally expose a half-open Engine as ready.
            try:
                self.executor.abort(owner_id, runtime_id)
            except Exception as stop_exc:
                raise ExecutorUnavailable("Private worker cleanup unverified") from stop_exc
            try:
                self.guard.acknowledge_open(owner_id, ticket, success=False)
            except StaleActivation as stale:
                raise ExecutorUnavailable("Private worker activation became stale") from stale
            raise ExecutorUnavailable("Private Engine failed to open") from exc
        self.guard.acknowledge_open(owner_id, ticket, success=True)
        return OpenResult(project_id=project_id, state="ready", generation=ticket.generation)


def owner_engine_blueprint(gateway: OwnerEngineGateway, sessions: SessionStore,
                           *, https_origin: str) -> Blueprint:
    """Optional POST-only seam; no Engine provisioner is created here."""
    bp = Blueprint("urano_owner_engine_admission", __name__, url_prefix="/urano/v1")

    @bp.post("/projects/<project_id>/open")
    def open_private_engine(project_id: str):
        if (request.host_url.rstrip("/") != https_origin or
                request.headers.get("Origin") != https_origin):
            return jsonify(error="Trusted HTTPS origin required"), 403
        if (request.content_length not in (None, 0) or
                request.headers.get("Transfer-Encoding")):
            return jsonify(error="Request body not supported"), 400
        identity = sessions.verify(request.cookies.get(SESSION_COOKIE))
        if identity is None:
            return jsonify(error="Authentication required"), 401
        if not identity.matches_csrf(request.headers.get("X-Urano-CSRF")):
            return jsonify(error="Invalid CSRF token"), 403
        try:
            result = gateway.open_verified_owner_project(identity.owner_id, project_id)
        except (ProjectNotFound, ValueError):
            return jsonify(error="Project not found"), 404
        except RuntimeBusy:
            return jsonify(error="Private Engine is busy"), 409
        except (ExecutorUnavailable, StaleActivation):
            return jsonify(error="Private Engine not available"), 503
        # Do not leak runtime IDs, Engine paths, worker UIDs or storage roots.
        response = jsonify(project_id=result.project_id, state=result.state,
                           generation=result.generation)
        response.headers["Cache-Control"] = "no-store"
        return response

    return bp
