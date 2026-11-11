"""Portable Owner state identity for trusted Linux worker storage.

Google, Cloudflare, VM provider and vCPU count never appear in the policy.
The Linux systemd executor maps the stable logical Owner key to a dedicated
StateDirectory; other executors can implement the same identity differently.

This is a namespace, not an encryption mechanism. Only the privileged broker
is allowed to ask systemd to mount or change ownership of the directory.
"""
from __future__ import annotations

import hashlib
import re

from urano.project_catalog import ProjectCatalog


def owner_state_directory(owner_id: str) -> str:
    """Stable systemd StateDirectory identifier for one verified Owner."""
    owner=ProjectCatalog._principal(owner_id)
    if not isinstance(owner,str) or len(owner)>256:
        raise ValueError("Invalid Owner state namespace")
    digest=hashlib.sha256(owner.encode("utf-8")).hexdigest()[:40]
    return "montara-owner-"+digest


def owner_state_path(owner_id: str) -> str:
    """StateDirectory Linux private path; no runtime/lease generation inside."""
    return "/var/lib/montara-owner-"+hashlib.sha256(
        ProjectCatalog._principal(owner_id).encode("utf-8")
    ).hexdigest()[:40]
