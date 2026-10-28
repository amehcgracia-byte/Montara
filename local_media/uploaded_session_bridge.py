"""Private bridge: finished Montara upload IDs -> local proxy preparation.

Does not add an HTTP endpoint, read user-chosen server paths or expose originals.
The existing upload pipeline remains the only owner of uploaded files.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from local_media.session_proxies import prepare_session

_UPLOAD_ID = re.compile(r"[a-f0-9]{32}\Z")
_VIDEO = {".mp4", ".mov", ".mkv", ".webm", ".mts", ".m2ts"}


def resolve_completed_upload(data_root: str | Path, upload_id: str) -> Path:
    if not isinstance(upload_id, str) or not _UPLOAD_ID.fullmatch(upload_id):
        raise ValueError("Invalid upload identifier")
    root = Path(data_root).resolve() / "Uploads" / upload_id
    try:
        meta = json.loads((root / "upload.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Unknown upload") from exc
    if not isinstance(meta, dict) or meta.get("complete") is not True:
        raise ValueError("Upload is not complete")
    name = meta.get("name")
    if (not isinstance(name, str) or not name or Path(name).name != name
            or "/" in name or "\\" in name or Path(name).suffix.lower() not in _VIDEO):
        raise ValueError("Upload is not a supported video")
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Uploaded video unavailable")
    if path.resolve().parent != root.resolve():
        raise ValueError("Upload escaped its private directory")
    if not isinstance(meta.get("size"), int) or isinstance(meta["size"], bool) or path.stat().st_size != meta["size"]:
        raise ValueError("Upload size mismatch")
    return path


def prepare_uploaded_videos(data_root: str | Path, upload_ids: list[str], *, sphere=False) -> dict:
    """Existing uploaded originals -> existing proxy cache; returns public IDs only.

    Caller must enforce authenticated project/session ownership before invocation.
    This is an internal helper, not a public authorization boundary.
    """
    if not isinstance(upload_ids, list) or not 1 <= len(upload_ids) <= 64:
        raise ValueError("Expected 1-64 completed upload IDs")
    if len(set(upload_ids)) != len(upload_ids):
        raise ValueError("Duplicate upload ID")
    paths = [resolve_completed_upload(data_root, item) for item in upload_ids]
    cache = Path(data_root).resolve() / "Cache" / "LocalMedia"
    return prepare_session(paths, cache, sphere=sphere)
