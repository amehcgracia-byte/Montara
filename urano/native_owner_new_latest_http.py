"""Exact original Chema New/Latest URLs admitted by an Owner HTTP gateway.

This is intentionally a SMALL read-only contract, not a public relay.
Before forwarding, the surrounding gateway must authenticate Google Owner,
verify CSRF for mutations, resolve that Owner's reserved workspace and
generation, then use the broker-authorized private Unix socket.

The private worker separately checks all project and media paths. No HTTP
caller can select a worker/owner/unit by passing a path or query parameter.
"""
from __future__ import annotations

from urllib.parse import parse_qs

# Source URLs and methods as used by Chema's unchanged web/montara.js and
# web/full-session.js. The gateway must not implement project selection UI.
_NATIVE = frozenset({
    ("GET", "/montara/recovery/latest"),
    ("GET", "/api/v1/wizard/projects"),
    ("GET", "/api/v1/project"),
    ("GET", "/api/v1/wizard/status"),
    ("POST", "/api/v1/wizard/projects/new"),
    ("POST", "/api/v1/wizard/projects/open"),
    ("POST", "/api/v1/wizard/projects/delete"),
    ("POST", "/api/v1/wizard/draft"),
    ("POST", "/api/v1/wizard/prepare"),
    ("POST", "/api/v1/wizard/start"),
    ("POST", "/api/v1/wizard/cancel"),
})


def native_new_latest_target(method: str, path: str,
                             query: str = "") -> str | None:
    """Return a reviewed private JM URL, or None (never a generic fallback)."""
    if (not isinstance(method, str) or not isinstance(path, str)
            or not isinstance(query, str)):
        return None
    if (method, path) not in _NATIVE or len(query) > 4096:
        return None
    if query:
        if (method, path) != ("GET", "/api/v1/wizard/status"):
            return None
        try:
            params = parse_qs(query, strict_parsing=True,
                              keep_blank_values=True, max_num_fields=1)
        except (ValueError, TypeError):
            return None
        if (set(params) != {"project_id"} or
                len(params["project_id"]) != 1 or
                len(params["project_id"][0]) > 4096):
            return None
    # Avoid constructing paths or query segments from arbitrary strings:
    # the prefix and key have been verified above.
    return path + ("?" + query if query else "")
