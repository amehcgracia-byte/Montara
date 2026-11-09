"""Owner-scoped, trusted-only source provenance for private Stage projects.

No public API can create bindings: trusted ingestion infrastructure must attest
each proxy to its exact original fingerprint. This metadata is *not* an original,
path, media upload or an executable render instruction. Fail closed when absent.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from urano.project_catalog import ProjectCatalog

_SHA = re.compile(r"^[a-f0-9]{64}$")
_NAME = re.compile(r"^[^/\\\\\x00]{1,200}$")
_MAX_SOURCE_COUNT = 16


class UnverifiedSources(ValueError):
    pass


def _canonical_sources(sources: object) -> list[dict]:
    if (not isinstance(sources, list) or not 1 <= len(sources) <= _MAX_SOURCE_COUNT):
        raise UnverifiedSources("Invalid Stage source count")
    clean = []
    seen = set()
    for entry in sources:
        if not isinstance(entry, dict) or set(entry) != {"source_slot", "original"}:
            raise UnverifiedSources("Invalid Stage source entry")
        slot, original = entry["source_slot"], entry["original"]
        if type(slot) is not int or slot not in range(16) or slot in seen:
            raise UnverifiedSources("Duplicate or invalid camera slot")
        if not isinstance(original, dict) or set(original) != {"name", "size", "fingerprint"}:
            raise UnverifiedSources("Missing original identity")
        if (not isinstance(original["name"], str) or not _NAME.fullmatch(original["name"])
                or original["name"] in {".", ".."}
                or type(original["size"]) is not int or not 0 < original["size"] < 2**63
                or not isinstance(original["fingerprint"], str)
                or not _SHA.fullmatch(original["fingerprint"])):
            raise UnverifiedSources("Invalid original identity")
        seen.add(slot)
        clean.append({"source_slot": slot, "original": dict(original)})
    return sorted(clean, key=lambda entry: entry["source_slot"])


class StageSourceProvenance:
    """Ingest-side certificate store, keyed by verified owner and project.

    Trusted infrastructure alone calls register_trusted AFTER Stage has attested
    which original file produced each proxy. Browser can only read and compare.
    """

    def __init__(self, db_path: Path, catalog: ProjectCatalog):
        self.catalog = catalog
        self.db_path = Path(db_path)
        if not self.db_path.parent.is_dir():
            raise ValueError("Private provenance database parent required")
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS urano_stage_source_provenance (
                project_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                source_json TEXT NOT NULL,
                stage_revision TEXT NOT NULL
            )""")

    def _connect(self):
        db = sqlite3.connect(str(self.db_path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def register_trusted(self, owner_id: str, project_id: str,
                         sources: list[dict], *, stage_revision: str) -> None:
        # Important: this method is not exposed to the HTTP application.
        self.catalog.get(owner_id, project_id)
        canonical = _canonical_sources(sources)
        if (not isinstance(stage_revision, str) or not _SHA.fullmatch(stage_revision)):
            raise UnverifiedSources("Missing Stage provenance revision")
        with self._connect() as db:
            db.execute("""INSERT INTO urano_stage_source_provenance
                         (project_id,owner_id,source_json,stage_revision)
                         VALUES (?,?,?,?)
                         ON CONFLICT(project_id) DO UPDATE SET
                         owner_id=excluded.owner_id,
                         source_json=excluded.source_json,
                         stage_revision=excluded.stage_revision""",
                       (project_id, owner_id, json.dumps(canonical), stage_revision))

    def verified(self, owner_id: str, project_id: str, *,
                 source_slots: set[int]) -> dict:
        self.catalog.get(owner_id, project_id)
        with self._connect() as db:
            row = db.execute("""SELECT source_json,stage_revision FROM urano_stage_source_provenance
                                WHERE project_id=? AND owner_id=?""",
                             (project_id, owner_id)).fetchone()
        if row is None:
            raise UnverifiedSources("No attested Stage source provenance")
        sources = _canonical_sources(json.loads(row["source_json"]))
        if {entry["source_slot"] for entry in sources} != source_slots:
            raise UnverifiedSources("Stage provenance does not cover selected cameras")
        return {"stage_revision": row["stage_revision"], "sources": sources}
