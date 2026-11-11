"""I33: broker-side, provider-neutral Stage snapshot handoff.

This is an in-process trusted bridge (not an HTTP, socket or systemd endpoint).
The caller MUST have independently verified the owner session in the broker.
The executor attests the exact active isolated worker before every read.

No browser-supplied worker address, unit, folder, command or owner is accepted.
"""
from __future__ import annotations

from typing import Protocol

from urano.job_recovery_ledger import JobRecoveryLedger
from urano.project_catalog import ProjectCatalog, ProjectNotFound
from urano.editor_project_bridge import project_mode
from urano.private_engine_route_contract import (
    PrivateEngineRouteDenied, VerifiedEngineBinding, plan_private_engine_request,
)


class PrivateSnapshotTransport(Protocol):
    """Trusted backend implementation; can be systemd, OCI or remote-worker.

    attest must validate actual isolation, currently running process identity
    and exact ledger-pinned target. No attestation based only on a filesystem
    readiness marker is sufficient.
    """
    def attest(self, target: str, *, project_id: str, generation: int) -> bool: ...
    def stage_snapshot(self, target: str, *, project_id: str, generation: int) -> dict: ...


_ALLOWED_STATES = frozenset({
    "pending", "idle", "queued", "running", "done",
    "failed", "blocked", "not_started",
})
_STAGES = ("ingest", "sync", "cut", "edit", "export")


def trusted_stage_snapshot(
    owner_id: str, project_id: str, *, generation: int,
    catalog: ProjectCatalog, ledger: JobRecoveryLedger,
    engine_sha: str, transport: PrivateSnapshotTransport,
) -> dict:
    """Fetch sanitized status after owner/project/worker/generation verification.

    The browser cannot construct this trust boundary. The broker resolves the
    owner from its independent session verification, pins the worker target
    from its durable ledger and supplies the deployed Engine bundle SHA.
    """
    try:
        project = catalog.get(owner_id, project_id)
    except (ProjectNotFound, ValueError) as exc:
        raise PrivateEngineRouteDenied("Project unavailable") from exc
    if project_mode(project) != "stage":
        raise PrivateEngineRouteDenied("Wrong editor mode")
    jobs = ledger.unverified_for_owner(owner_id)
    if (len(jobs) != 1 or jobs[0].state != "running"
            or jobs[0].project_id != project_id
            or type(generation) is not int or jobs[0].generation != generation):
        raise PrivateEngineRouteDenied("No matching running Engine")
    target = ledger.target_for_trusted(jobs[0])
    if target is None:
        raise PrivateEngineRouteDenied("Unreserved Engine target")
    binding = VerifiedEngineBinding(
        owner_id=jobs[0].owner_id, project_id=jobs[0].project_id,
        mode="stage", generation=jobs[0].generation,
        engine_sha=engine_sha, ready=True,
    )
    # Restrict this first feature to the same GET snapshot contract that
    # the private worker uses; no generic Engine HTTP request tunnel.
    plan_private_engine_request(
        binding, owner_id=owner_id, project_id=project_id,
        generation=generation, method="GET", path="/api/v1/project",
    )
    if transport.attest(target, project_id=project_id, generation=generation) is not True:
        raise PrivateEngineRouteDenied("Private worker attestation failed")
    reply = transport.stage_snapshot(target, project_id=project_id,
                                     generation=generation)
    # Treat the transport reply as untrusted even though its peer is verified.
    if (not isinstance(reply, dict) or reply.get("ok") is not True
            or reply.get("type") != "stage_snapshot"
            or reply.get("project") != project_id
            or set(reply) != {"ok", "type", "project", "stages", "camera_count"}):
        raise PrivateEngineRouteDenied("Invalid private Engine response")
    stages = reply["stages"]
    if (not isinstance(stages, dict) or set(stages) != set(_STAGES)
            or any(type(stages[k]) is not str or stages[k] not in _ALLOWED_STATES
                   for k in _STAGES)
            or type(reply["camera_count"]) is not int
            or not 0 <= reply["camera_count"] <= 200):
        raise PrivateEngineRouteDenied("Invalid Stage snapshot")
    # Never forward worker path, bytes, runtime IDs, UID, logs or token.
    return {
        "project_id": project_id,
        "generation": generation,
        "stages": {k: stages[k] for k in _STAGES},
        "camera_count": reply["camera_count"],
    }
