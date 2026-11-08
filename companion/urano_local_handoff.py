"""Translate U20's path-free cuts into the existing local original-quality renderer.

Runs exclusively INSIDE Companion on the user's computer. The remote plan
contains no paths; the local Companion binds each source via name, byte size
and edge fingerprint, validated again by VideoJobs.start before FFmpeg.

No proxy upload, server render, filesystem path from HTTP, or Engine-side
access is introduced. This is a narrow local YouTube/Stage cutting profile,
not full parity with all Engine editor controls.
"""
from __future__ import annotations

import re
import uuid

from video_recipe import validate

_ALLOWED_PLAN = {
    "schema", "project_id", "project_revision", "cuts",
    "requires_local_originals", "local_source_resolution_verified", "render_ready",
}
_ALLOWED_BODY = {"plan", "project", "master", "originals", "name", "branding"}
_ID = re.compile(r"[a-f0-9]{16}")
_AUDIO = re.compile(r"montara-render-audio-[a-f0-9]{32}\.audio")
_MAX_CUTS = 500
_MAX_MS = 86400000


def local_render_payload(body: dict, *, engine_sha: str) -> dict:
    """Reject plan/file substitutions before handing off to VideoJobs.start."""
    if not isinstance(body, dict) or set(body) != _ALLOWED_BODY:
        raise ValueError("Invalid local handoff fields")
    plan = body["plan"]
    if not isinstance(plan, dict) or set(plan) != _ALLOWED_PLAN:
        raise ValueError("Invalid private handoff descriptor")
    if plan.get("schema") != "urano-local-handoff-descriptor-v1":
        raise ValueError("Unsupported handoff descriptor")
    try:
        if str(uuid.UUID(plan["project_id"])) != plan["project_id"]:
            raise ValueError()
    except (ValueError, TypeError, AttributeError, KeyError) as exc:
        raise ValueError("Invalid project identity") from exc
    if (type(plan["project_revision"]) is not int or plan["project_revision"] < 0
            or plan["project_revision"] > 2**31 - 1):
        raise ValueError("Invalid project revision")
    if (plan["requires_local_originals"] is not True
            or plan["local_source_resolution_verified"] is not False
            or plan["render_ready"] is not False):
        raise ValueError("Unexpected handoff state")
    if not isinstance(body["project"], str) or not _ID.fullmatch(body["project"]):
        raise ValueError("Choose a local Companion project")
    if not isinstance(body["master"], str) or not _AUDIO.fullmatch(body["master"]):
        raise ValueError("Choose local master audio")
    if not isinstance(body["name"], str) or not 1 <= len(body["name"]) <= 80:
        raise ValueError("Invalid export name")
    if body["branding"] not in ("none", "montara"):
        raise ValueError("Invalid branding option")
    if not isinstance(engine_sha, str) or not re.fullmatch(r"[a-f0-9]{40}", engine_sha):
        raise ValueError("Companion editor version unavailable")

    cuts = plan["cuts"]
    if not isinstance(cuts, list) or not 1 <= len(cuts) <= _MAX_CUTS:
        raise ValueError("Empty or oversized cut plan")
    if not isinstance(body["originals"], list):
        raise ValueError("Original identities required")
    identities: dict[int, dict] = {}
    for item in body["originals"]:
        if not isinstance(item, dict) or set(item) != {"source", "original"}:
            raise ValueError("Only local original identities are allowed")
        slot, identity = item["source"], item["original"]
        if type(slot) is not int or not 0 <= slot <= 15 or slot in identities:
            raise ValueError("Invalid or duplicate source slot")
        if not isinstance(identity, dict) or set(identity) != {"name", "size", "fingerprint"}:
            raise ValueError("Invalid local source identity")
        name, size, fingerprint = identity["name"], identity["size"], identity["fingerprint"]
        if (not isinstance(name, str) or not 1 <= len(name) <= 200
                or "/" in name or "\\" in name or "\x00" in name
                or type(size) is not int or not 0 < size < 2**63
                or not isinstance(fingerprint, str)
                or not re.fullmatch("[a-f0-9]{64}", fingerprint)):
            raise ValueError("Invalid local source fingerprint")
        identities[slot] = {"name": name, "size": size, "fingerprint": fingerprint}

    used = set()
    segments = []
    master_position_ms = 0
    for cut in cuts:
        if not isinstance(cut, dict) or set(cut) != {"source_slot", "start_ms", "end_ms"}:
            raise ValueError("Invalid source cut")
        slot, start, end = cut["source_slot"], cut["start_ms"], cut["end_ms"]
        if (type(slot) is not int or slot not in identities
                or type(start) is not int or type(end) is not int
                or not 0 <= start < end <= _MAX_MS):
            raise ValueError("Cut points outside local media")
        used.add(slot)
        duration = end - start
        if master_position_ms + duration > 21600000:
            raise ValueError("Output exceeds six hours")
        segments.append({
            "source": slot,
            "clip_start_sec": start / 1000,
            "duration_sec": duration / 1000,
            "master_start_sec": master_position_ms / 1000,
            "playback_speed": 1.0,
        })
        master_position_ms += duration
    if used != set(identities):
        raise ValueError("All mapped sources must be in the cut plan")

    recipe = validate({
        "version": 1,
        "platform": "youtube",
        "engine": engine_sha,
        "sources": [{"key": slot} for slot in sorted(identities)],
        "segments": segments,
        "diagnostics": [],
    })
    return {
        "project": body["project"],
        "master": body["master"],
        "name": body["name"],
        "branding": body["branding"],
        "originals": [{"source": slot, "original": identity}
                      for slot, identity in sorted(identities.items())],
        "recipe": recipe,
    }
