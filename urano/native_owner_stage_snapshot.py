"""Owner-private Stage snapshot from the CURRENT Chema native edit.

The root-broker reservation identifies a stable workspace UUID, not one
native .zuckervid edit. A newly started owner worker therefore has no edit
yet; that is normal and must not be reported as a crashed Engine.

Never report a path, filename, song, member identity or host filesystem data
to the broker. The authenticated broker already knows the workspace ID.
"""
from __future__ import annotations

from pathlib import Path

from urano.native_owner_project_scope import verified_native_project

STAGES = ("ingest", "sync", "cut", "edit", "export")
STATES = frozenset((
    "pending", "idle", "queued", "running", "done", "failed",
    "blocked", "not_started",
))


def native_owner_stage_snapshot(app, *, data_root: Path, workspace_id: str) -> dict:
    """Reconcile Chema's changing edit with a stable Owner/broker workspace."""
    if not isinstance(workspace_id, str) or not workspace_id:
        raise ValueError("Trusted workspace identity unavailable")
    root = Path(data_root).resolve(strict=True)
    state = app.config.get("ZUCKER_STATE")
    if state is None:
        raise ValueError("Native Chema state unavailable")
    loaded = getattr(getattr(state, "project", None), "folder", None)

    if loaded is None:
        return {
            "ok": True, "type": "stage_snapshot",
            "project": workspace_id,
            "stages": {name: "not_started" for name in STAGES},
            "camera_count": 0,
        }

    if not isinstance(loaded, (str, Path)):
        raise ValueError("Invalid native project selection")
    verified_native_project(root, str(loaded))
    with app.test_client() as client:
        response = client.get("/api/v1/project")
    if response.status_code != 200:
        raise ValueError("Native Chema edit unavailable")
    body = response.get_json(silent=True)
    if not isinstance(body, dict):
        raise ValueError("Malformed native edit")
    inputs, stages = body.get("inputs", {}), body.get("stages", {})
    if not isinstance(inputs, dict) or not isinstance(stages, dict):
        raise ValueError("Malformed Stage data")
    videos = inputs.get("videos", [])
    if not isinstance(videos, list) or len(videos) > 200:
        raise ValueError("Invalid private Stage camera count")
    statuses = {}
    for name in STAGES:
        item = stages.get(name, {})
        if not isinstance(item, dict):
            raise ValueError("Invalid private Stage state")
        status = item.get("status", "not_started")
        if not isinstance(status, str) or status not in STATES:
            raise ValueError("Unrecognized native Stage status")
        statuses[name] = status
    return {
        "ok": True, "type": "stage_snapshot",
        "project": workspace_id,
        "stages": statuses,
        "camera_count": len(videos),
    }
