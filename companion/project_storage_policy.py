"""Replaceable, no-side-effects local project location policy.

Does NOT move old projects, modify Companion HOME, create directories or alter
the current /projects picker. A future UI can consume this small policy from
Companion without changing any Engine, render or Owner code.

Use a user-confirmed destination for new projects. Existing Companion project
IDs remain mapped in their original HOME/projects.json.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


class InvalidProjectRoot(ValueError):
    pass


def suggested_root(*, home: Path | None = None,
                   environ: dict[str, str] | None = None,
                   preference: str | None = None) -> Path:
    """Propose, never silently select/create or move a project directory.

    Precedence: explicit user preference > environment configuration >
    platform's Documents. Any final choice still goes through local picker.
    """
    env = os.environ if environ is None else environ
    local_home = Path.home() if home is None else Path(home)
    configured = preference or env.get("MONTARA_PROJECTS_ROOT")
    if configured:
        root = Path(configured).expanduser()
        if not root.is_absolute():
            raise InvalidProjectRoot("Project root must be an absolute path")
        return root
    # XDG user-dirs resolves redirection only when it is supplied by the
    # shell/session; otherwise leave the Documents default editable in the UI.
    documents = env.get("MONTARA_DOCUMENTS_ROOT")
    if documents:
        root = Path(documents).expanduser()
        if not root.is_absolute():
            raise InvalidProjectRoot("Documents root must be absolute")
        return root / "Montara"
    return local_home / "Documents" / "Montara"


def load_preferred_root(settings_file: Path) -> str | None:
    """Read user choice without touching existing Companion project records."""
    file = Path(settings_file)
    if file.is_symlink():
        raise InvalidProjectRoot("Linked settings file rejected")
    if not file.is_file():
        return None
    if file.stat().st_size > 8192:
        raise InvalidProjectRoot("Project settings file too large")
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise InvalidProjectRoot("Invalid project settings file") from exc
    if not isinstance(data, dict):
        raise InvalidProjectRoot("Invalid project settings")
    value = data.get("projects_root")
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        raise InvalidProjectRoot("Invalid preferred project root")
    return str(suggested_root(preference=value))


def project_folder(root: Path, project_name: str) -> Path:
    """Pure folder proposal; does not create anything and cannot escape root.

    Future Companion should handle collisions/reconnecting by trusted local
    project IDs, not by blindly reusing a display name.
    """
    if not isinstance(project_name, str):
        raise InvalidProjectRoot("Project name must be text")
    import re
    safe = re.sub(r"[^\w .,()+-]", "-", project_name).strip(" .")[:80]
    if not safe or safe in (".", ".."):
        raise InvalidProjectRoot("Invalid project name")
    base = Path(root)
    if not base.is_absolute():
        raise InvalidProjectRoot("Project root must be absolute")
    return base / safe
