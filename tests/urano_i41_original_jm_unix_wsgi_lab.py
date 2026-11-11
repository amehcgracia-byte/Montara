"""I41 lab: COMPLETE original JM editor HTML/JS/API over private Unix WSGI.

A source checkout of Chema's reviewed branch is combined in a TEMPORARY
directory with the pinned real Engine and the FER adapter. Does not launch
any TCP service or use browser-owned media. Not the production Owner proxy.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import threading
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--execute", action="store_true")
    a = p.parse_args()
    if not a.execute:
        p.error("Requires --execute on an isolated lab checkout")
    bundle = a.bundle.resolve(strict=True)
    if (bundle.parent != Path("/opt/montara/bundles")
            or not bundle.name.startswith("engine-")
            or len(bundle.name) != 47
            or any(c not in "0123456789abcdef" for c in bundle.name[7:])):
        p.error("Not a reviewed immutable Engine bundle")
    root = Path(__file__).resolve().parents[1]
    if not (root / "web/index.html").is_file() or not (root / "app.py").is_file():
        p.error("Missing original JM application")
    sys.path[:0] = [str(root), str(bundle / "site"),
                    str(bundle / "app"), str(bundle / "engine")]
    from app import create_montara_app
    from core.project import new_project_document
    from urano.private_jm_wsgi_socket import (
        VerifiedJMUnixConnection, create_private_jm_wsgi_server,
        pinned_jm_static_assets,
    )

    with tempfile.TemporaryDirectory(prefix="montara-i41-jm-http-") as tmp:
        project_root = Path(tmp) / "jm-private"
        project_root.mkdir(mode=0o700)
        project = "7b8f5fd6-02b4-4cd0-8d16-c2d6d606a505"
        folder = project_root / "Projects" / project
        folder.mkdir(parents=True)
        (folder / "project.json").write_text(
            json.dumps(new_project_document(project)), encoding="utf-8")
        app = create_montara_app(project_root, samples=False)
        opened = app.test_client().post(
            "/api/v1/wizard/projects/open", json={"path": str(folder)})
        if opened.status_code != 200:
            raise RuntimeError("Real JM Engine refused test project")
        server, path = create_private_jm_wsgi_server(app, project_root)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        outcomes = {}
        manifest = pinned_jm_static_assets(root / "web")
        try:
            with VerifiedJMUnixConnection(
                path, expected_pid=os.getpid(), expected_uid=os.getuid(),
                approved_assets=manifest,
            ) as channel:
                for endpoint in (
                    "/", "/montara.js", "/companion.js", "/montara.css",
                    "/api/v1/wizard/status", "/api/v1/project",
                    "/montara/version",
                ):
                    code, content_type, data = channel.get_safe_read(endpoint)
                    outcomes[endpoint] = {
                        "status": code, "content_type": content_type,
                        "bytes": len(data),
                    }
                    if code != 200 or not data:
                        raise RuntimeError("Real original JM route unavailable: " + endpoint)
                    if endpoint == "/" and not all(
                            x in data for x in (
                                b'data-platform="youtube"',
                                b'data-platform="reel"',
                                b'data-platform="show"',
                            )):
                        raise RuntimeError("Original Stage/Push/Show UI not present")
                try:
                    channel.get_safe_read("/api/v1/wizard/projects/new")
                except PermissionError:
                    pass
                else:
                    raise RuntimeError("Unreviewed editor mutation permitted")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            path.unlink(missing_ok=True)
        if thread.is_alive():
            raise RuntimeError("Unix WSGI server not fully stopped")
        print(json.dumps({
            "real_original_jm_app": True,
            "real_pinned_engine": True,
            "original_html_js_css": True,
            "original_editor_api_project_opened": True,
            "private_unix_wsgi_only": True,
            "reviewed_static_asset_count": len(manifest),
            "routes": outcomes,
            "public_editor_http_enabled": False,
            "owner_google_session_in_this_lab": False,
            "real_windows_companion_e2e": False,
        }, sort_keys=True))


if __name__ == "__main__":
    main()
