"""Reviewable native Chema New/Latest boundary inside a private Owner worker.

Do not mount on a public WSGI server. Authentication, CSRF, owner->worker
admission, OS isolation and the trusted data_root are enforced by the
surrounding Owner/broker. This module only fences project paths and media
arguments before handing requests to Chema's ORIGINAL handlers.

Crucially:
  - New is forwarded untouched; it never deletes saved native projects.
  - The native /montara/recovery/latest handler runs unchanged and searches
    Projects AND Sessions within the worker's private data_root.
  - A browser must not open a project or use media outside that data_root.

This first gate covers the New/Latest/Stage draft transition. Other original
API families (Music, Push, Show, native export, etc.) require a separate
route-by-route review before the complete UI can be published.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

from werkzeug.wrappers import Response

from urano.native_owner_project_scope import (
    UnsafeNativeProject,
    verified_native_project,
)

_MAX_BODY = 256_000
_SESSION_ID = re.compile(r"[a-f0-9]{12}\Z")
_UPLOAD_ID = re.compile(r"[a-f0-9]{32}\Z")
_PROJECT_BODY = {
    "/api/v1/wizard/projects/open",
    "/api/v1/wizard/projects/delete",
}
_MEDIA_BODY = {
    "/api/v1/wizard/draft",
    "/api/v1/wizard/prepare",
    "/api/v1/wizard/start",
}
_GUARDED_POST = _PROJECT_BODY | _MEDIA_BODY | {
    "/api/v1/wizard/projects/new",
}
_GUARDED_GET = {"/api/v1/wizard/status"}


class UntrustedNativeWorkspace(ValueError):
    """An incoming JM request references a different workspace."""


def verified_private_media(data_root: Path, supplied: str) -> Path:
    """Require a regular local file inside a reviewed Owner-owned data area.

    Uploads created by Chema's unmodified upload endpoints and files generated
    inside the private Sessions/Projects folders are legitimate. No arbitrary
    fixture roots, host absolute paths, symlinks, ../, or browser file paths.
    """
    if (not isinstance(supplied, str) or not supplied or len(supplied) > 4096
            or "\x00" in supplied):
        raise UntrustedNativeWorkspace("Untrusted private media")
    try:
        root = Path(data_root).resolve(strict=True)
        path = Path(supplied)
        if (not path.is_absolute() or "." in path.parts or ".." in path.parts
                or path.is_symlink() or not path.is_file()
                or path.stat().st_size <= 0):
            raise UntrustedNativeWorkspace("Untrusted private media")
        relative = path.relative_to(root)
        parts = relative.parts
        if len(parts) < 2 or parts[0] not in (
                "WizardUploads", "Uploads", "Sessions", "Projects"):
            raise UntrustedNativeWorkspace("Untrusted private media")
        # Reject a linked intermediate folder even when the canonical file
        # appears to be regular or points back into this owner namespace.
        current = root
        for component in parts:
            current = current / component
            if current.is_symlink():
                raise UntrustedNativeWorkspace("Linked private media")
        if path.resolve(strict=True) != root.joinpath(*parts):
            raise UntrustedNativeWorkspace("Untrusted private media")
        if parts[0] == "WizardUploads":
            if len(parts) != 2:
                raise UntrustedNativeWorkspace("Invalid wizard upload")
        elif parts[0] == "Uploads":
            if len(parts) != 3 or not _UPLOAD_ID.fullmatch(parts[1]):
                raise UntrustedNativeWorkspace("Invalid completed upload")
            metadata = root / "Uploads" / parts[1] / "upload.json"
            if metadata.is_symlink() or not metadata.is_file():
                raise UntrustedNativeWorkspace("Unverified upload")
            if not 1 <= metadata.stat().st_size <= 8192:
                raise UntrustedNativeWorkspace("Unverified upload")
            info = json.loads(metadata.read_text(encoding="utf-8"))
            if (not isinstance(info, dict) or info.get("complete") is not True
                    or parts[2] != info.get("restored", info.get("name"))):
                raise UntrustedNativeWorkspace("Unverified upload")
        elif parts[0] == "Sessions":
            if len(parts) < 3 or not _SESSION_ID.fullmatch(parts[1]):
                raise UntrustedNativeWorkspace("Unknown private session")
            metadata = root / "Sessions" / parts[1] / "session.json"
            if (metadata.is_symlink() or not metadata.is_file()
                    or not 1 <= metadata.stat().st_size <= 8 * 1024 * 1024):
                raise UntrustedNativeWorkspace("Unknown private session")
            session = json.loads(metadata.read_text(encoding="utf-8"))
            if not isinstance(session, dict) or session.get("id") != parts[1]:
                raise UntrustedNativeWorkspace("Unknown private session")
        else:
            if len(parts) < 3:
                raise UntrustedNativeWorkspace("Invalid saved media source")
            verified_native_project(root, str(root / "Projects" / parts[1]))
        return path
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise UntrustedNativeWorkspace("Untrusted private media") from exc


class NativeOwnerWorkspaceGate:
    """Minimal request validation; do not replace Chema's New/Latest logic."""

    def __init__(self, application, *, data_root: Path):
        root = Path(data_root)
        if root.is_symlink() or not root.is_dir():
            raise UntrustedNativeWorkspace("Private workspace unavailable")
        self.root = root.resolve(strict=True)
        if self.root.stat().st_mode & 0o077:
            raise UntrustedNativeWorkspace("Private workspace permissions")
        if not callable(application):
            raise TypeError("A native WSGI application is required")
        self.app = application

    def __call__(self, environ, start_response):
        method = environ.get("REQUEST_METHOD")
        path = environ.get("PATH_INFO")
        if method == "GET" and path in _GUARDED_GET:
            # Chema may poll another *saved* project while a new video starts.
            # The query's project_id must still be owner-local.
            from urllib.parse import parse_qs
            query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
            ids = query.get("project_id", [])
            if (len(ids) > 1 or
                    (ids and ids[0] not in ("", None)
                     and not self._safe_project(ids[0]))):
                return self._deny(environ, start_response)
            return self.app(environ, start_response)
        if method != "POST" or path not in _GUARDED_POST:
            # All other APIs require review at the *outer* CSRF/Owner gateway.
            return self.app(environ, start_response)
        try:
            length = int(environ.get("CONTENT_LENGTH") or "")
            if not 0 <= length <= _MAX_BODY:
                raise UntrustedNativeWorkspace("Invalid body size")
            data = environ["wsgi.input"].read(length)
            if len(data) != length:
                raise UntrustedNativeWorkspace("Incomplete request")
            body = json.loads(data) if data else {}
            if not isinstance(body, dict):
                raise UntrustedNativeWorkspace("Invalid native request")
            if path == "/api/v1/wizard/projects/new":
                if body:
                    raise UntrustedNativeWorkspace("New needs no client project")
            elif path in _PROJECT_BODY:
                if set(body) != {"path"}:
                    raise UntrustedNativeWorkspace("Invalid project selection")
                verified_native_project(self.root, body["path"])
            else:
                self._validate_media_request(path, body)
        except (KeyError, ValueError, TypeError, OSError,
                json.JSONDecodeError, UnsafeNativeProject):
            return self._deny(environ, start_response)
        copy = dict(environ)
        copy["wsgi.input"] = io.BytesIO(data)
        copy["CONTENT_LENGTH"] = str(len(data))
        return self.app(copy, start_response)

    def _safe_project(self, path: str) -> bool:
        try:
            verified_native_project(self.root, path)
            return True
        except (ValueError, UnsafeNativeProject):
            return False

    def _validate_media_request(self, path: str, body: dict):
        project = body.get("project_id")
        if path == "/api/v1/wizard/draft":
            # The original Chema handler creates a new project for null ID.
            if project not in (None, ""):
                verified_native_project(self.root, project)
        elif not isinstance(project, str) or not project:
            # Prepare/start belong to an existing saved project.
            raise UntrustedNativeWorkspace("Selected project unavailable")
        else:
            verified_native_project(self.root, project)
        videos = body.get("videos", [])
        if (not isinstance(videos, list) or len(videos) > 200
                or any(not isinstance(x, str) for x in videos)):
            raise UntrustedNativeWorkspace("Invalid video sources")
        for item in videos:
            verified_private_media(self.root, item)
        audio_paths = body.get("audio_paths", [])
        if (not isinstance(audio_paths, list) or len(audio_paths) > 128
                or any(not isinstance(x, str) for x in audio_paths)):
            raise UntrustedNativeWorkspace("Invalid audio sources")
        for item in (body.get("master"), body.get("songs"),
                     body.get("spherical_source_path"), *audio_paths):
            if item not in (None, ""):
                verified_private_media(self.root, item)

    @staticmethod
    def _deny(environ, start_response):
        return Response(
            json.dumps({"error": {"code": "private_workspace",
                                   "message": "Private workspace resource unavailable"}}),
            status=403,
            content_type="application/json",
            headers={"Cache-Control": "no-store",
                     "X-Content-Type-Options": "nosniff"},
        )(environ, start_response)
