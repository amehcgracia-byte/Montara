"""Read-only preflight for a future *physical* client + HTTPS server trial.

Run independently on EACH client computer. Does not start Montara, upload
media, inspect project files, or send auth credentials. No automatic deploy.
Never address the Companion through a network interface other than loopback.

The HTTPS endpoint reachability is NOT an authenticated E2E or a benchmark.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import socket
import ssl
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, HTTPSHandler

SAFE_PATH = "/api/v1/wizard/status"
COMPANION_HEALTH = "http://127.0.0.1:47820/health"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def check_server_url(url: str, resolve=socket.getaddrinfo) -> str:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/") or parsed.port not in (None, 443)):
        raise ValueError("Server must be a bare HTTPS origin on port 443 with no credentials")
    # Reject internal endpoints, even when a public hostname resolves to them.
    if parsed.hostname.lower() in ("localhost", "localhost.localdomain"):
        raise ValueError("The shared server may not be loopback")
    try:
        literal = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        literal = None
    if literal is not None:
        raise ValueError("Use an approved public DNS hostname, not an IP literal")
    try:
        addresses = resolve(parsed.hostname, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError("The HTTPS server hostname cannot be resolved") from exc
    if not addresses:
        raise ValueError("No HTTPS server DNS addresses found")
    for result in addresses:
        ip = ipaddress.ip_address(result[4][0])
        if not ip.is_global:
            raise ValueError("Server DNS points to private, loopback or reserved IP")
    return f"https://{parsed.hostname.lower()}"


def _get(url: str, *, opener, timeout: float) -> tuple[int, bytes, float]:
    request = Request(url, headers={"Accept": "application/json",
                                    "User-Agent": "URANO-Preflight/1.0"})
    start = time.monotonic()
    try:
        with opener.open(request, timeout=timeout) as response:
            status = response.status
            payload = response.read(4096)
    except HTTPError as response:
        status = response.code
        payload = response.read(4096)
    return status, payload, round((time.monotonic() - start) * 1000, 3)


def run_preflight(origin: str, *, local_health: str = COMPANION_HEALTH,
                  resolve=socket.getaddrinfo, opener=None, timeout: float = 3) -> dict:
    if not 0.5 <= timeout <= 10:
        raise ValueError("Timeout out of safe range")
    server = check_server_url(origin, resolve=resolve)
    if local_health != COMPANION_HEALTH:
        # Explicitly forbid using this script to expose or contact another
        # user's Companion service, even via loopback on another port.
        raise ValueError("Companion must be the fixed default loopback health endpoint")
    # HTTPS certificates verified by platform trust store. No redirections.
    opener = opener or build_opener(NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))
    result = {
        "schema": "urano-remote-preflight-v1",
        "server_scheme": "https",
        "server_origin_redacted": True,
        "remote_server_checked": True,
        "companion_loopback_only": True,
        "authenticated_job_verified": False,
        "two_physical_clients_verified": False,
        "distributed_performance_verified": False,
        "media_uploaded": False,
        "report_contains_urls": False,
    }
    try:
        code, payload, ms = _get(server + SAFE_PATH, opener=opener, timeout=timeout)
        # A 401/403 indicates a reachable *protected* endpoint, not
        # authentication success. A redirect/404 indicates setup mismatch.
        result["server_http_status"] = code
        result["server_http_ms_observed"] = ms
        result["server_endpoint_reachable"] = code in (200, 401, 403)
        result["server_auth_required_or_forbidden"] = code in (401, 403)
    except (URLError, OSError, TimeoutError, ValueError):
        result["server_endpoint_reachable"] = False
        result["server_http_status"] = None
        result["server_http_ms_observed"] = None
        result["server_auth_required_or_forbidden"] = None
    try:
        code, payload, ms = _get(local_health, opener=opener, timeout=timeout)
        body = json.loads(payload) if code == 200 else {}
        result["companion_healthy"] = (
            code == 200 and isinstance(body, dict)
            and body.get("app") == "montara-companion" and body.get("ffmpeg") is True)
        result["companion_http_ms_observed"] = ms
    except (URLError, OSError, TimeoutError, ValueError, json.JSONDecodeError):
        result["companion_healthy"] = False
        result["companion_http_ms_observed"] = None
    result["ready_for_manual_auth_trial"] = (
        result["server_endpoint_reachable"] and result["companion_healthy"])
    return result


def main():
    parser = argparse.ArgumentParser(description="Read-only HTTPS server / loopback Companion preflight")
    parser.add_argument("--server-origin", required=True,
                        help="Operator-approved bare HTTPS URL, no credentials")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="Explicitly enable live GET health requests")
    args = parser.parse_args()
    if not args.execute:
        parser.error("Live checks are opt-in: --execute required")
    # No automatic discovery of remote servers, IPs or running Companions.
    path = args.output
    if path.is_symlink() or not path.parent.is_dir() or path.exists():
        parser.error("Output must be a new file in an existing directory, not a symlink")
    report = run_preflight(args.server_origin)
    with path.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2)
        output.write("\n")
    print(json.dumps({"ready_for_manual_auth_trial": report["ready_for_manual_auth_trial"],
                      "authenticated_job_verified": False,
                      "distributed_performance_verified": False}))


if __name__ == "__main__":
    main()
