"""Preflight the native Chema storage preferences for one private Owner UID.

Chema intentionally supports desktop paths and external disks; those are
correct for local installations but must not let a cloud worker escape its
private StateDirectory. This preflight runs BEFORE creating Chema's app.
It doesn't alter original config, UI or source files.
"""
from __future__ import annotations

import json
from pathlib import Path


class UnsafeOwnerStorage(ValueError):
    """An external or linked native project/source root cannot be authorized."""


def verify_owner_storage_config(data_root: Path) -> None:
    root = Path(data_root)
    if root.is_symlink() or not root.is_dir() or root.stat().st_mode & 0o077:
        raise UnsafeOwnerStorage("Private StateDirectory not verified")
    root = root.resolve(strict=True)
    config = root / "config.json"
    if config.is_symlink():
        raise UnsafeOwnerStorage("Linked native storage configuration")
    if not config.exists():
        return
    if not config.is_file() or not 1 <= config.stat().st_size <= 262144:
        raise UnsafeOwnerStorage("Invalid native storage configuration")
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError, OSError) as exc:
        raise UnsafeOwnerStorage("Unreadable native storage configuration") from exc
    if not isinstance(data, dict):
        raise UnsafeOwnerStorage("Invalid native storage configuration")

    def contained(value) -> Path:
        if not isinstance(value, str) or not value or len(value) > 4096:
            raise UnsafeOwnerStorage("Untrusted native path")
        path = Path(value)
        if (not path.is_absolute() or "." in path.parts or ".." in path.parts
                or path.is_symlink()):
            raise UnsafeOwnerStorage("Untrusted native path")
        # Reject links in EVERY existing parent, not just the final path.
        for parent in (path, *path.parents):
            if parent == root:
                break
            if parent.is_symlink():
                raise UnsafeOwnerStorage("Linked native storage path")
        else:
            raise UnsafeOwnerStorage("Native path outside private storage")
        if not path.is_relative_to(root) or not path.resolve().is_relative_to(root):
            raise UnsafeOwnerStorage("Native path outside private storage")
        return path

    # Chema may list project directories from config.json; the cloud beta
    # currently supports only the native Projects/ subtree. Do not permit a
    # second internal project root until native scope gating supports it.
    expected = root / "Projects"
    for key in ("project_root",):
        if (value := data.get(key)):
            if contained(value) != expected:
                raise UnsafeOwnerStorage("Alternative project root unavailable")
    roots = data.get("project_roots", [])
    if not isinstance(roots, list) or len(roots) > 10:
        raise UnsafeOwnerStorage("Untrusted project root list")
    for value in roots:
        if contained(value) != expected:
            raise UnsafeOwnerStorage("Alternative project root unavailable")

    for key in ("inbox_path", "last_project_path"):
        if data.get(key):
            contained(data[key])
    sources = data.get("source_folders", [])
    if not isinstance(sources, list) or len(sources) > 64:
        raise UnsafeOwnerStorage("Untrusted native source folders")
    for folder in sources:
        contained(folder)
    # Never mutate these settings here: Chema's own application remains
    # responsible for their normal evolution once its scope is authorized.
