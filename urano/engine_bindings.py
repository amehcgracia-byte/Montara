"""U13 lab: owner-scoped binding from a catalog UUID to an Engine folder.

This is INTERNAL registry metadata. There is intentionally no HTTP endpoint to
register arbitrary file paths, activate a project or read media. The Engine has
a single active project per process; a future isolated runtime adapter must
authorize ownership, then resolve this binding before it can open any project.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from urano.project_catalog import ProjectCatalog, ProjectNotFound

_FOLDER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,199}$")


@dataclass(frozen=True)
class EngineBinding:
    catalog_project_id: str
    folder_name: str


class EngineProjectRegistry:
    """Database-backed map that does not change current Engine runtime state."""

    def __init__(self, db_path: str | Path, engine_data_root: str | Path,
                 catalog: ProjectCatalog):
        self.db_path = Path(db_path)
        if not self.db_path.parent.is_dir():
            raise ValueError("Registry database parent must exist")
        self.root = Path(engine_data_root).absolute()
        self.projects_dir = self.root / "Projects"
        if (self.root.is_symlink() or not self.root.is_dir() or
            self.projects_dir.is_symlink() or not self.projects_dir.is_dir()):
            raise ValueError("Existing non-symlink Engine Projects root required")
        self.catalog = catalog
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS urano_engine_bindings (
                catalog_project_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                folder_name TEXT NOT NULL UNIQUE
            )""")
            db.execute("""CREATE INDEX IF NOT EXISTS urano_engine_bindings_owner
                       ON urano_engine_bindings(owner_id)""")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.db_path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def _validated_folder(self, folder_name: str) -> Path:
        if (not isinstance(folder_name, str) or not _FOLDER.fullmatch(folder_name) or
            folder_name in {".", ".."} or folder_name.strip() != folder_name):
            raise ValueError("Invalid Engine project folder")
        folder = self.projects_dir / folder_name
        project_file = folder / "project.json"
        if (folder.is_symlink() or not folder.is_dir() or project_file.is_symlink()
            or not project_file.is_file()):
            raise ValueError("Engine project folder missing or linked")
        # Never accept a traversal or a symlink target leaving the private root.
        if (not folder.resolve().is_relative_to(self.projects_dir.resolve()) or
            folder.resolve().parent != self.projects_dir.resolve()):
            raise ValueError("Engine project is outside allowed root")
        return folder

    def bind_trusted(self, owner_id: str, catalog_project_id: str,
                     folder_name: str) -> EngineBinding:
        """Server operator/runtime only: a browser must never call this directly.

        Does NOT claim orphan Engine folders: only an already-owned catalog
        project may be bound, and a folder can be bound to only one UUID.
        """
        self.catalog.get(owner_id, catalog_project_id)
        self._validated_folder(folder_name)
        try:
            with self._connect() as db:
                db.execute("""INSERT INTO urano_engine_bindings
                    (catalog_project_id,owner_id,folder_name) VALUES(?,?,?)""",
                           (catalog_project_id, owner_id, folder_name))
        except sqlite3.IntegrityError as exc:
            raise ValueError("Project or Engine folder already bound") from exc
        return EngineBinding(catalog_project_id, folder_name)

    def resolve_internal(self, owner_id: str, catalog_project_id: str) -> Path:
        """Return a private Engine project path to trusted backend code only."""
        self.catalog.get(owner_id, catalog_project_id)
        with self._connect() as db:
            row = db.execute("""SELECT folder_name FROM urano_engine_bindings
                                WHERE catalog_project_id=? AND owner_id=?""",
                             (catalog_project_id, owner_id)).fetchone()
        if row is None:
            raise ProjectNotFound("Project is not linked to an Engine workspace")
        return self._validated_folder(row["folder_name"])
