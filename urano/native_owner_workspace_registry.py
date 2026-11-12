"""One stable Owner workspace per Google identity, without a project picker.

The Owner catalog is still the trusted source of ownership. This small SQLite
mapping distinguishes ONE broker workspace UUID from Chema's MANY native edits
inside that Owner's private data_root/Projects and Sessions directories.

For an existing beta Owner whose catalog already has projects, NEVER choose a
workspace automatically: it could silently hide/strand real material. A
separate, explicitly verified migration binds one existing owner-owned UUID.
No data files are moved, deleted or overwritten by this registry.

Caller obligations: use an owner_id already verified by SessionStore; consult
the root broker before starting or switching a runtime; verify filesystem and
the last running lease before binding a legacy workspace. No HTTP route here.
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass

from urano.project_catalog import ProjectCatalog, ProjectNotFound


class ExistingOwnerProjects(RuntimeError):
    """Existing owner work requires an explicit, non-destructive choice."""


class WorkspaceAlreadyBound(RuntimeError):
    """Do not silently switch the immutable Owner workspace identity."""


@dataclass(frozen=True)
class NativeWorkspace:
    owner_id: str
    workspace_id: str


class NativeOwnerWorkspaceRegistry:
    """Atomic identity registry backed by the existing Owner SQLite database."""

    def __init__(self, catalog: ProjectCatalog):
        if not isinstance(catalog, ProjectCatalog):
            raise TypeError("Trusted Owner project catalog required")
        self.catalog = catalog
        with closing(catalog._connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS urano_native_owner_workspace (
                owner_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT
                    (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                FOREIGN KEY(workspace_id) REFERENCES urano_projects(project_id)
            )""")

    def get(self, owner_id: str) -> NativeWorkspace | None:
        owner_id = ProjectCatalog._principal(owner_id)
        with closing(self.catalog._connect()) as db:
            row = db.execute(
                """SELECT workspace_id FROM urano_native_owner_workspace
                   WHERE owner_id=?""", (owner_id,),
            ).fetchone()
        return NativeWorkspace(owner_id, row["workspace_id"]) if row else None

    def reserve_new(self, owner_id: str) -> NativeWorkspace:
        """Idempotent New Owner onboarding; never auto-select legacy projects."""
        owner_id = ProjectCatalog._principal(owner_id)
        with closing(self.catalog._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""SELECT workspace_id
                FROM urano_native_owner_workspace WHERE owner_id=?""",
                (owner_id,)).fetchone()
            if row:
                return NativeWorkspace(owner_id, row["workspace_id"])
            legacy = db.execute("""SELECT COUNT(*) AS total FROM urano_projects
                WHERE owner_id=?""", (owner_id,)).fetchone()["total"]
            if legacy:
                raise ExistingOwnerProjects(
                    "Existing private projects must be verified before onboarding")
            workspace_id = str(uuid.uuid4())
            db.execute("""INSERT INTO urano_projects
                (project_id,owner_id,title) VALUES(?,?,?)""",
                (workspace_id, owner_id, "Montara private workspace"))
            db.execute("""INSERT INTO urano_native_owner_workspace
                (owner_id,workspace_id) VALUES(?,?)""",
                (owner_id,workspace_id))
        return NativeWorkspace(owner_id, workspace_id)

    def bind_existing(self, owner_id: str, project_id: str) -> NativeWorkspace:
        """Explicit legacy binding after external owner/job/filesystem audit.

        No side effects to saved projects. Broker process safety must be
        checked at the invoking orchestration layer before calling this.
        """
        owner_id = ProjectCatalog._principal(owner_id)
        project_id = ProjectCatalog._project_id(project_id)
        with closing(self.catalog._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("""SELECT workspace_id
                FROM urano_native_owner_workspace WHERE owner_id=?""",
                (owner_id,)).fetchone()
            if existing:
                if existing["workspace_id"] != project_id:
                    raise WorkspaceAlreadyBound("Private workspace already fixed")
                return NativeWorkspace(owner_id, project_id)
            candidate = db.execute("""SELECT 1 FROM urano_projects
                WHERE owner_id=? AND project_id=?""",
                (owner_id, project_id)).fetchone()
            if candidate is None:
                raise ProjectNotFound("Private workspace does not belong to owner")
            db.execute("""INSERT INTO urano_native_owner_workspace
                (owner_id,workspace_id) VALUES(?,?)""",
                (owner_id,project_id))
        return NativeWorkspace(owner_id,project_id)
