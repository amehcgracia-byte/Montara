"""Opt-in browser HTTP transfer counter for the URANO hybrid architecture.

Read only Playwright request/response size metadata. Never inspect or store
request bodies, media contents, URLs, query strings, token values, file paths,
cookies, or headers. Loopback in CI is NOT WAN or a remote server.
"""
from __future__ import annotations

from collections import defaultdict
from urllib.parse import urlsplit


def _kind(path: str) -> str:
    if path.startswith("/montara/uploads") or path.startswith("/api/v1/inputs"):
        return "proxy_or_input_transfer"
    if path.startswith("/video-renders/") and path.endswith("/file"):
        return "local_final_video_download"
    if path.startswith("/video-renders"):
        return "local_render_control"
    if path.startswith("/proxies"):
        return "local_proxy_generation"
    if path.startswith("/api/v1/"):
        return "stage_api"
    if path.startswith("/projects") or path.startswith("/locate"):
        return "local_companion_lookup"
    return "other"


class BrowserTransferMeter:
    def __init__(self, *, server_origin: str, companion_origin: str):
        a, b = urlsplit(server_origin), urlsplit(companion_origin)
        if (a.scheme not in ("http", "https") or b.scheme not in ("http", "https")
                or not a.netloc or not b.netloc or (a.scheme, a.netloc) == (b.scheme, b.netloc)
                or a.username or a.password or b.username or b.password):
            raise ValueError("Two distinct explicit HTTP origins are required")
        self.origins = {
            (a.scheme, a.netloc): "server",
            (b.scheme, b.netloc): "local_companion",
        }
        self.counts = defaultdict(lambda: {
            "requests": 0, "request_body_bytes": 0, "response_body_bytes": 0,
            "request_header_bytes": 0, "response_header_bytes": 0,
        })
        self.unmeasured = 0
        self.failed = 0
        self.max_server_request_body_bytes = 0
        self.server_upload_sizes = []

    def attach(self, page):
        page.on("requestfinished", self.finished)
        page.on("requestfailed", self.failure)
        return self

    def finished(self, request):
        # Only count browser-observed exchanges, not localhost service-to-service
        # traffic or FFmpeg file I/O. Playwright sizes() may reject service-worker
        # requests; mark them unmeasured, never silently pretend zero bytes.
        try:
            uri = urlsplit(request.url)
            role = self.origins.get((uri.scheme, uri.netloc))
            if role is None:
                return
            sizes = request.sizes()
            keys = ("requestBodySize", "responseBodySize", "requestHeadersSize",
                    "responseHeadersSize")
            if any(type(sizes.get(k)) is not int or sizes[k] < 0 for k in keys):
                self.unmeasured += 1
                return
            method = request.method if request.method in ("GET", "POST", "PUT", "PATCH", "DELETE") else "OTHER"
            label = (role, method, _kind(uri.path))
            record = self.counts[label]
            record["requests"] += 1
            for name, key in (
                ("request_body_bytes", "requestBodySize"),
                ("response_body_bytes", "responseBodySize"),
                ("request_header_bytes", "requestHeadersSize"),
                ("response_header_bytes", "responseHeadersSize"),
            ):
                record[name] += sizes[key]
            if role == "server":
                self.max_server_request_body_bytes = max(
                    self.max_server_request_body_bytes, sizes["requestBodySize"])
                if method in ("POST", "PUT", "PATCH") and _kind(uri.path) == "proxy_or_input_transfer":
                    self.server_upload_sizes.append(sizes["requestBodySize"])
        except Exception:
            self.unmeasured += 1

    def failure(self, request):
        try:
            u = urlsplit(request.url)
            if (u.scheme, u.netloc) in self.origins:
                self.failed += 1
        except Exception:
            self.failed += 1

    def report(self, *, originals_sizes: list[int] | None = None) -> dict:
        groups = []
        for (role, method, family), counts in sorted(self.counts.items()):
            groups.append({"destination": role, "method": method,
                           "endpoint_family": family, **counts})
        server_upload_bytes = sum(g["request_body_bytes"] for g in groups
                                  if g["destination"] == "server"
                                  and g["endpoint_family"] == "proxy_or_input_transfer")
        local_download_bytes = sum(g["response_body_bytes"] for g in groups
                                   if g["destination"] == "local_companion"
                                   and g["endpoint_family"] == "local_final_video_download")
        total_original_bytes = sum(originals_sizes) if originals_sizes else None
        return {
            "schema": "urano-browser-http-transfer-v1",
            "capture": "playwright-request-sizes",
            "network_topology": "loopback-shared-runner-not-WAN",
            "remote_server_bytes_measured": False,
            "server_upload_browser_body_bytes_observed": server_upload_bytes,
            "companion_final_video_download_body_bytes_observed": local_download_bytes,
            "originals_total_bytes_local": total_original_bytes,
            # Comparing body sizes does not prove content identity. We must
            # inspect code and/or enforce a server-side upload limit to verify
            # originals remain local. This is a diagnostic only.
            "original_upload_proven_absent": False,
            "unmeasured_requests": self.unmeasured,
            "failed_requests": self.failed,
            "request_groups": groups,
            "limitations": [
                "Browser requests only; does not cover server background fetches.",
                "Loopback transfer sizes are not physical network or WAN bytes.",
                "Interception/mocking may affect network-level byte counts.",
                "No request bodies, URLs, tokens, or user media were captured.",
            ],
        }
