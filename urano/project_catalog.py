"""Durable, owner-scoped URANO metadata (not authentication or HTTP endpoints).

The caller MUST supply a server-verified principal. Never trust an owner_id sent by
a browser. No original media or local file paths are stored in this catalog.
"""
from __future__ import annotations

import json
import re
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ProjectNotFound(LookupError):
    """No visible project, including when it belongs to another owner."""


class ProjectConflict(RuntimeError):
    """A newer saved revision exists."""


@dataclass(frozen=True)
class Project:
    id: str
    title: str
    recipe: dict[str, Any]
    revision: int
    created_at: str
    updated_at: str


class ProjectCatalog:
    """One SQLite connection per operation; writes are atomic and owner-scoped."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        if not self.db_path.parent.is_dir():
            raise ValueError("Database parent must already exist and be private")
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS urano_projects (
                project_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                title TEXT NOT NULL,
                recipe_json TEXT NOT NULL DEFAULT '{}',
                revision INTEGER NOT NULL DEFAULT 0 CHECK(revision >= 0),
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            )""")
            db.execute("""CREATE INDEX IF NOT EXISTS urano_projects_owner
                       ON urano_projects(owner_id, updated_at DESC)""")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.db_path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout = 10000")
        return db

    @staticmethod
    def _principal(owner_id: str) -> str:
        if not isinstance(owner_id, str) or not _ID.fullmatch(owner_id):
            raise ValueError("Invalid trusted owner identifier")
        return owner_id

    @staticmethod
    def _project_id(project_id: str) -> str:
        if not isinstance(project_id, str):
            raise ValueError("Invalid project identifier")
        try:
            parsed = uuid.UUID(project_id)
        except (ValueError, AttributeError) as exc:
            raise ValueError("Invalid project identifier") from exc
        if str(parsed) != project_id:
            raise ValueError("Non-canonical project identifier")
        return project_id

    @staticmethod
    def _title(title: str) -> str:
        if not isinstance(title, str) or not (1 <= len(title.strip()) <= 160):
            raise ValueError("Project title must be 1-160 characters")
        return title.strip()

    @staticmethod
    def _recipe(recipe: dict[str, Any]) -> str:
        if not isinstance(recipe, dict):
            raise ValueError("Recipe must be a JSON object")
        try:
            value = json.dumps(recipe, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Recipe must contain valid JSON values") from exc
        if len(value.encode("utf-8")) > 256_000:
            raise ValueError("Recipe exceeds 256 KB catalog limit")
        return value

    @staticmethod
    def _to_project(row: sqlite3.Row) -> Project:
        return Project(
            id=row["project_id"], title=row["title"], recipe=json.loads(row["recipe_json"]),
            revision=row["revision"], created_at=row["created_at"], updated_at=row["updated_at"],
        )

    def create(self, owner_id: str, title: str) -> Project:
        owner_id, title = self._principal(owner_id), self._title(title)
        project_id = str(uuid.uuid4())
        with self._connect() as db:
            db.execute("INSERT INTO urano_projects(project_id,owner_id,title) VALUES(?,?,?)",
                       (project_id, owner_id, title))
            row = db.execute("SELECT * FROM urano_projects WHERE project_id=?", (project_id,)).fetchone()
        return self._to_project(row)

    def list_for(self, owner_id: str) -> list[Project]:
        owner_id = self._principal(owner_id)
        with self._connect() as db:
            rows = db.execute("""SELECT * FROM urano_projects WHERE owner_id=?
                                 ORDER BY updated_at DESC, project_id ASC""", (owner_id,)).fetchall()
        return [self._to_project(row) for row in rows]

    def get(self, owner_id: str, project_id: str) -> Project:
        owner_id, project_id = self._principal(owner_id), self._project_id(project_id)
        with self._connect() as db:
            row = db.execute("SELECT * FROM urano_projects WHERE project_id=? AND owner_id=?",
                             (project_id, owner_id)).fetchone()
        if row is None:
            raise ProjectNotFound("Project not found")
        return self._to_project(row)

    def save_recipe(self, owner_id: str, project_id: str, recipe: dict[str, Any],
                    *, expected_revision: int) -> Project:
        owner_id, project_id = self._principal(owner_id), self._project_id(project_id)
        payload = self._recipe(recipe)
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("Expected revision must be a nonnegative integer")
        with self._connect() as db:
            cursor = db.execute("""UPDATE urano_projects SET recipe_json=?, revision=revision+1,
                                   updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                                   WHERE project_id=? AND owner_id=? AND revision=?""",
                                (payload, project_id, owner_id, expected_revision))
            if cursor.rowcount != 1:
                exists = db.execute("SELECT 1 FROM urano_projects WHERE project_id=? AND owner_id=?",
                                    (project_id, owner_id)).fetchone()
                if exists is None:
                    raise ProjectNotFound("Project not found")
                raise ProjectConflict("Project has a newer revision")
            row = db.execute("SELECT * FROM urano_projects WHERE project_id=? AND owner_id=?",
                             (project_id, owner_id)).fetchone()
        return self._to_project(row)
