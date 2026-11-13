"""Minimal authenticated-worker binding for Chema's ORIGINAL Flask application.

The caller (root-broker-supervised worker) must already have:
  - a verified Owner principal, reserved workspace UUID and exact generation;
  - a separate DynamicUser/cgroup and private persistent StateDirectory;
  - an AF_UNIX transport allowing only the corresponding trusted gateway.

This function does NOT establish any of those external privileges. It avoids
opening a synthetic project and instead lets Chema's original app handle its
own New/Latest transitions inside the Owner's private data_root.

Do not route Internet requests directly to this Flask app; only use behind
the existing authenticated Owner CSRF/HTTP->broker->Unix boundary.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Callable

from urano.native_owner_project_scope import verified_native_project
from urano.native_owner_stage_snapshot import native_owner_stage_snapshot
from urano.native_owner_storage_guard import verify_owner_storage_config
from urano.native_owner_workspace_gate import NativeOwnerWorkspaceGate


class NativeWorkerBindingError(RuntimeError):
    """The worker cannot safely serve this native Chema workspace."""


def bind_native_owner_application(*, app_factory: Callable,
                                  data_root: Path, workspace_id: str):
    """Return (app, read_snapshot) for a privately mounted Chema Flask app.

    app_factory is the ORIGINAL Chema create_montara_app(data_root,
    samples=False), never a second app implementation.
    """
    if not callable(app_factory):
        raise NativeWorkerBindingError("Original Chema app factory required")
    try:
        parsed = uuid.UUID(workspace_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise NativeWorkerBindingError("Trusted workspace UUID required") from exc
    if str(parsed) != workspace_id:
        raise NativeWorkerBindingError("Noncanonical Owner workspace UUID")
    root = Path(data_root)
    if root.is_symlink() or not root.is_dir():
        raise NativeWorkerBindingError("Private data root not available")
    if root.stat().st_mode & 0o077:
        raise NativeWorkerBindingError("Private data root permissions too broad")
    root = root.resolve(strict=True)
    verify_owner_storage_config(root)

    # The sole application entrypoint is Chema's existing app. In particular
    # there is no Owner-generated "Projects/<uuid>/project.json" bootstrap
    # and no POST /wizard/projects/open that overrides Chema's last edit.
    app = app_factory(root, samples=False)
    state = app.config.get("ZUCKER_STATE")
    if state is None:
        raise NativeWorkerBindingError("Original Chema project state unavailable")
    loaded = getattr(getattr(state, "project", None), "folder", None)
    if loaded is not None:
        try:
            verified_native_project(root, str(loaded))
        except ValueError as exc:
            raise NativeWorkerBindingError(
                "Initial project is outside Owner workspace") from exc

    app.wsgi_app = NativeOwnerWorkspaceGate(app.wsgi_app, data_root=root)

    def read_snapshot():
        return native_owner_stage_snapshot(
            app, data_root=root, workspace_id=workspace_id)

    return app, read_snapshot
