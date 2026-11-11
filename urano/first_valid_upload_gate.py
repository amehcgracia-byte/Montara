"""Opt-in Owner ingress hook for first VALID JM media submission.

Mount only AFTER independent Owner session+CSRF+project authorization and
BEFORE forwarding to private JM worker. Does not parse or buffer media,
launch arbitrary workers, or modify original Chema uploader.

The callable ensure_private_worker() must be bound to a trusted Owner UUID,
never derived from HTTP headers. It verifies active worker generation using
the same root broker I27 admission already implemented.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path
from urllib.parse import unquote

from werkzeug.wrappers import Response

_FILE_NAME = re.compile(r"[^\\/\x00-\x1f]{1,200}\Z")
_DIGEST = re.compile(r"[a-f0-9]{64}\Z")
_SUPPORTED = frozenset({".mp4", ".mov", ".m4v", ".mts", ".m2ts",
                        ".mkv", ".avi", ".webm", ".wav", ".aif",
                        ".aiff", ".mp3", ".flac", ".opus", ".wv",
                        ".m4a", ".ogg"})


def valid_first_upload(environ, *, max_proxy_bytes: int = 256 * 1024**2) -> bool:
    """Only recognized new-upload calls, never dragenter, listing or polling."""
    path = environ.get("PATH_INFO")
    method = environ.get("REQUEST_METHOD")
    try:
        length = int(environ.get("CONTENT_LENGTH", "-1"))
    except (ValueError, TypeError):
        return False
    if method == "POST" and path == "/api/v1/wizard/upload":
        if not 0 < length <= 256_000_000:
            return False
        if environ.get("CONTENT_TYPE", "").split(";")[0].strip() != "application/octet-stream":
            return False
        name = unquote(environ.get("HTTP_X_ZUCKER_FILENAME", ""))
        return bool(_FILE_NAME.fullmatch(name)
                    and Path(name).suffix.lower() in _SUPPORTED)
    if method == "POST" and path == "/montara/uploads":
        # Parse only bounded metadata, NEVER media bytes. Replace the WSGI
        # stream so Chema's original resumable handler still receives the
        # exact same JSON even when admission fails.
        if (not 0 < length <= 8192
                or environ.get("CONTENT_TYPE", "").split(";")[0].strip()
                     != "application/json"):
            return False
        raw = environ["wsgi.input"].read(length)
        environ["wsgi.input"] = io.BytesIO(raw)
        if len(raw) != length:
            return False
        try:
            record = json.loads(raw)
        except (ValueError, UnicodeError):
            return False
        if not isinstance(record, dict):
            return False
        name = record.get("name")
        size = record.get("size")
        fingerprint = record.get("fingerprint")
        return bool(
            isinstance(name, str) and _FILE_NAME.fullmatch(name)
            and Path(name).suffix.lower() in _SUPPORTED
            and type(size) is int and 0 < size <= (
                max_proxy_bytes if record.get("video_preview") is True
                or name.lower().endswith((".wav.opus", ".aif.opus", ".aiff.opus"))
                else 256 * 1024**2)
            and isinstance(fingerprint, str) and
            _DIGEST.fullmatch(fingerprint)
        )
    return False


class FirstValidUploadEngineGate:
    """Authorize in the outer gateway, then ensure once per actual upload.

    No WSGI input bytes are read and no client-supplied project/worker target
    is used. A failed ensure prevents upload entirely.
    """

    def __init__(self, upstream_wsgi, *, ensure_private_worker):
        if not callable(ensure_private_worker):
            raise ValueError("Trusted Engine admission callback required")
        self.upstream = upstream_wsgi
        self.ensure = ensure_private_worker

    def __call__(self, environ, start_response):
        upload_route = (environ.get("REQUEST_METHOD") == "POST"
                        and environ.get("PATH_INFO") in
                        ("/api/v1/wizard/upload", "/montara/uploads"))
        if not upload_route:
            return self.upstream(environ, start_response)
        if not valid_first_upload(environ):
            response = Response(
                '{"error":{"message":"Invalid private media upload"}}',
                status=400, mimetype="application/json",
                headers={"Cache-Control":"no-store"})
            return response(environ, start_response)
        try:
            outcome = self.ensure()
            if (not isinstance(outcome, dict)
                    or outcome.get("ok") is not True
                    or outcome.get("state") != "ready"
                    or type(outcome.get("generation")) is not int
                    or outcome["generation"] < 1):
                raise RuntimeError("Private Engine not ready")
        except (RuntimeError, OSError, ValueError, TimeoutError):
            response = Response(
                '{"error":{"message":"Private Engine not ready"}}',
                status=503, mimetype="application/json",
                headers={"Cache-Control": "no-store"})
            return response(environ, start_response)
        return self.upstream(environ, start_response)
