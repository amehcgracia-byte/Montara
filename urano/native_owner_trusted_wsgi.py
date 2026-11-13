"""Opt-in native Chema Owner WSGI factory for a future ISOLATED beta.

No server is started and no existing systemd service/Cloudflare binding is
changed by importing this file. Deployment must select this factory with an
operator-controlled launch, bind only 127.0.0.1, and keep Google secrets in
a private file. This factory DOES NOT turn the old pilot into native mode.

Copies only the proven integrity preflight and loopback HTTPS boundary from
the existing beta; never reimplements Google OAuth or serves a mock login.
"""
from __future__ import annotations

import json
import os
import re
from functools import partial
from pathlib import Path

from urano.c6_beta_preflight import validate_beta_settings
from urano.jm_bundle_manifest import (
    verify_jm_bundle_files, verify_pinned_chema_manifest,
)
from urano.jm_private_proxy_overlay import private_proxy_limit_mib
from urano.native_owner_app import create_native_owner_api
from urano.owner_broker_preview import broker_request
from urano.owner_private_http_client import authenticated_private_jm_connection
from urano.trusted_local_https import TrustedLocalHTTPSBoundary

_H4_BROKER_SOCKET="/run/montara-h4-owner-admission/control.sock"

_PINNED_BUNDLE = re.compile(r"/opt/montara/bundles/jm-[a-f0-9]{40}\Z")
_SHA = re.compile(r"[a-f0-9]{40}\Z")


def create_loopback_native_owner_application(*, config=None, provider=None):
    """Mount Chema's original UI behind exact Google+Owner identity and HTTPS.

    Only an operator-selected *new* Gunicorn instance may call this factory.
    Native Owner must still have an authorized root broker using the reviewed
    native script. This function does not start or configure that broker.
    """
    env = dict(os.environ) if config is None else dict(config)
    if env.get("MONTARA_NATIVE_OWNER_PORTAL") != "reviewed-opt-in":
        raise ValueError("Native Owner beta requires explicit operator opt-in")
    beta = validate_beta_settings(env)
    root = Path(env.get("MONTARA_OWNER_PRIVATE_DIR",""))
    if (not root.is_absolute() or root == Path("/") or root.is_symlink()
            or not root.is_dir() or root.stat().st_mode & 0o077):
        raise ValueError("Operator must provision a private 0700 Owner data root")
    if hasattr(os,"getuid") and root.stat().st_uid != os.getuid():
        raise ValueError("Owner database directory must belong to web account")

    jm_location = env.get("MONTARA_JM_BUNDLE","")
    if not isinstance(jm_location,str) or not _PINNED_BUNDLE.fullmatch(jm_location):
        raise ValueError("Exact reviewed Chema bundle required")
    jm = Path(jm_location)
    if (jm.is_symlink() or not jm.is_dir() or jm.stat().st_uid != 0
            or jm.stat().st_mode & 0o022):
        raise ValueError("Root-pinned Chema bundle unavailable")
    engine_pin = env.get("MONTARA_JM_ENGINE_PIN","")
    if not isinstance(engine_pin,str) or not _SHA.fullmatch(engine_pin):
        raise ValueError("Exact reviewed Engine pin required")
    try:
        limit = private_proxy_limit_mib(int(
            env.get("MONTARA_PRIVATE_PREVIEW_LIMIT_MIB","256")))
    except (ValueError,TypeError) as exc:
        raise ValueError("Invalid private proxy profile") from exc
    path = jm / "montara-jm-bundle.json"
    if (path.is_symlink() or not path.is_file() or
            not 1 <= path.stat().st_size <= 8192):
        raise ValueError("Reviewed Chema bundle manifest unavailable")
    try:
        manifest=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError,UnicodeError) as exc:
        raise ValueError("Invalid Chema bundle manifest") from exc
    verify_pinned_chema_manifest(
        manifest,expected_editor_commit=jm.name[3:],
        expected_engine_commit=engine_pin,
        expected_private_preview_limit_mib=limit,
    )
    verify_jm_bundle_files(jm,manifest)
    app=create_native_owner_api(
        root,settings=beta.settings,chema_web_root=jm/"web",
        provider=provider,private_preview_limit_mib=limit,
        ensure_worker=partial(
            broker_request,control_socket=_H4_BROKER_SOCKET),
        connect_worker=partial(
            authenticated_private_jm_connection,
            control_socket=Path(_H4_BROKER_SOCKET)),
    )
    app.wsgi_app=TrustedLocalHTTPSBoundary(
        app.wsgi_app,origin=beta.origin)
    return app
