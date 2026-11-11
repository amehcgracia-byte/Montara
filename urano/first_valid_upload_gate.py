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


def valid_first_upload(environ, *, max_proxy_bytes: int = 256 * 1024**2,
                       rejection_codes: list[str] | None = None) -> bool:
    """Validate media metadata only; never interpret untrusted names as paths.

    Optional rejection codes distinguish unsupported format, size or metadata
    to the authenticated Owner. No filename, fingerprint or original path is
    included in the diagnostic.
    """
    def reject(code: str) -> bool:
        if rejection_codes is not None:
            rejection_codes.append(code)
        return False

    path = environ.get("PATH_INFO")
    method = environ.get("REQUEST_METHOD")
    try:
        length = int(environ.get("CONTENT_LENGTH", "-1"))
    except (ValueError, TypeError):
        return reject("invalid_content_length")
    if method == "POST" and path == "/api/v1/wizard/upload":
        if not 0 < length <= 256_000_000:
            return reject("invalid_or_oversize_direct_media")
        if environ.get("CONTENT_TYPE", "").split(";")[0].strip() != "application/octet-stream":
            return reject("invalid_direct_content_type")
        raw_name = environ.get("HTTP_X_ZUCKER_FILENAME", "")
        if not raw_name:
            return reject("missing_media_filename_header")
        try:
            name = unquote(raw_name, errors="strict")
        except (UnicodeDecodeError, TypeError, ValueError):
            return reject("invalid_media_filename_encoding")
        if not _FILE_NAME.fullmatch(name):
            return reject("invalid_media_name")
        if Path(name).suffix.lower() not in _SUPPORTED:
            return reject("unsupported_media_extension")
        return True
    if method == "POST" and path == "/montara/uploads":
        if not 0 < length <= 8192:
            return reject("invalid_resumable_metadata_length")
        if environ.get("CONTENT_TYPE", "").split(";")[0].strip() != "application/json":
            return reject("invalid_resumable_content_type")
        raw = environ["wsgi.input"].read(length)
        environ["wsgi.input"] = io.BytesIO(raw)
        if len(raw) != length:
            return reject("incomplete_resumable_metadata")
        try:
            record = json.loads(raw)
        except (ValueError, UnicodeError):
            return reject("invalid_resumable_json")
        if not isinstance(record, dict):
            return reject("invalid_resumable_fields")
        name = record.get("name")
        size = record.get("size")
        fingerprint = record.get("fingerprint")
        if not isinstance(name, str) or not _FILE_NAME.fullmatch(name):
            return reject("invalid_media_name")
        if Path(name).suffix.lower() not in _SUPPORTED:
            return reject("unsupported_media_extension")
        if type(size) is not int or size <= 0:
            return reject("invalid_media_size")
        # Companion's lossless audio output retains the source audio
        # extension before .flac/.wv. Apply the already-configured private
        # proxy ceiling to those bounded derivatives as well as to video
        # previews. Raw .mp4/.mov without video_preview remain at 256 MiB;
        # this never authorizes an implicit original-video upload.
        lossless_audio_derivative = bool(re.search(
            r"\.(?:wav|aif|aiff|mp3|m4a|flac|ogg|opus|wv)\.(?:flac|wv)\Z",
            name, re.IGNORECASE))
        compact_audio_derivative = name.lower().endswith(
            (".wav.opus", ".aif.opus", ".aiff.opus"))
        is_video_proxy = (record.get("video_preview") is True
                          and name.lower().endswith(".small.mp4")
                          and isinstance(record.get("original"), dict))
        allowed_size = (max_proxy_bytes if is_video_proxy
                        or lossless_audio_derivative or compact_audio_derivative
                        else 256 * 1024**2)
        if size > allowed_size:
            return reject("media_exceeds_private_transfer_limit")
        if not isinstance(fingerprint,str) or not _DIGEST.fullmatch(fingerprint):
            return reject("invalid_media_fingerprint")
        return True
    return reject("invalid_upload_operation")


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
