"""Strict, redacted Stage status produced inside the isolated Engine worker.

No browser, proxy or broker can pass paths or choose a different project.
"""
from pathlib import Path

_ALLOWED_STATES = frozenset({
    "pending", "idle", "queued", "running", "done", "failed",
    "blocked", "not_started",
})
_STAGES = ("ingest", "sync", "cut", "edit", "export")


def private_stage_snapshot(client, expected_folder: Path) -> dict:
    folder = Path(expected_folder)
    state = client.application.config.get("ZUCKER_STATE")
    loaded = getattr(getattr(state, "project", None), "folder", None)
    if (not isinstance(loaded, (str, Path))
            or Path(loaded).resolve() != folder.resolve()):
        raise ValueError("Private Engine project changed")
    inspected = client.get("/api/v1/project")
    if inspected.status_code != 200:
        raise ValueError("Engine project unavailable")
    project = inspected.get_json()
    if not isinstance(project, dict):
        raise ValueError("Invalid Engine project")
    stages = project.get("stages", {})
    inputs = project.get("inputs", {})
    if not isinstance(stages, dict) or not isinstance(inputs, dict):
        raise ValueError("Invalid private Stage data")
    statuses = {}
    for name in _STAGES:
        value = stages.get(name, {})
        if not isinstance(value, dict):
            raise ValueError("Invalid private stage")
        status = value.get("status", "not_started")
        if not isinstance(status, str) or status not in _ALLOWED_STATES:
            raise ValueError("Unrecognized Stage status")
        statuses[name] = status
    videos = inputs.get("videos", [])
    if not isinstance(videos, list) or len(videos) > 200:
        raise ValueError("Invalid camera count")
    return {
        "ok": True, "type": "stage_snapshot",
        "project": folder.name, "stages": statuses,
        "camera_count": len(videos),
    }
