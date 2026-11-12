"""Opt-in trusted adapter: I13 activation -> I19 durable fenced admission.

No OS launcher, no HTTP listener, no implicit owner registration. Deployment
requires a separately audited per-owner isolated transport and startup recovery.
Never expose this bridge in C8 without that security gate.
"""
from __future__ import annotations

from threading import RLock
from typing import Callable, Protocol

from urano.job_recovery_ledger import JobLease
from urano.runtime_activation import ActivationTicket, RuntimeActivationGuard
from urano.trusted_job_admission import JobAdmission, TrustedJobAdmission


class VerifiedEngineTransport(Protocol):
    """OS-audited transport: open and verify Engine; stop exact worker/cgroup."""
    def open_verified(self, owner_id: str, ticket: ActivationTicket) -> bool: ...
    def stop_verified(self, owner_id: str, ticket: ActivationTicket) -> bool: ...


class _TicketBroker:
    """Bridge I19 to the trusted I13 ActivationTicket (never from HTTP)."""
    def __init__(self, transport: VerifiedEngineTransport):
        self.transport = transport
        self._pending: dict[str, ActivationTicket] = {}
        self._tickets: dict[str, ActivationTicket] = {}
        self._lock = RLock()

    def reserve_ticket(self, owner_id: str, ticket: ActivationTicket) -> None:
        with self._lock:
            if owner_id in self._pending:
                raise RuntimeError('Another project activation is pending')
            self._pending[owner_id] = ticket

    def finish_pending(self, owner_id: str) -> None:
        with self._lock:
            self._pending.pop(owner_id, None)

    def launch_and_verify(self, lease: JobLease) -> bool:
        with self._lock:
            ticket = self._pending.get(lease.owner_id)
            if ticket is None or ticket.project_id != lease.project_id:
                raise RuntimeError('Job does not match trusted activation ticket')
            self._tickets[lease.job_id] = ticket
        return self.transport.open_verified(lease.owner_id, ticket) is True

    def stop_and_verify_empty(self, lease: JobLease) -> bool:
        with self._lock:
            ticket = self._tickets.get(lease.job_id)
            if ticket is None or ticket.project_id != lease.project_id:
                # Cannot certify cleanup without identifying exact target.
                return False
        if self.transport.stop_verified(lease.owner_id, ticket) is not True:
            return False
        with self._lock:
            self._tickets.pop(lease.job_id, None)
        return True


class GatewayJobBridge:
    """Implements I13 PrivateExecutor using the I19 durable control plane.

    Only use after startup_reconcile(), and after independently cleaning every
    orphan. Recovered jobs deliberately remain blocked if the broker cannot
    match their historical unit/cgroup (this adapter has no durable unit map).
    """
    def __init__(self, guard: RuntimeActivationGuard,
                 admission: TrustedJobAdmission,
                 broker: _TicketBroker,
                 trusted_runtime_for_owner: Callable[[str], str | None]):
        if admission.broker is not broker:
            raise ValueError('Admission and bridge must use the same broker')
        self.guard = guard
        self.admission = admission
        self.broker = broker
        self.lookup = trusted_runtime_for_owner
        self._jobs: dict[str, JobAdmission] = {}
        self._lock = RLock()

    @classmethod
    def prepare(cls, guard: RuntimeActivationGuard,
                ledger_admission_factory: Callable[[_TicketBroker], TrustedJobAdmission],
                transport: VerifiedEngineTransport,
                trusted_runtime_for_owner: Callable[[str], str | None]):
        broker = _TicketBroker(transport)
        admission = ledger_admission_factory(broker)
        instance = cls(guard, admission, broker, trusted_runtime_for_owner)
        # May raise on DB failure: no admission permitted until recovery succeeds.
        instance.startup_orphans = admission.startup_reconcile()
        return instance

    def runtime_for_owner(self, owner_id: str) -> str | None:
        # Do not hand I13 an existing slot while it still has a real job;
        # otherwise I13 might enter `switching` and abort an active Engine.
        with self._lock:
            if owner_id in self._jobs:
                return None
        return self.lookup(owner_id)

    def open_verified(self, owner_id: str, ticket: ActivationTicket) -> bool:
        if not isinstance(ticket, ActivationTicket):
            raise ValueError('No trusted activation ticket')
        if self.lookup(owner_id) != ticket.runtime_id:
            raise RuntimeError('Runtime identity mismatch')
        with self._lock:
            if owner_id in self._jobs:
                raise RuntimeError('Owner already has a job')
            self.broker.reserve_ticket(owner_id, ticket)
            try:
                active = self.admission.admit(owner_id, ticket.project_id)
                self._jobs[owner_id] = active
                return active.state == 'running'
            finally:
                self.broker.finish_pending(owner_id)

    def abort(self, owner_id: str, runtime_id: str) -> None:
        if self.lookup(owner_id) != runtime_id:
            raise ValueError('Runtime identity mismatch')
        with self._lock:
            job = self._jobs.get(owner_id)
            if job is None:
                # Failed I19 admission might have left `stopping` or `orphaned`.
                # I13 MUST NOT acknowledge an unverified cleanup as idle.
                if self.admission.ledger.unverified_for_owner(owner_id):
                    raise RuntimeError('Previous Engine cleanup is unverified')
                return
            self.admission.stop(job)
            del self._jobs[owner_id]

    def close_trusted(self, owner_id: str, runtime_id: str) -> None:
        """Control-plane close, never called directly with browser owner IDs."""
        with self._lock:
            job = self._jobs.get(owner_id)
            if job is None:
                raise RuntimeError('No live job to close')
            self.abort(owner_id, runtime_id)
            self.guard.invalidate_after_worker_exit(owner_id, runtime_id,
                                                     self.guard.get_state(owner_id, runtime_id)[2])
