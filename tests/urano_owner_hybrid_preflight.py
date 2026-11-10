"""Opt-in, read-only preflight for current C8 Google owner portal + local Companion.

No OAuth login, tokens, uploads, renders, or process starts. This is NOT a benchmark.
"""
from __future__ import annotations

import argparse
import json
import socket
import ssl
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import build_opener, HTTPSHandler

from urano_remote_hybrid_preflight import (
    COMPANION_HEALTH, NoRedirect, _get, check_server_url,
)


def preflight_owner_portal(origin: str, *, local_health: str = COMPANION_HEALTH,
                           resolve=socket.getaddrinfo, opener=None,
                           timeout: float = 3) -> dict:
    """Probe a fixed HTTPS C8 health path and anonymous dashboard gate.

    DNS validation and the fixed Companion loopback endpoint are inherited from
    the reviewed U18 preflight. All HTTP redirects are refused by default.
    A healthy anonymous portal NEVER proves authentic Google or Engine readiness.
    """
    if not .5 <= timeout <= 10:
        raise ValueError("Timeout must be between 0.5 and 10 seconds")
    server = check_server_url(origin, resolve=resolve)
    if local_health != COMPANION_HEALTH:
        raise ValueError("Companion probe must use its fixed localhost endpoint")
    opener = opener or build_opener(NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))
    report = {
        "schema": "montara-owner-hybrid-preflight-v1",
        "topology": "remote-https-and-local-companion",
        "server_url_recorded": False,
        "server_http_status": None,
        "server_http_ms_observed": None,
        "server_identity_valid": False,
        "anonymous_dashboard_status": None,
        "anonymous_dashboard_denied": False,
        "companion_healthy": False,
        "companion_http_ms_observed": None,
        "ready_for_manual_auth_trial": False,
        "google_login_verified": False,
        "owner_engine_verified": False,
        "stage_to_local_mp4_verified": False,
        "one_user_benchmark_complete": False,
        "client_cpu_seconds": None,
        "server_cpu_seconds": None,
        "wan_proxy_upload_bytes": None,
        "local_mp4_bytes": None,
    }
    try:
        status, payload, ms = _get(server + "/healthz", opener=opener, timeout=timeout)
        report["server_http_status"] = status
        report["server_http_ms_observed"] = ms
        body = json.loads(payload) if status == 200 else {}
        report["server_identity_valid"] = bool(status == 200 and isinstance(body, dict)
            and body.get("service") == "montara-owner-beta")
    except (HTTPError, URLError, OSError, TimeoutError, ValueError, json.JSONDecodeError):
        pass
    if report["server_identity_valid"]:
        try:
            status, _, _ = _get(server + "/urano/v1/dashboard", opener=opener, timeout=timeout)
            report["anonymous_dashboard_status"] = status
            report["anonymous_dashboard_denied"] = status in (401, 403)
        except (HTTPError, URLError, OSError, TimeoutError, ValueError):
            pass
    try:
        status, payload, ms = _get(local_health, opener=opener, timeout=timeout)
        body = json.loads(payload) if status == 200 else {}
        report["companion_healthy"] = bool(status == 200 and isinstance(body, dict)
            and body.get("app") == "montara-companion" and body.get("ffmpeg") is True)
        report["companion_http_ms_observed"] = ms
    except (HTTPError, URLError, OSError, TimeoutError, ValueError, json.JSONDecodeError):
        pass
    report["ready_for_manual_auth_trial"] = bool(report["server_identity_valid"]
        and report["anonymous_dashboard_denied"] and report["companion_healthy"])
    return report


def main():
    parser = argparse.ArgumentParser(description="Opt-in C8 owner portal + local Companion health preflight")
    parser.add_argument("--server-origin", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("Remote and local health requests require --execute")
    output = args.output
    if output.is_symlink() or output.exists() or not output.parent.is_dir():
        parser.error("Output must be a new file in an existing directory")
    result = preflight_owner_portal(args.server_origin)
    with output.open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(json.dumps({"ready_for_manual_auth_trial": result["ready_for_manual_auth_trial"],
                      "one_user_benchmark_complete": False}))


if __name__ == "__main__":
    main()
