"""Pure product-mode helper shared by web and privileged Owner broker.

No Flask, sessions, sockets or cloud dependencies are imported here.
"""
from __future__ import annotations

MODES = frozenset({"stage", "push", "show"})


def project_mode(project) -> str | None:
    """Read the existing workspace mode without modifying legacy projects."""
    workspace = project.recipe.get("montara_beta_workspace")
    if not isinstance(workspace, dict):
        return None
    mode = workspace.get("mode")
    return mode if isinstance(mode, str) and mode in MODES else None
