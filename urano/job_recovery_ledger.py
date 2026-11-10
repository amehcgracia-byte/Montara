"""Durable, fail-closed job admission ledger for an isolated Engine broker.

NOT a process/container launcher or security sandbox. Only a trusted executor
may call lifecycle methods. Never expose identifiers/paths or ledger writes to
HTTP. Every state mutation verifies a generation to fence stale controllers.
"""
from __future__ import annotations

import secrets
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from urano.project_catalog import ProjectCatalog


class BusyOwner(RuntimeError):
    """Owner has an unfinished or unverified Engine job."""


class StaleJob(RuntimeError):
    """Job generation, owner or expected state no longer match."""


@dataclass(frozen=True)
class JobLease:
    owner_id: str
    project_id: str
    job_id: str
    generation: int
    state: str


class JobRecoveryLedger:
    """One unfinished isolated job per canonical owner; generation monotonic.

    State: starting -> running -> stopping -> stopped.
    On a host crash: starting/running/stopping -> orphaned; NEVER mark idle.
    After the trusted broker independently checks target cgroup EMPTY,
    `confirm_stopped` may release the owner slot. This is not a lease TTL:
    expired time cannot prove a process exited, and must not allow reuse.
    """

    OPEN_STATES = ('starting', 'running', 'stopping', 'orphaned')

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        if not self.db_path.parent.is_dir():
            raise ValueError('Ledger parent directory must exist')
        with self._connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS urano_job_generations (
                owner_id TEXT PRIMARY KEY, generation INTEGER NOT NULL
            )''')
            db.execute('''CREATE TABLE IF NOT EXISTS urano_engine_jobs (
                job_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                generation INTEGER NOT NULL,
                state TEXT NOT NULL CHECK(state IN
                    ('starting','running','stopping','orphaned','stopped')),
                UNIQUE(owner_id, generation)
            )''')
            db.execute('''CREATE UNIQUE INDEX IF NOT EXISTS urano_one_unverified_job_per_owner
                ON urano_engine_jobs(owner_id)
                WHERE state IN ('starting','running','stopping','orphaned')''')

    def _connect(self):
        db=sqlite3.connect(str(self.db_path),timeout=10)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA busy_timeout=10000')
        return db

    @staticmethod
    def _principal(value):
        return ProjectCatalog._principal(value)

    def start_trusted(self,owner_id,project_id) -> JobLease:
        owner_id=self._principal(owner_id)
        project_id=self._principal(project_id)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('''SELECT 1 FROM urano_engine_jobs WHERE owner_id=?
                AND state IN ('starting','running','stopping','orphaned')''',
                (owner_id,)).fetchone()
            if existing:
                raise BusyOwner('Unverified previous job still owns this slot')
            row=db.execute('SELECT generation FROM urano_job_generations WHERE owner_id=?',
                           (owner_id,)).fetchone()
            generation=1 if row is None else row['generation']+1
            db.execute('''INSERT INTO urano_job_generations(owner_id,generation)
                VALUES (?,?) ON CONFLICT(owner_id)
                DO UPDATE SET generation=excluded.generation''',(owner_id,generation))
            job_id='job-'+secrets.token_hex(16)
            db.execute('''INSERT INTO urano_engine_jobs
                (job_id,owner_id,project_id,generation,state)
                VALUES (?,?,?,?, 'starting')''',(job_id,owner_id,project_id,generation))
        return JobLease(owner_id,project_id,job_id,generation,'starting')

    def _transition(self,lease:JobLease,expected:tuple[str,...],target:str) -> JobLease:
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('''SELECT owner_id,project_id,generation,state FROM urano_engine_jobs
                WHERE job_id=?''',(lease.job_id,)).fetchone()
            if (row is None or row['owner_id']!=lease.owner_id or
                row['project_id']!=lease.project_id or row['generation']!=lease.generation or
                row['state'] not in expected):
                raise StaleJob('Job no longer admits this transition')
            db.execute('UPDATE urano_engine_jobs SET state=? WHERE job_id=?',
                       (target,lease.job_id))
        return JobLease(lease.owner_id,lease.project_id,lease.job_id,lease.generation,target)

    def mark_running(self,lease:JobLease)->JobLease:
        """Trusted broker only, after exact unit/cgroup and process attestation."""
        return self._transition(lease,('starting',),'running')

    def request_stop(self,lease:JobLease)->JobLease:
        return self._transition(lease,('starting','running','orphaned'),'stopping')

    def recover_after_restart(self)->tuple[JobLease,...]:
        """All unfinished jobs become fenced; cleanup required before reuse.

        This call MUST be part of broker startup, before admitting new jobs.
        An empty/cancelled unit is NOT assumed: orphaned stays unverified.
        """
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''UPDATE urano_engine_jobs SET state='orphaned'
                WHERE state IN ('starting','running','stopping')''')
            rows=db.execute('''SELECT owner_id,project_id,job_id,generation,state
                FROM urano_engine_jobs WHERE state='orphaned'
                ORDER BY owner_id''').fetchall()
        return tuple(JobLease(**dict(row)) for row in rows)

    def confirm_stopped(self,lease:JobLease,*, verified_cgroup_empty:bool)->JobLease:
        """Caller must independently verify exact unit gone AND cgroup empty.

        A boolean is only an assertion from a separately authorized broker;
        this ledger cannot independently attest that the caller is honest.
        """
        if verified_cgroup_empty is not True:
            raise ValueError('Never release an unverified cgroup')
        return self._transition(lease,('stopping','orphaned'),'stopped')

    def unverified_for_owner(self, owner_id: str) -> tuple[JobLease, ...]:
        """Trusted read: only a proven-empty worker can clear an owner fence."""
        owner_id = self._principal(owner_id)
        with self._connect() as db:
            rows = db.execute("""SELECT owner_id,project_id,job_id,generation,state
                FROM urano_engine_jobs WHERE owner_id=?
                AND state IN ('starting','running','stopping','orphaned')
                ORDER BY generation""", (owner_id,)).fetchall()
        return tuple(JobLease(**dict(row)) for row in rows)

    def get_trusted(self,job_id:str)->JobLease|None:
        with self._connect() as db:
            row=db.execute('''SELECT owner_id,project_id,job_id,generation,state
                FROM urano_engine_jobs WHERE job_id=?''',(job_id,)).fetchone()
        return JobLease(**dict(row)) if row else None
