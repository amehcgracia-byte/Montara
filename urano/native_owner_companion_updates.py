"""Pinned public H4 Companion beta release files. No project/owner data."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from flask import Blueprint, Response, abort, request

def companion_update_blueprint(*, https_origin: str, release_dir: Path) -> Blueprint:
    root=Path(release_dir).resolve(strict=True)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Operator release directory required")
    manifest=root/"manifest.json"
    archive=root/"package.zip"
    if not manifest.is_file() or not archive.is_file() or manifest.is_symlink() or archive.is_symlink():
        raise ValueError("Exact Companion release files required")
    data=json.loads(manifest.read_text())
    if data.get("channel")!="montara-h4-windows" or not isinstance(data.get("sha256"),str):
        raise ValueError("Invalid release manifest")
    bundle_bytes=archive.read_bytes()
    if hashlib.sha256(bundle_bytes).hexdigest()!=data["sha256"] or len(bundle_bytes)!=data["bytes"]:
        raise ValueError("Release digest/size mismatch")
    bootstrap=root/"bootstrap.zip"
    if bootstrap.is_symlink() or not bootstrap.is_file():
        raise ValueError("Pinned bootstrap package required")
    bootstrap_bytes=bootstrap.read_bytes()
    if (hashlib.sha256(bootstrap_bytes).hexdigest()!=data.get("bootstrap_sha256")
            or len(bootstrap_bytes)!=data.get("bootstrap_bytes")):
        raise ValueError("Invalid H4 bootstrap integrity")
    encoded=manifest.read_bytes()
    bp=Blueprint("montara_h4_companion_updates",__name__,url_prefix="/urano/v1/companion-updates")
    def serve(blob: bytes, mimetype: str):
        if request.host_url.rstrip("/")!=https_origin:
            abort(403)
        response=Response(blob,mimetype=mimetype)
        response.headers["Cache-Control"]="public, max-age=60"
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Content-Security-Policy"]="default-src 'none'"
        response.headers["Content-Disposition"]="attachment" if mimetype=="application/zip" else "inline"
        return response
    @bp.get("/manifest.json")
    def manifest_file():
        return serve(encoded,"application/json")
    @bp.get("/package.zip")
    def release_file():
        return serve(bundle_bytes,"application/zip")
    @bp.get("/bootstrap.zip")
    def initial_install():
        return serve(bootstrap_bytes,"application/zip")
    return bp
