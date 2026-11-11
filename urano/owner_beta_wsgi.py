"""Private C8 Google owner UI entrypoint.

This is the *real* C1 Google OIDC / verified-owner catalog and dashboard,
not the single-user classic editor on port 8114. It starts without any Engine
worker until infrastructure registers it through the trusted-only controller.
No mock login, fake users or public project creation.

A separate, authorized HTTPS reverse proxy must set a verified WSGI HTTPS
scheme. This module does not trust arbitrary X-Forwarded-* request headers.
"""
from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, request

from urano.c6_beta_preflight import validate_beta_settings
from urano.minimal_owner_api import create_owner_api
from urano.session_auth import SESSION_COOKIE, SessionStore


def create_private_owner_beta(
    env: dict[str, str] | None = None,
    *,
    provider=None,
    runtime_controller=None,
    stage_provenance=None,
    proxy_staging_root=None,
    receipt_verifier=None,
) -> Flask:
    """Build an opt-in Google-only owner portal, never a global Engine app."""
    config = dict(os.environ) if env is None else dict(env)
    preflight = validate_beta_settings(config)
    root = Path(config.get("MONTARA_OWNER_PRIVATE_DIR", ""))
    if (not root.is_absolute() or root.is_symlink() or not root.is_dir()
            or root == Path("/") or root.stat().st_mode & 0o077):
        raise ValueError("Operator must provision a private 0700 owner data root")
    if hasattr(os, "getuid") and root.stat().st_uid != os.getuid():
        raise ValueError("Private owner storage belongs to another process account")
    # I3 deliberately does not provision Engine or proxy ingestion. The actual
    # multi-owner worker/provenance integration is a later, separate reviewed PR.
    if (runtime_controller is not None or proxy_staging_root is not None
            or receipt_verifier is not None or stage_provenance is not None):
        raise ValueError("Private Engine and proxy inbox require a later trusted integration")

    private_engine = config.get("MONTARA_I27_OWNER_ENGINE_FLAG") == "private"
    editor_pilot = config.get("MONTARA_JM_EDITOR_PILOT") == "private"
    original_web_root = None
    proxy_limit = 256
    if editor_pilot:
        if not private_engine:
            raise ValueError("Original JM beta requires Owner private Engine")
        from urano.jm_bundle_manifest import (
            verify_jm_bundle_files, verify_pinned_chema_manifest
        )
        from urano.jm_private_proxy_overlay import private_proxy_limit_mib
        import json
        import re
        requested = config.get("MONTARA_JM_BUNDLE", "")
        if not re.fullmatch(r"/opt/montara/bundles/jm-[0-9a-f]{40}", requested):
            raise ValueError("Original JM beta requires pinned bundle")
        bundle = Path(requested)
        if (bundle.is_symlink() or not bundle.is_dir()
                or bundle.stat().st_uid != 0
                or bundle.stat().st_mode & 0o022):
            raise ValueError("Original JM beta bundle not immutable")
        proxy_limit = private_proxy_limit_mib(int(
            config.get("MONTARA_PRIVATE_PREVIEW_LIMIT_MIB", "256")))
        manifest_path = bundle / "montara-jm-bundle.json"
        if (manifest_path.is_symlink() or not manifest_path.is_file()
                or manifest_path.stat().st_size > 8192):
            raise ValueError("Original JM beta manifest missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        engine_pin = config.get("MONTARA_JM_ENGINE_PIN", "")
        if not re.fullmatch(r"[a-f0-9]{40}", engine_pin):
            raise ValueError("Original JM beta Engine revision required")
        verify_pinned_chema_manifest(
            manifest, expected_editor_commit=bundle.name[3:],
            expected_engine_commit=engine_pin,
            expected_private_preview_limit_mib=proxy_limit)
        verify_jm_bundle_files(bundle, manifest)
        original_web_root = bundle / "web"

    app = create_owner_api(
        root, settings=preflight.settings, provider=provider,
        enable_dashboard=True,
        enable_engine_preview=private_engine,
        original_jm_web_root=original_web_root,
        enable_original_jm_rpc=editor_pilot,
        enable_original_jm_browser_pilot=editor_pilot,
        private_preview_limit_mib=proxy_limit,
    )
    origin = preflight.origin

    @app.before_request
    def owner_portal_origin():
        # Never infer authority from X-Forwarded-* supplied by a browser.
        # The operator must terminate TLS in a trusted reverse proxy and
        # provide scheme/Host as actual WSGI properties, not raw headers.
        if request.host_url.rstrip("/") != origin:
            return jsonify(error="Trusted HTTPS beta origin required"), 403
        if request.headers.get("X-Forwarded-Host") or request.headers.get("X-Forwarded-Proto"):
            return jsonify(error="Untrusted forwarding metadata"), 403

    @app.get("/")
    def owner_home():
        session = SessionStore(root / "sessions.sqlite3").verify(
            request.cookies.get(SESSION_COOKIE))
        return redirect("/urano/v1/dashboard" if session else
                        "/urano/v1/google/start", code=303)

    @app.get("/urano/v1/login")
    @app.get("/urano/v1/register")
    def owner_auth_choice():
        """Small accessible auth entry. Email/password is deliberately NOT enabled."""
        session = SessionStore(root / "sessions.sqlite3").verify(
            request.cookies.get(SESSION_COOKIE))
        if session:
            return redirect("/urano/v1/dashboard", code=303)
        registering = request.path == "/urano/v1/register"
        heading = "Crear cuenta" if registering else "Iniciar sesión"
        alternate = ('<p>¿Ya tienes cuenta? <a href="/urano/v1/login">Inicia sesión</a></p>'
                     if registering else
                     '<p>¿Primera vez en Montara? <a href="/urano/v1/register">Crear cuenta</a></p>')
        body = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Montara · %s</title>
<style>:root{color-scheme:dark;font-family:system-ui,sans-serif;background:#0c0d11;color:#f8f6f2}
*{box-sizing:border-box}body{min-height:100vh;display:grid;place-items:center;margin:0;padding:24px}
main{width:min(100%%,430px);background:#17171d;border:1px solid #34343c;border-radius:20px;padding:34px}
h1{font-size:34px;letter-spacing:-.05em;margin:14px 0}p{color:#b3b3bd;line-height:1.5}
a{color:#ff9b88}a.primary{display:block;background:#ff593e;color:#121218;border-radius:9px;
text-decoration:none;font-weight:700;padding:15px;text-align:center;margin:24px 0}
.disabled{padding:16px;border:1px solid #43434d;border-radius:9px;color:#babac3;font-size:14px}
small{color:#aaaab4}footer{margin-top:28px}footer a{margin-right:18px}</style></head>
<body><main><strong>MONTARA</strong><h1>%s</h1>
<p>Accede a tu espacio privado y continúa con tus proyectos.</p>
<a class="primary" href="/urano/v1/google/start">Continuar con Google</a>
<div class="disabled" aria-label="Acceso con correo y contraseña no disponible">
<strong>Correo y contraseña</strong><p>En preparación: verificación de email y recuperación segura.</p>
<small>No crees una contraseña todavía.</small></div>
%s<footer><a href="/urano/v1/login">Iniciar sesión</a><a href="/urano/v1/register">Registrarse</a></footer>
</main></body></html>""" % (heading, heading, alternate)
        result = Response(body, mimetype="text/html; charset=utf-8")
        result.headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; "
            "form-action 'none'; frame-ancestors 'none'"
        )
        return result

    @app.get("/healthz")
    def owner_healthz():
        # This does not disclose owner IDs, Google settings or Engine state.
        return jsonify(service="montara-owner-beta", authenticated=False,
                       engine_provisioned=False,
                       public_multiuser_ready=False)

    @app.after_request
    def no_cache_owner_beta(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    return app


def main() -> None:
    """For deployment use a reviewed TLS proxy and Gunicorn factory only."""
    raise SystemExit("Use a reviewed TLS reverse proxy and WSGI factory; no embedded dev server")


# Importing this module never reads secrets or starts a public listener.
