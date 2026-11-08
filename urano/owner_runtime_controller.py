"""U19: trusted session-owner -> existing private Docker Engine bridge.

Infrastructure, NEVER a public factory, provisions each owner with a dedicated
bridge/worker. Browser selects a catalog UUID only. No media, Docker parameters,
paths, or rendering exposed through these operations.
"""
from __future__ import annotations

from threading import RLock

from urano.container_worker_bridge import ContainerWorkerBridge
from urano.project_catalog import ProjectCatalog, ProjectNotFound
from urano.private_worker_supervisor import WorkerFailure
from urano.runtime_activation import RuntimeBusy, StaleActivation


class OwnerRuntimeController:
    """Narrow isolated-lab adapter over the already tested U13 worker bridge.

    One bridge per owner. No shared global Engine. Runtime registration is
    process-local trusted provisioning; not a remotely writable catalogue.
    """

    def __init__(self):
        self._workers: dict[str, ContainerWorkerBridge] = {}
        self._lock = RLock()

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

    def _worker(self, owner_id: str) -> ContainerWorkerBridge:
        owner_id = ProjectCatalog._principal(owner_id)
        bridge = self._workers.get(owner_id)
        if bridge is None:
            raise ProjectNotFound("Private worker not provisioned")
        return bridge

    def activate(self, owner_id: str, project_id: str) -> None:
        """Resolve the actual project owner BEFORE starting a worker."""
        with self._lock:
            bridge = self._worker(owner_id)
            # This is a trusted *internal* path check, never exposed as a URL.
            bridge.guard.bindings.resolve_internal(owner_id, project_id)
            if bridge.process is None:
                bridge.start()
            bridge.open_project(project_id)

    def close(self, owner_id: str) -> None:
        with self._lock:
            self._worker(owner_id).stop()

    def state(self, owner_id: str) -> str:
        with self._lock:
            bridge = self._worker(owner_id)
            state, _, _ = bridge.guard.get_state(owner_id, bridge.runtime_id)
            # A stale worker whose process exited must NEVER be reported ready.
            if state in ("ready", "busy", "switching"):
                if bridge.process is None or bridge.process.poll() is not None:
                    return "unavailable"
            return state
