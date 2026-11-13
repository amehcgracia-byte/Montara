"""Trusted local HTTPS boundary for the C8 real Google-owner portal.

A Flask app behind a reviewed TLS-terminating reverse proxy sees plain HTTP
on its local listener. Never trust arbitrary X-Forwarded-* from the Internet.
Instead, only when the backend connection is *actually loopback*, validate
a pinned Host and set WSGI's scheme to HTTPS. The server MUST bind 127.0.0.1,
and the reverse proxy MUST strip forwarded headers and enforce valid TLS.

Not suitable for Cloud Run or an arbitrary network-reachable upstream.
"""
from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from urano.c6_beta_preflight import validate_beta_origin

_FORBIDDEN_HEADERS = (
    "HTTP_X_FORWARDED_FOR", "HTTP_X_FORWARDED_HOST",
    "HTTP_X_FORWARDED_PROTO", "HTTP_X_FORWARDED_PORT",
    "HTTP_FORWARDED", "HTTP_X_REAL_IP",
)


class TrustedLocalHTTPSBoundary:
    """Only the local trusted reverse proxy can claim HTTPS for Google OAuth."""

    def __init__(self, wsgi_app, *, origin: str):
        self.wsgi_app = wsgi_app
        self.origin = validate_beta_origin(origin)
        self.hostname = urlsplit(self.origin).netloc

    def __call__(self, environ, start_response):
        remote = environ.get("REMOTE_ADDR", "")
        try:
            local = ipaddress.ip_address(remote).is_loopback
        except ValueError:
            local = False
        if (
            not local
            or environ.get("HTTP_HOST") != self.hostname
            or any(environ.get(key) is not None for key in _FORBIDDEN_HEADERS)
            or environ.get("REQUEST_METHOD") not in
               {"GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS"}
        ):
            body = b"Trusted HTTPS reverse proxy required"
            start_response("403 Forbidden", [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
                ("X-Content-Type-Options", "nosniff"),
            ])
            return [body]
        # Only the protected socket owner/proxy can reach this connection.
        trusted = dict(environ)
        trusted["wsgi.url_scheme"] = "https"
        trusted["HTTPS"] = "on"
        trusted["SERVER_PORT"] = "443"
        return self.wsgi_app(trusted, start_response)


def create_loopback_owner_application(*, config=None, provider=None):
    """WSGI factory, no servers launched and no Google mock fallback."""
    from urano.owner_beta_wsgi import create_private_owner_beta
    import os
    env = dict(os.environ) if config is None else dict(config)
    origin = validate_beta_origin(env.get("MONTARA_BETA_ORIGIN", ""))
    app = create_private_owner_beta(env, provider=provider)
    app.wsgi_app = TrustedLocalHTTPSBoundary(app.wsgi_app, origin=origin)
    return app
