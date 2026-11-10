"""Trusted Owner Project -> fenced job -> private broker orchestration.

No HTTP route, provider SDK, filesystem paths supplied by browser or process
launcher. The broker MUST independently enforce OS isolation, exact cgroup
identity, child cleanup and fencing before this is used in production.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from urano.job_recovery_ledger import JobLease, JobRecoveryLedger, BusyOwner, StaleJob
from urano.project_catalog import ProjectCatalog


class BrokerUnverified(RuntimeError):
    """Broker could not attest successful start/cleanup; never claim ready."""


class IsolatedJobBroker(Protocol):
    """Trusted implementation, not browser-controlled; interface is provider-neutral."""
    def launch_and_verify(self, lease: JobLease) -> bool: ...
    def stop_and_verify_empty(self, lease: JobLease) -> bool: ...


@dataclass(frozen=True)
class JobAdmission:
    owner_id: str
    project_id: str
    job_id: str
    generation: int
    state: str


class TrustedJobAdmission:
    """Fail closed if a private process cannot be started or reaped.

    startup_reconcile MUST be invoked before admit(); the method fences all
    incomplete jobs and denies scheduling until an independent broker proves
    exact target cgroup empty and acknowledges each recovered job.
    """

    def __init__(self, catalog: ProjectCatalog, ledger: JobRecoveryLedger,
                 broker: IsolatedJobBroker):
        self.catalog, self.ledger, self.broker = catalog, ledger, broker
        self._startup_completed = False

    def startup_reconcile(self) -> tuple[JobLease, ...]:
        if self._startup_completed:
            raise RuntimeError('Broker startup reconciliation already attempted')
        self._startup_completed = True
        return self.ledger.recover_after_restart()

    def admit(self, owner_id: str, project_id: str) -> JobAdmission:
        if not self._startup_completed:
            raise BrokerUnverified('Broker startup recovery not performed')
        # Owner ownership checked BEFORE reserving or touching broker.
        self.catalog.get(owner_id, project_id)
        try:
            lease = self.ledger.start_trusted(owner_id, project_id)
        except BusyOwner:
            raise
        try:
            if self.broker.launch_and_verify(lease) is not True:
                raise BrokerUnverified('Isolated Engine launch not attested')
            active = self.ledger.mark_running(lease)
        except Exception as exc:
            # Even if broker.launch fails before a service exists, do NOT mark
            # stopped until broker has verified that no cgroup can remain.
            try:
                self._stop_known(lease)
            except Exception as cleanup:
                raise BrokerUnverified('Engine cleanup could not be verified') from cleanup
            raise BrokerUnverified('Engine did not become ready') from exc
        return JobAdmission(active.owner_id, active.project_id, active.job_id,
                            active.generation, active.state)

    def _stop_known(self, lease: JobLease) -> JobLease:
        # State is persisted before signaling/inspecting the OS. A crashed
        # broker can safely recover a `stopping` job as `orphaned` later.
        if lease.state in ('starting', 'running', 'orphaned'):
            stopping = self.ledger.request_stop(lease)
        elif lease.state == 'stopping':
            stopping = lease
        else:
            raise StaleJob('Cannot stop an already finished job')
        if self.broker.stop_and_verify_empty(stopping) is not True:
            raise BrokerUnverified('Target cgroup not proven empty')
        return self.ledger.confirm_stopped(stopping, verified_cgroup_empty=True)

    def stop(self, job: JobAdmission) -> None:
        lease = self.ledger.get_trusted(job.job_id)
        if (lease is None or lease.owner_id != job.owner_id or
            lease.project_id != job.project_id or
            lease.generation != job.generation or
            lease.state not in ('running', 'stopping')):
            raise StaleJob('Job token is stale or from another owner')
        self._stop_known(lease)

    def cleanup_orphan(self, orphan: JobLease) -> None:
        current = self.ledger.get_trusted(orphan.job_id)
        if current != orphan or orphan.state != 'orphaned':
            raise StaleJob('Recovered job changed or has wrong identity')
        self._stop_known(orphan)
