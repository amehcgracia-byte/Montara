"""Boundary for original Chema JM project paths inside one private Owner worker.

The broker, not the browser, supplies the already verified data_root. Chema
may create and restore multiple native projects *within* this one private
worker directory. No Owner catalog or project picker is involved.

This does not authorize a user or start a worker: authentication, broker
ownership and admission are required before calling this helper.
"""
from __future__ import annotations

import json
from pathlib import Path


class UnsafeNativeProject(ValueError):
    """A Chema project is not a safe member of this worker's data root."""


def verified_native_project(data_root: Path, supplied: str) -> Path:
    """Validate an EXISTING Chema project path; never accept arbitrary paths.

    A valid path names a direct child of data_root/Projects, containing a
    regular non-symlink project.json with a JSON object. The caller must
    obtain data_root from the authenticated worker, not an HTTP parameter.
    """
    if (not isinstance(supplied, str) or not supplied
            or len(supplied) > 4096 or "\\x00" in supplied):
        raise UnsafeNativeProject("Invalid native project path")

    try:
        root = Path(data_root).resolve(strict=True)
        projects = root / "Projects"
        if not projects.is_dir() or projects.is_symlink():
            raise UnsafeNativeProject("Private project storage unavailable")
        candidate = Path(supplied)
        if (not candidate.is_absolute() or ".." in candidate.parts
                or "." in candidate.parts or candidate.parent != projects
                or candidate.is_symlink() or not candidate.is_dir()):
            raise UnsafeNativeProject("Project outside its private workspace")
        resolved = candidate.resolve(strict=True)
        if resolved.parent != projects.resolve(strict=True):
            raise UnsafeNativeProject("Project escapes its private workspace")
        metadata = candidate / "project.json"
        if metadata.is_symlink() or not metadata.is_file():
            raise UnsafeNativeProject("Project metadata missing or linked")
        size = metadata.stat().st_size
        if not 1 <= size <= 8 * 1024 * 1024:
            raise UnsafeNativeProject("Invalid project metadata size")
        with metadata.open("rb") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise UnsafeNativeProject("Invalid project metadata format")
        return resolved
    except (OSError, RuntimeError, TypeError, json.JSONDecodeError) as exc:
        raise UnsafeNativeProject("Invalid private project") from exc
