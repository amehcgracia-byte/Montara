"""I42: adapt Chema's ORIGINAL first Stage wizard to an already-open Owner UUID.

An opt-in WSGI middleware INSIDE one isolated per-owner JM worker.
The JM UI calls POST /wizard/projects/new then /wizard/draft(project_id:null).
That would create a SECOND unrelated Engine project; here we keep the already
authorized empty project and let the original Engine register proxy inputs.
No changes to JM HTML, JS, Engine, or editor UX.

NOT browser authentication, proxy/media authorization, a general rewrite proxy,
or a substitute for a separate tenant OS identity.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
from werkzeug.wrappers import Response


def _json_error(start_response, reason: str, status=409):
    return Response(
        json.dumps({"error": {"code": "owner_project_gate",
                               "message": reason}}, separators=(",", ":")),
        status=status, mimetype="application/json",
        headers={"Cache-Control": "no-store"},
    )


def _vetted_stage_video(path_value, data_root: Path) -> bool:
    """Require real per-worker uploaded bytes; never trust arbitrary JSON paths.

    Original JM stores ordinary wizard uploads under WizardUploads and chunked
    Companion proxies under Uploads/<upload-id>. Keep this independent from
    cloud providers and Companion installation paths.
    """
    import re
    if not isinstance(path_value, str) or len(path_value) > 4096:
        return False
    raw = Path(path_value)
    if not raw.is_absolute() or raw.is_symlink():
        return False
    try:
        root = Path(data_root).resolve(strict=True)
        parts = raw.relative_to(root).parts
        if not parts or any(part in ("", ".", "..") for part in parts):
            return False
        if not raw.is_file() or raw.stat().st_size <= 0:
            return False
        if any(parent.is_symlink() for parent in (raw, *raw.parents)
               if parent == root or root in parent.parents):
            return False
        if raw.resolve(strict=True) != root.joinpath(*parts):
            return False
        if len(parts) == 2 and parts[0] == "WizardUploads":
            return True
        if (len(parts) != 3 or parts[0] != "Uploads"
                or re.fullmatch(r"[a-f0-9]{32}", parts[1]) is None):
            return False
        upload = root / "Uploads" / parts[1] / "upload.json"
        if upload.is_symlink() or not upload.is_file() or upload.stat().st_size > 8192:
            return False
        metadata = json.loads(upload.read_text(encoding="utf-8"))
        return (isinstance(metadata, dict)
                and metadata.get("complete") is True
                and parts[2] == metadata.get("restored", metadata.get("name"))
                and raw.stat().st_size > 0)
    except (ValueError, OSError, TypeError, json.JSONDecodeError):
        return False


class OwnerFirstStageWizard:
    """Fail-closed reuse of the Owner UUID's initially opened empty project."""

    def __init__(self, application, *, owner_project_folder: Path):
        self.app = application
        self.folder = Path(owner_project_folder).resolve(strict=True)
        if self.folder.is_symlink() or not (self.folder / "project.json").is_file():
            raise ValueError("No trusted Owner Engine project")

    def _opened(self):
        state = self.app.config.get("ZUCKER_STATE")
        current = getattr(state, "project", None)
        folder = getattr(current, "folder", None)
        if (not isinstance(folder, (Path, str))
                or Path(folder).is_symlink()
                or Path(folder).resolve() != self.folder):
            return None
        return current

    @staticmethod
    def _empty(project) -> bool:
        if not isinstance(getattr(project, "data", None), dict):
            return False
        data = project.data
        inputs = data.get("inputs")
        stages = data.get("stages")
        settings = data.get("settings", {})
        return (
            isinstance(inputs, dict)
            and inputs.get("master") is None
            and inputs.get("songs") is None
            and inputs.get("videos") == []
            and isinstance(stages, dict)
            and bool(stages)
            and all(isinstance(s, dict) and s.get("status") == "pending"
                    for s in stages.values())
            and isinstance(settings, dict)
            and not settings.get("wizard")
        )

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO")
        method = environ.get("REQUEST_METHOD")
        if method != "POST" or path not in (
                "/api/v1/wizard/projects/new", "/api/v1/wizard/draft"):
            return self.app(environ, start_response)
        project = self._opened()
        if project is None:
            return _json_error(start_response,
                               "Private Owner Engine project unavailable")(environ,start_response)
        if path == "/api/v1/wizard/projects/new":
            if not self._empty(project):
                return _json_error(start_response,
                                   "Create a new private Montara project first")(environ,start_response)
            # JM normally clears state.project here. We preserve the already
            # opened, authenticated Owner UUID so next draft never creates an
            # unrelated Engine project.
            response = Response('{"ok":true}', mimetype="application/json",
                                headers={"Cache-Control": "no-store"})
            return response(environ, start_response)
        try:
            length = int(environ.get("CONTENT_LENGTH") or "0")
            if not 0 < length <= 256_000:
                raise ValueError("Invalid draft metadata size")
            raw = environ["wsgi.input"].read(length)
            if len(raw) != length:
                raise ValueError("Truncated editor request")
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise ValueError("Invalid editor request")
            supplied_id = body.get("project_id")
            if supplied_id not in (None, "", str(self.folder)):
                raise ValueError("Foreign JM Engine project")
            if body.get("platform") != "youtube":
                raise ValueError("Only Stage draft supported here")
            videos = body.get("videos")
            if (not isinstance(videos, list) or not videos
                    or len(videos) > 200
                    or any(not _vetted_stage_video(path, self.folder.parent.parent)
                           for path in videos)):
                raise ValueError("Stage sources must be verified worker uploads")
            # Original JM also accepts master, songs and audio_paths.
            # Never let a Stage draft smuggle an arbitrary host file through
            # an audio field after video paths have been checked.
            audio = body.get("audio_paths", [])
            if not isinstance(audio, list) or len(audio) > 100:
                raise ValueError("Invalid Stage audio paths")
            for supplied in (body.get("master", ""), body.get("songs", ""), *audio):
                if supplied in ("", None):
                    continue
                if not _vetted_stage_video(supplied, self.folder.parent.parent):
                    raise ValueError("Stage audio must be verified worker uploads")
            # Initial browser draft supplies null. Once media has been saved,
            # only an explicit resume of this same physical project is safe.
            if supplied_id in (None, "") and not self._empty(project):
                raise ValueError("Existing Owner project must be resumed, not overwritten")
        except (TypeError, ValueError, KeyError, UnicodeError):
            return _json_error(start_response, "Invalid private Stage draft", 400)(environ,start_response)
        body["project_id"] = str(self.folder)
        patched = json.dumps(body, separators=(",", ":"), allow_nan=False).encode()
        environ = dict(environ)
        environ["wsgi.input"] = io.BytesIO(patched)
        environ["CONTENT_LENGTH"] = str(len(patched))
        return self.app(environ, start_response)
