"""I31: fail-closed route admission for a future PRIVATE JM Engine transport.

Pure contract only. No HTTP endpoint, Unix socket, worker, or user-selected address.
The caller must independently verify the Google owner/session/project in the root
broker and bind the project to its active private worker generation BEFORE dispatch.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from urllib.parse import urlsplit

# Deliberately tiny first Stage handshake. Add individual operations only after
# inspecting the JM routes and proving isolation and request-body validation.
_STAGE_ROUTES = {
    ("GET", "/api/v1/wizard/status"),
    ("GET", "/api/v1/project"),
    ("GET", "/api/v1/artifacts/sync"),
}
_ALLOWED = {"stage": _STAGE_ROUTES, "push": frozenset(), "show": frozenset()}
_HEX_SHA = re.compile(r"[a-f0-9]{40}\Z")


class PrivateEngineRouteDenied(PermissionError):
    """Invalid binding, capability, project or Engine operation."""


@dataclass(frozen=True)
class VerifiedEngineBinding:
    """Trusted output of the broker ledger and isolation check; never from HTTP."""

    owner_id: str
    project_id: str
    mode: str
    generation: int
    engine_sha: str
    ready: bool


@dataclass(frozen=True)
class EngineRequestPlan:
    """Canonical, bodyless request for a private Engine client."""

    method: str
    path: str
    owner_id: str
    project_id: str
    generation: int
    engine_sha: str


def plan_private_engine_request(
    binding: VerifiedEngineBinding, *, owner_id: str, project_id: str,
    generation: int, method: str, path: str
) -> EngineRequestPlan:
    if not isinstance(binding, VerifiedEngineBinding) or type(binding.ready) is not bool or not binding.ready:
        raise PrivateEngineRouteDenied("Engine binding unavailable")
    try:
        canonical = str(uuid.UUID(project_id))
        worker_canonical = str(uuid.UUID(binding.project_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise PrivateEngineRouteDenied("Invalid project") from exc
    if (not isinstance(owner_id, str) or not owner_id
            or not isinstance(binding.owner_id, str) or not binding.owner_id
            or canonical != project_id or worker_canonical != binding.project_id
            or binding.owner_id != owner_id or binding.project_id != project_id):
        raise PrivateEngineRouteDenied("Owner or project mismatch")
    if (type(generation) is not int or generation < 1
            or type(binding.generation) is not int
            or binding.generation != generation):
        raise PrivateEngineRouteDenied("Engine generation mismatch")
    if not isinstance(binding.engine_sha, str) or not _HEX_SHA.fullmatch(binding.engine_sha):
        raise PrivateEngineRouteDenied("Unverified Engine bundle")
    if binding.mode not in _ALLOWED:
        raise PrivateEngineRouteDenied("Unsupported project mode")
    if not isinstance(method, str) or not isinstance(path, str):
        raise PrivateEngineRouteDenied("Invalid route")
    # Exact string lookup rejects URLs, query strings, percent-encoding, dot
    # segments, encoded slashes, variant cases and user supplied paths.
    if (method, path) not in _ALLOWED[binding.mode]:
        raise PrivateEngineRouteDenied("Engine operation not permitted")
    return EngineRequestPlan(method, path, owner_id, project_id,
                             generation, binding.engine_sha)
