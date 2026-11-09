"""Strict metadata-only Stage edit plan for local Companion resolution.

Never pass raw project recipes to Companion: old engine render.json contains
source_files paths from one user's disk. This is a deliberately *non-renderable*
handoff descriptor until a verified local source resolver consumes it.
"""
from __future__ import annotations

from urano.project_catalog import ProjectCatalog

MAX_CUTS = 500
MAX_DURATION_MS = 24 * 60 * 60 * 1000


class UnsafeCompanionPlan(ValueError):
    pass


def validate_cut_list(cuts: object, *, require_nonempty: bool = False) -> list[dict]:
    """Canonical path-free cuts only, shared by editor writes and Companion reads."""
    if (not isinstance(cuts, list) or len(cuts) > MAX_CUTS
            or (require_nonempty and not cuts)):
        raise UnsafeCompanionPlan("Invalid number of edits")
    safe = []
    total_ms = 0
    for cut in cuts:
        if not isinstance(cut, dict) or set(cut) != {"source_slot", "start_ms", "end_ms"}:
            raise UnsafeCompanionPlan("Invalid cut fields")
        slot, start, end = cut["source_slot"], cut["start_ms"], cut["end_ms"]
        if (type(slot) is not int or slot < 0 or slot > 15
                or type(start) is not int or type(end) is not int
                or not 0 <= start < end <= MAX_DURATION_MS):
            raise UnsafeCompanionPlan("Invalid cut timing or source index")
        total_ms += end - start
        if total_ms > 6 * 60 * 60 * 1000:
            raise UnsafeCompanionPlan("Cut plan exceeds six hours")
        safe.append({"source_slot": slot, "start_ms": start, "end_ms": end})
    return safe


def project_handoff(catalog: ProjectCatalog, owner_id: str, project_id: str) -> dict:
    project = catalog.get(owner_id, project_id)
    recipe = project.recipe
    if not isinstance(recipe, dict) or set(recipe) - {"urano_edits_v1", "notes"}:
        raise UnsafeCompanionPlan("Companion handoff needs approved edit schema")
    source = recipe.get("urano_edits_v1", {})
    if not isinstance(source, dict) or set(source) != {"cuts"}:
        raise UnsafeCompanionPlan("Invalid edit plan")
    safe = validate_cut_list(source["cuts"])
    return {
        "schema": "urano-local-handoff-descriptor-v1",
        "project_id": project.id,
        "project_revision": project.revision,
        "cuts": safe,
        "requires_local_originals": True,
        "local_source_resolution_verified": False,
        "render_ready": False,
    }
