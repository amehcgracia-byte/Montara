"""I38: link the ORIGINAL JM Engine project to the existing private Owner UUID.

No new database, editor, HTTP endpoint or Engine runtime. This reuses U13A
EngineProjectRegistry, I27's per-owner folder name, and the live JM Engine's
authoritative active project, never a browser-supplied path or project ID.
"""
from __future__ import annotations

from pathlib import Path

from urano.editor_project_bridge import project_mode
from urano.engine_bindings import EngineProjectRegistry, EngineBinding
from urano.project_catalog import ProjectCatalog, ProjectNotFound


class EditorHandoffDenied(PermissionError):
    pass


def bind_open_jm_editor_project(
    *, owner_id: str, project_id: str, mode: str,
    catalog: ProjectCatalog, registry: EngineProjectRegistry,
    engine_client,
) -> EngineBinding:
    """Trusted worker-only handoff AFTER successful Engine open.

    The Engine's folder is its private UUID-named workspace, as established by
    the I27 broker worker. Do not bind an arbitrary JM draft, a Push pack ID,
    or a value from request parameters.
    """
    if mode not in ("stage", "push", "show"):
        raise EditorHandoffDenied("Unsupported editor mode")
    try:
        project = catalog.get(owner_id, project_id)
    except (ProjectNotFound, ValueError) as exc:
        raise EditorHandoffDenied("Owner project unavailable") from exc
    if project_mode(project) != mode:
        raise EditorHandoffDenied("Project mode mismatch")
    try:
        state = engine_client.application.config["ZUCKER_STATE"]
        folder = getattr(getattr(state, "project", None), "folder", None)
        if not isinstance(folder, (Path, str)):
            raise EditorHandoffDenied("JM Engine has not opened a project")
        folder = Path(folder)
        # No legacy last_project_path or user-supplied path may be used.
        expected = registry.projects_dir / project_id
        if (folder.is_symlink() or expected.is_symlink()
                or not folder.is_dir() or folder.name != project_id
                or folder.resolve() != expected.resolve()):
            raise EditorHandoffDenied("Wrong JM Engine project")
        response = engine_client.get("/api/v1/project")
        if response.status_code != 200 or not isinstance(response.get_json(), dict):
            raise EditorHandoffDenied("JM Engine project not verified")
    except (OSError, KeyError, TypeError, AttributeError) as exc:
        raise EditorHandoffDenied("JM Engine state unavailable") from exc
    # Existing U13A registry uniquely binds folder to one Owner UUID.
    # A valid reopening must be idempotent; do not fail merely because a
    # previous authenticated editing session already registered this folder.
    try:
        already = registry.resolve_internal(owner_id, project_id)
    except ProjectNotFound:
        already = None
    if already is not None:
        if already.resolve() != folder.resolve():
            raise EditorHandoffDenied("JM project binding changed")
        return EngineBinding(project_id, project_id)
    try:
        return registry.bind_trusted(owner_id, project_id, project_id)
    except ValueError as exc:
        # A second trusted transaction may have bound the same project in the
        # meantime. Accept only the identical, physically checked mapping.
        try:
            already = registry.resolve_internal(owner_id, project_id)
        except (ValueError, ProjectNotFound):
            raise EditorHandoffDenied("JM project binding unavailable") from exc
        if already.resolve() != folder.resolve():
            raise EditorHandoffDenied("JM project binding changed") from exc
        return EngineBinding(project_id, project_id)
