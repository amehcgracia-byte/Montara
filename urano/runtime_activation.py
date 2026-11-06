"""U13B: persistent handoff guard for ONE isolated Engine runtime per owner.

This deliberately does NOT call the Engine or start a worker. An Engine adapter
must later perform the actual open in a private process, then acknowledge it.
Only trusted backend code can register a runtime or acknowledge an activation.
"""
from __future__ import annotations

import secrets
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from urano.engine_bindings import EngineProjectRegistry
from urano.project_catalog import ProjectCatalog, ProjectNotFound


class RuntimeBusy(RuntimeError):
    """Cannot switch workspaces while a switch/job is still in progress."""


class StaleActivation(RuntimeError):
    """A previously issued activation ticket is no longer current."""


@dataclass(frozen=True)
class ActivationTicket:
    runtime_id: str
    generation: int
    project_id: str
    project_path: Path


class RuntimeActivationGuard:
    """State machine: idle -> switching -> ready -> busy -> ready, or switching -> idle.

    Runtime ownership is provisioned ONLY via register_trusted(). This prevents
    multiple accounts from taking turns mutating one global Engine process.
    Cross-process state changes are serialized via SQLite BEGIN IMMEDIATE.
    """

    def __init__(self, db_path: str | Path, catalog: ProjectCatalog,
                 bindings: EngineProjectRegistry):
        self.db_path = Path(db_path)
        if not self.db_path.parent.is_dir():
            raise ValueError("Database parent must exist")
        self.catalog, self.bindings = catalog, bindings
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS urano_runtime_slots (
                runtime_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL UNIQUE,
                project_id TEXT,
                generation INTEGER NOT NULL DEFAULT 0,
                state TEXT NOT NULL DEFAULT 'idle'
                    CHECK(state IN ('idle','switching','ready','busy'))
            )""")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.db_path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def register_trusted(self, owner_id: str, runtime_id: str | None = None) -> str:
        """Infrastructure only: binds an isolated process slot to exactly one owner.

        No route accepts an owner_id or runtime_id from a browser. The actual
        process/container isolation is a prerequisite, NOT done by this function.
        """
        owner_id = ProjectCatalog._principal(owner_id)
        runtime_id = runtime_id or "urano-" + secrets.token_hex(16)
        ProjectCatalog._principal(runtime_id)
        with self._connect() as db:
            try:
                db.execute("INSERT INTO urano_runtime_slots(runtime_id,owner_id) VALUES(?,?)",
                           (runtime_id, owner_id))
            except sqlite3.IntegrityError as exc:
                raise ValueError("Owner or runtime already registered") from exc
        return runtime_id

    def _slot(self, db: sqlite3.Connection, owner_id: str, runtime_id: str) -> sqlite3.Row:
        owner_id = ProjectCatalog._principal(owner_id)
        runtime_id = ProjectCatalog._principal(runtime_id)
        row = db.execute("""SELECT * FROM urano_runtime_slots
                            WHERE runtime_id=? AND owner_id=?""",
                         (runtime_id, owner_id)).fetchone()
        if row is None:
            raise ProjectNotFound("Runtime unavailable")
        return row

    def request_open(self, owner_id: str, runtime_id: str, project_id: str) -> ActivationTicket:
        """Reserve a safe switch; DOES NOT open Engine. Worker must acknowledge.

        A pre-existing busy/switching operation blocks every competing switch,
        including to another project of the same account. This call never
        changes the old project's Engine state, media or recipe.
        """
        # Validate catalog+physical folder before acquiring the reservation.
        project_path = self.bindings.resolve_internal(owner_id, project_id)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            slot = self._slot(db, owner_id, runtime_id)
            if slot["state"] in ("busy", "switching"):
                raise RuntimeBusy("Runtime has an active job or pending switch")
            generation = slot["generation"] + 1
            db.execute("""UPDATE urano_runtime_slots
                          SET state='switching',project_id=?,generation=?
                          WHERE runtime_id=? AND owner_id=?""",
                       (project_id, generation, runtime_id, owner_id))
        return ActivationTicket(runtime_id, generation, project_id, project_path)

    def acknowledge_open(self, owner_id: str, ticket: ActivationTicket, *, success: bool) -> None:
        """Trusted isolated worker only; acknowledge Engine opening succeeded/failed.

        If Engine open fails, runtime is marked idle and cannot report an active
        project. Actual process isolation and recovery remain separate gates.
        """
        if not isinstance(ticket, ActivationTicket) or type(success) is not bool:
            raise ValueError("Invalid activation acknowledgement")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            slot = self._slot(db, owner_id, ticket.runtime_id)
            if (slot["generation"] != ticket.generation or
                slot["project_id"] != ticket.project_id or slot["state"] != "switching"):
                raise StaleActivation("Stale activation acknowledgement")
            db.execute("""UPDATE urano_runtime_slots
                          SET state=?, project_id=? WHERE runtime_id=?""",
                       ("ready" if success else "idle", ticket.project_id if success else None,
                        ticket.runtime_id))

    def begin_job(self, owner_id: str, runtime_id: str, project_id: str) -> int:
        """Trusted worker only: mark a job busy; fails if project not active."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            slot = self._slot(db, owner_id, runtime_id)
            if slot["state"] != "ready" or slot["project_id"] != project_id:
                raise RuntimeBusy("Project not active or runtime unavailable")
            db.execute("UPDATE urano_runtime_slots SET state='busy' WHERE runtime_id=?",
                       (runtime_id,))
            return slot["generation"]

    def finish_job(self, owner_id: str, runtime_id: str, project_id: str,
                   generation: int) -> None:
        """Trusted worker only; cannot release a newer/different job."""
        if type(generation) is not int:
            raise ValueError("Invalid job generation")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            slot = self._slot(db, owner_id, runtime_id)
            if (slot["state"] != "busy" or slot["project_id"] != project_id or
                slot["generation"] != generation):
                raise StaleActivation("Cannot finish another job")
            db.execute("UPDATE urano_runtime_slots SET state='ready' WHERE runtime_id=?",
                       (runtime_id,))

    def get_state(self, owner_id: str, runtime_id: str) -> tuple[str, str | None, int]:
        with self._connect() as db:
            slot = self._slot(db, owner_id, runtime_id)
            return slot["state"], slot["project_id"], slot["generation"]
