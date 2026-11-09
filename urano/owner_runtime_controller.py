"""U19: trusted session-owner -> existing private Docker Engine bridge.

Infrastructure, NEVER a public factory, provisions each owner with a dedicated
bridge/worker. Browser selects a catalog UUID only. No media, Docker parameters,
paths, or rendering exposed through these operations.
"""
from __future__ import annotations

from threading import RLock
from pathlib import Path

from urano.container_worker_bridge import ContainerWorkerBridge
from urano.project_catalog import ProjectCatalog, ProjectNotFound
from urano.private_worker_supervisor import WorkerFailure
from urano.runtime_activation import RuntimeBusy, StaleActivation
from urano.trusted_stage_inputs import prepare_trusted_stage_inputs
from urano.stage_source_provenance import StageSourceProvenance, UnverifiedSources
from urano.stage_ingest_attestation import attest_authenticated_inbox


class OwnerRuntimeController:
    """Narrow isolated-lab adapter over the already tested U13 worker bridge.

    One bridge per owner. No shared global Engine. Runtime registration is
    process-local trusted provisioning; not a remotely writable catalogue.
    """

    def __init__(self):
        self._workers: dict[str, ContainerWorkerBridge] = {}
        self._owner_locks: dict[str, RLock] = {}
        self._lock = RLock()
        # Trusted-only opt-in; never configured from HTTP, cookies, or uploads.
        self._attestation: tuple[StageSourceProvenance, Path, Path | None] | None = None

    def configure_trusted_attestation(self, provenance: StageSourceProvenance,
                                      inbox_root: Path, *,
                                      container_workspace: Path | None = None) -> None:
        """Infrastructure-only configuration for post-Ingest certification.

        Operator configures verified receipts, owner-bound bindings and trusted
        Docker mount mapping. No HTTP request can call this method.
        """
        if not isinstance(provenance, StageSourceProvenance):
            raise ValueError("Trusted Stage provenance store required")
        inbox = Path(inbox_root)
        if not inbox.is_dir() or inbox.is_symlink():
            raise ValueError("Existing private proxy inbox required")
        if container_workspace is not None:
            inside = Path(container_workspace)
            if not inside.is_absolute() or inside == Path("/"):
                raise ValueError("Trusted container workspace path required")
        with self._lock:
            if self._attestation is not None:
                raise ValueError("Stage certification already provisioned")
            self._attestation = (provenance, inbox, container_workspace)

    def register_trusted(self, owner_id: str, bridge: ContainerWorkerBridge) -> None:
        owner_id = ProjectCatalog._principal(owner_id)
        if not isinstance(bridge, ContainerWorkerBridge):
            raise ValueError("A private U13 container bridge must be provisioned")
        if bridge.owner_id != owner_id:
            raise ValueError("Worker owner does not match trusted registration")
        with self._lock:
            if owner_id in self._workers or any(b is bridge for b in self._workers.values()):
                raise ValueError("Worker already assigned")
            self._workers[owner_id] = bridge
            self._owner_locks[owner_id] = RLock()

    def _worker(self, owner_id: str):
        owner_id = ProjectCatalog._principal(owner_id)
        with self._lock:
            bridge = self._workers.get(owner_id)
            owner_lock = self._owner_locks.get(owner_id)
        if bridge is None or owner_lock is None:
            raise ProjectNotFound("Private worker not provisioned")
        return bridge, owner_lock

    def activate(self, owner_id: str, project_id: str) -> None:
        """Resolve the actual project owner BEFORE starting a worker.

        Same-owner switches are serialized. Different owners use separate
        locks, so two independent containers CAN start concurrently.
        """
        bridge, owner_lock = self._worker(owner_id)
        with owner_lock:
            # This is a trusted *internal* path check, never exposed as a URL.
            bridge.guard.bindings.resolve_internal(owner_id, project_id)
            if bridge.process is None:
                bridge.start()
            bridge.open_project(project_id)

    def register_private_inputs_trusted(self, owner_id: str, project_id: str,
                                        *, inbox_root: Path, source_slots: set[int]) -> int:
        """Operator-only: promote private verified proxy bytes into active Engine.

        Not exposed by HTTP. The original receipt remains UNTRUSTED until
        separate real Stage provenance verification is completed.
        """
        bridge, owner_lock = self._worker(owner_id)
        with owner_lock:
            bridge.guard.bindings.resolve_internal(owner_id, project_id)
            state, active, _ = bridge.guard.get_state(owner_id, bridge.runtime_id)
            if state != "ready" or active != project_id:
                raise RuntimeBusy("Project must be active for trusted provisioning")
            prepared = prepare_trusted_stage_inputs(
                bridge.guard.bindings, inbox_root, owner_id, project_id,
                source_slots=source_slots)
            count = bridge.register_staged_inputs(project_id)
            if count != len(prepared):
                bridge.stop()
                raise WorkerFailure("Private Engine source count mismatch")
            return count

    def ingest_start(self, owner_id: str, project_id: str) -> None:
        bridge, owner_lock = self._worker(owner_id)
        with owner_lock:
            # The status/activation path cannot be used to switch to a
            # foreign owner or an unbound Engine project.
            bridge.guard.bindings.resolve_internal(owner_id, project_id)
            state, active, _ = bridge.guard.get_state(owner_id, bridge.runtime_id)
            if state != "ready" or active != project_id:
                raise RuntimeBusy("Project not active")
            bridge.ingest_start(project_id)

    def ingest_status(self, owner_id: str, project_id: str) -> str:
        bridge, owner_lock = self._worker(owner_id)
        with owner_lock:
            bridge.guard.bindings.resolve_internal(owner_id, project_id)
            state, active, _ = bridge.guard.get_state(owner_id, bridge.runtime_id)
            if state not in {"busy", "ready"} or active != project_id:
                raise RuntimeBusy("Project not active")
            status = bridge.ingest_status(project_id)
            # Only a real Engine DONE from the active, owner-bound worker may
            # trigger source attestation. The browser never passes receipts.
            # A failure must not turn Ingest DONE into a false success for the
            # original verification: the existing Stage certificate stays
            # revoked, while status remains an accurate Engine result.
            if status == "done" and self._attestation is not None:
                provenance, inbox_root, inside = self._attestation
                bound = bridge.guard.bindings.resolve_internal(owner_id, project_id)
                try:
                    attest_authenticated_inbox(
                        provenance, bridge.guard.bindings, inbox_root,
                        owner_id, project_id,
                        engine_project_file=bound / "project.json",
                        container_workspace=inside,
                    )
                except (UnverifiedSources, OSError, ValueError, KeyError):
                    provenance.invalidate_trusted(owner_id, project_id)
            return status

    def project_state(self, owner_id: str, project_id: str) -> dict:
        """Owner-scoped status for exactly one bound project, not a global ready flag.

        A ready worker for project A must never enable Stage for project B.
        No internal paths, container identities or other owners are returned.
        """
        bridge, owner_lock = self._worker(owner_id)
        with owner_lock:
            bridge.guard.bindings.resolve_internal(owner_id, project_id)
            state, active, _ = bridge.guard.get_state(owner_id, bridge.runtime_id)
            if state in ("ready", "busy", "switching"):
                if bridge.process is None or bridge.process.poll() is not None:
                    state = "unavailable"
            selected = active == project_id
            return {
                "state": state if selected else "inactive",
                "is_active_project": selected,
                "can_start_ingest": selected and state == "ready",
            }

    def close(self, owner_id: str) -> None:
        bridge, owner_lock = self._worker(owner_id)
        with owner_lock:
            bridge.stop()

    def state(self, owner_id: str) -> str:
        bridge, owner_lock = self._worker(owner_id)
        with owner_lock:
            state, _, _ = bridge.guard.get_state(owner_id, bridge.runtime_id)
            # A stale worker whose process exited must NEVER be reported ready.
            if state in ("ready", "busy", "switching"):
                if bridge.process is None or bridge.process.poll() is not None:
                    return "unavailable"
            return state
