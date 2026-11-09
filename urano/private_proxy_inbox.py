"""Opt-in, owner-scoped staging of proxy bytes. NEVER an original attestation.

This endpoint accepts a browser-provided identity claim only as UNTRUSTED metadata.
StageSourceProvenance.register_trusted() must NOT be called from this module.
No original bytes, filenames as storage paths, arbitrary Engine commands or
public readback of the staged proxy are accepted.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from flask import Blueprint, jsonify, request

from urano.project_catalog import ProjectCatalog, ProjectNotFound
from urano.session_auth import SESSION_COOKIE, SessionStore
from urano.stage_source_provenance import StageSourceProvenance, UnverifiedSources, _canonical_sources
from urano.companion_receipt_auth import CompanionReceiptVerifier

_MAX_PROXY_BYTES = 128 * 1024 * 1024
_SLOT = re.compile(r"^(?:[0-9]|1[0-5])$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def private_proxy_inbox_blueprint(catalog: ProjectCatalog, sessions: SessionStore,
                                  *, https_origin: str, staging_root: Path,
                                  stage_provenance: StageSourceProvenance | None = None,
                                  receipt_verifier: CompanionReceiptVerifier | None = None) -> Blueprint:
    parsed = urlsplit(https_origin)
    if (parsed.scheme != "https" or not parsed.netloc or parsed.path
            or parsed.query or parsed.fragment or parsed.username or parsed.password):
        raise ValueError("Canonical HTTPS origin required")
    root = Path(staging_root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Existing private staging root required")
    bp = Blueprint("urano_proxy_inbox", __name__, url_prefix="/urano/v1/proxy-inbox")

    @bp.put("/projects/<project_id>/slots/<slot>")
    def receive(project_id: str, slot: str):
        session = sessions.verify(request.cookies.get(SESSION_COOKIE))
        if session is None:
            return jsonify(error="Authentication required"), 401
        if (request.host_url.rstrip("/") != https_origin
                or request.headers.get("Origin") != https_origin):
            return jsonify(error="Trusted HTTPS same-origin required"), 403
        if not session.matches_csrf(request.headers.get("X-Urano-CSRF")):
            return jsonify(error="Invalid CSRF token"), 403
        try:
            catalog.get(session.owner_id, project_id)
        except (ValueError, ProjectNotFound):
            return jsonify(error="Project unavailable"), 404
        if not _SLOT.fullmatch(slot):
            return jsonify(error="Invalid camera slot"), 400
        length = request.content_length
        if (type(length) is not int or not 0 < length <= _MAX_PROXY_BYTES
                or request.mimetype != "video/mp4"):
            return jsonify(error="Unsupported proxy size or media type"), 413
        expected = request.headers.get("X-Urano-Proxy-SHA256", "")
        if not _DIGEST.fullmatch(expected):
            return jsonify(error="Missing proxy digest"), 400
        claim = request.headers.get("X-Urano-Original-Claim", "")
        if len(claim.encode("utf-8")) > 1024:
            return jsonify(error="Invalid original metadata"), 400
        try:
            original = json.loads(claim)
            _canonical_sources([{"source_slot": int(slot), "original": original}])
        except (ValueError, TypeError, UnverifiedSources):
            return jsonify(error="Invalid original metadata"), 400

        authenticated_receipt = None
        if receipt_verifier is not None:
            envelope_text = request.headers.get("X-Urano-Signed-Receipt", "")
            if not envelope_text or len(envelope_text.encode("utf-8")) > 4096:
                return jsonify(error="Signed Companion receipt required"), 403
            try:
                envelope = json.loads(envelope_text)
                authenticated_receipt = receipt_verifier.verify(
                    session.owner_id, project_id, int(slot), expected,
                    original, envelope)
            except (UnverifiedSources, ValueError, TypeError, OSError):
                return jsonify(error="Companion source receipt not trusted"), 403

        # Derive all paths from verified principal and UUID, never from filename.
        owner_token = hashlib.sha256(session.owner_id.encode()).hexdigest()
        folder = root / owner_token / project_id
        if (folder.is_symlink() or folder.parent.is_symlink()
                or root.is_symlink()):
            return jsonify(error="Storage unavailable"), 409
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        folder.chmod(0o700)
        temp_name = None
        digest = hashlib.sha256()
        copied = 0
        try:
            # Flask's default owner API cap is 300 KB for JSON endpoints.
            # Only this authenticated binary route permits a bounded proxy.
            request.max_content_length = _MAX_PROXY_BYTES
            with tempfile.NamedTemporaryFile(
                    dir=folder, prefix=".incoming-", suffix=".part",
                    delete=False) as temporary:
                temp_name = Path(temporary.name)
                os.chmod(temp_name, 0o600)
                while True:
                    block = request.stream.read(min(1024 * 1024, length - copied))
                    if not block:
                        break
                    copied += len(block)
                    if copied > length or copied > _MAX_PROXY_BYTES:
                        raise ValueError("Proxy too large")
                    digest.update(block)
                    temporary.write(block)
            if copied != length or digest.hexdigest() != expected:
                return jsonify(error="Proxy bytes do not match digest"), 422
            # All old source certificates become invalid BEFORE replacement.
            # Even identical media re-uploads require an independent Stage
            # recheck. If invalidation fails, do not publish staged bytes.
            if stage_provenance is not None:
                stage_provenance.invalidate_trusted(session.owner_id, project_id)
            target = folder / f"slot-{int(slot)}-{expected}.mp4"
            # Staged bytes are immutable by digest; untrusted identity claims
            # NEVER cause certification. Replacing an existing same-hash file
            # only preserves its contents.
            os.replace(temp_name, target)
            temp_name = None
            pending = folder / f"slot-{int(slot)}-{expected}.json"
            record = {
                "source_slot": int(slot), "proxy_sha256": expected,
                "original_claim": original, "attested": False,
                "bytes": copied,
                "receipt_authenticated": authenticated_receipt is not None,
            }
            with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=folder,
                    prefix=".metadata-", suffix=".part", delete=False) as metadata:
                tmp_meta = Path(metadata.name)
                os.chmod(tmp_meta, 0o600)
                json.dump(record, metadata, separators=(",", ":"))
            os.replace(tmp_meta, pending)
            result = jsonify(source_slot=int(slot), proxy_sha256=expected,
                             bytes=copied, attested=False,
                             receipt_authenticated=authenticated_receipt is not None)
            result.headers["Cache-Control"] = "no-store"
            return result, 201
        except (OSError, ValueError):
            return jsonify(error="Proxy could not be staged"), 409
        finally:
            if temp_name is not None:
                temp_name.unlink(missing_ok=True)

    return bp
