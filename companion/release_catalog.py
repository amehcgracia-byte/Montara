"""Opt-in Companion release catalog for independently verified Windows/macOS installers.

This does NOT build, sign, notarize or update a device. The publisher must
validate the platform signature before writing this operator-controlled manifest.
A GitHub Actions QA artifact alone is never a release.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Callable

from flask import Blueprint, jsonify, request, send_file

_SHA = re.compile(r"[a-f0-9]{40}\Z")
_DIGEST = re.compile(r"[a-f0-9]{64}\Z")
_VERSION = re.compile(r"[0-9]+(?:\.[0-9]+){2,3}\Z")
_FILES = re.compile(r"Montara-Companion-[A-Za-z0-9._-]{1,100}\.(?:pkg|msix|msi|exe)\Z")
_PLATFORMS = {
    ("windows", "x64"): (".msix", ".msi", ".exe"),
    ("windows", "arm64"): (".msix", ".msi", ".exe"),
    ("macos", "x64"): (".pkg",),
    ("macos", "arm64"): (".pkg",),
}
_MAX_MANIFEST_BYTES = 64 * 1024


def _read_verified_releases(root: Path, engine: str) -> list[dict]:
    """Fail closed on malformed or unverified entries. Never accept URL/paths."""
    if not _SHA.fullmatch(engine):
        return []
    manifest = root / "companion-releases.json"
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > _MAX_MANIFEST_BYTES:
        return []
    try:
        raw = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return []
    if not isinstance(raw, dict) or raw.get("schema") != 1 or raw.get("engine") != engine:
        return []
    items = raw.get("releases")
    if not isinstance(items, list) or len(items) > 8:
        return []
    result = []
    seen = set()
    for entry in items:
        if not isinstance(entry, dict):
            continue
        os_name, arch = entry.get("os"), entry.get("arch")
        key = (os_name, arch)
        filename = entry.get("filename")
        digest = entry.get("sha256")
        version = entry.get("version")
        if (key not in _PLATFORMS or key in seen
                or not isinstance(filename, str) or not _FILES.fullmatch(filename)
                or not filename.endswith(_PLATFORMS[key])
                or not isinstance(version, str) or not _VERSION.fullmatch(version)
                or not isinstance(digest, str) or not _DIGEST.fullmatch(digest)
                or entry.get("signed") is not True
                or not isinstance(entry.get("signing_identity"), str)
                or not entry["signing_identity"].strip()):
            continue
        # macOS distributables must also be Apple notarized.
        if os_name == "macos" and entry.get("notarized") is not True:
            continue
        path = root / filename
        if path.is_symlink() or not path.is_file() or path.stat().st_size < 1024:
            continue
        seen.add(key)
        result.append({"os": os_name, "arch": arch, "filename": filename,
                       "version": version, "sha256": digest, "path": path})
    return result


def companion_releases_blueprint(installer_root: str | Path,
                                 engine_sha: Callable[[], str]) -> Blueprint:
    """Attach separately to a trusted app; no installer published by default."""
    root = Path(installer_root)
    bp = Blueprint("montara_companion_verified_releases", __name__,
                   url_prefix="/montara/companion/releases")

    def catalog():
        try:
            engine = engine_sha()
        except (OSError, ValueError):
            return None, []
        if not isinstance(engine, str) or not _SHA.fullmatch(engine):
            return None, []
        return engine, _read_verified_releases(root, engine)

    @bp.get("")
    def list_releases():
        engine, entries = catalog()
        if engine is None:
            return jsonify(error="Companion engine version unavailable"), 503
        # No filesystem paths or unapproved QA artifacts exposed to the browser.
        return jsonify(engine=engine, releases=[
            {k: e[k] for k in ("os", "arch", "version", "sha256")}
            | {"download": f"/montara/companion/releases/download?os={e['os']}&arch={e['arch']}"}
            for e in entries
        ], available=bool(entries)), 200

    @bp.get("/download")
    def download_release():
        os_name, arch = request.args.get("os", ""), request.args.get("arch", "")
        if (os_name, arch) not in _PLATFORMS:
            return jsonify(error="Unsupported Companion platform"), 400
        engine, entries = catalog()
        if engine is None:
            return jsonify(error="Companion engine version unavailable"), 503
        chosen = next((x for x in entries if x["os"] == os_name and x["arch"] == arch), None)
        if chosen is None:
            return jsonify(error="No verified installer published for this platform"), 503
        # Verify release content against the operator's pinned digest immediately
        # before streaming; the publisher MUST have independently checked signing.
        digest = hashlib.sha256()
        try:
            with chosen["path"].open("rb") as package:
                for block in iter(lambda: package.read(1024 * 1024), b""):
                    digest.update(block)
        except OSError:
            return jsonify(error="Installer unavailable"), 503
        if digest.hexdigest() != chosen["sha256"]:
            return jsonify(error="Installer integrity mismatch"), 503
        response = send_file(chosen["path"], mimetype="application/octet-stream",
                             as_attachment=True, download_name=chosen["filename"],
                             max_age=0, conditional=True)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    return bp
