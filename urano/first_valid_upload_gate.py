"""Opt-in Owner ingress hook for first VALID JM media submission.

Mount only AFTER independent Owner session+CSRF+project authorization and
BEFORE forwarding to private JM worker. Does not parse or buffer media,
launch arbitrary workers, or modify original Chema uploader.

The callable ensure_private_worker() must be bound to a trusted Owner UUID,
never derived from HTTP headers. It verifies active worker generation using
the same root broker I27 admission already implemented.
"""
from __future__ import annotations

import json
import re

from werkzeug.wrappers import Response

_FILE_NAME = re.compile(r"[^\\/\x00-\x1f]{1,200}\Z")
_DIGEST = re.compile(r"[a-f0-9]{64}\Z")
_SUPPORTED = frozenset({".mp4", ".mov", ".m4v", ".mts", ".mkv",
                        ".avi", ".webm", ".wav", ".aif", ".aiff",
                        ".mp3", ".flac", ".opus", ".wv"})


def valid_first_upload(environ) -> bool:
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
        from urllib.parse import unquote
        name = unquote(environ.get("HTTP_X_ZUCKER_FILENAME", ""))
        return bool(_FILE_NAME.fullmatch(name))
    if method == "POST" and path == "/montara/uploads":
        # This endpoint's small metadata body is validated by the real JM
        # upload implementation. Do not consume its WSGI input here.
        return 0 < length <= 8192 and environ.get(
            "CONTENT_TYPE", "").split(";")[0].strip() == "application/json"
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
        if not valid_first_upload(environ):
            return self.upstream(environ, start_response)
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
