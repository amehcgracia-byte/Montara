"""Validate source paths offered to the Stage mixer.

A web browser cannot grant a remote server direct access to the visitor's disk.
This boundary allows only server-owned, completed uploads and bundled fixtures
when the public preview token is enabled. It does NOT implement user ownership.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


_UPLOAD_ID = re.compile(r"[a-f0-9]{32}\Z")


def resolve_mix_sources(raw_tracks, data_root: Path, fixtures_root: Path, *, remote: bool):
    """Return authorised Paths; raise ValueError on invalid or unregistered input.

    Local development retains explicitly supplied local paths for compatibility.
    Remote mode accepts only exact completed uploads or bundled fixture files.
    """
    if not isinstance(raw_tracks, list) or not raw_tracks or len(raw_tracks) > 64:
        raise ValueError("Choose between 1 and 64 audio tracks.")
    if any(not isinstance(item, str) or not item or len(item) > 4096 for item in raw_tracks):
        raise ValueError("Invalid audio track.")
    paths = [Path(item).resolve() for item in raw_tracks]
    if any(not path.is_file() for path in paths):
        raise ValueError("One or more audio tracks are unavailable.")
    if len(set(paths)) != len(paths) or len({p.name.casefold() for p in paths}) != len(paths):
        raise ValueError("Duplicate audio tracks or filenames.")

    if not remote:
        return paths

    uploads = (Path(data_root).resolve() / "Uploads").resolve()
    fixtures = Path(fixtures_root).resolve()
    for path in paths:
        if path.is_relative_to(fixtures):
            # Fixtures are shipped by Montara itself, not uploaded by visitors.
            continue
        if not path.is_relative_to(uploads):
            raise ValueError("Track is not a registered upload.")
        relative = path.relative_to(uploads)
        if len(relative.parts) != 2 or not _UPLOAD_ID.fullmatch(relative.parts[0]):
            raise ValueError("Track is not a registered upload.")
        folder = uploads / relative.parts[0]
        try:
            record = json.loads((folder / "upload.json").read_text())
        except (OSError, ValueError, TypeError):
            raise ValueError("Track upload record is unavailable.") from None
        if record.get("complete") is not True or record.get("name") != relative.parts[1]:
            raise ValueError("Track upload is not completed or does not match the record.")
    return paths
