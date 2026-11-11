"""Owner-only original Chema editor assets, without starting any Engine.

The original HTML and scripts can be served from a reviewed read-only JM web
bundle while the user's Engine is OFF. A separate authorized gateway will
later admit the first valid proxy upload and start the private worker.

Only original static assets; NO media, JM API or public upload is exposed here.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, Response, abort, make_response, request, send_from_directory

from urano.project_catalog import ProjectCatalog, ProjectNotFound
from urano.session_auth import SESSION_COOKIE, SessionStore
from urano.private_jm_wsgi_socket import pinned_jm_static_assets


def original_editor_assets_blueprint(
    catalog: ProjectCatalog, sessions: SessionStore, *,
    https_origin: str, web_root: Path,
    enable_browser_pilot: bool = False,
) -> Blueprint:
    root = Path(web_root).resolve(strict=True)
    if not root.is_dir() or not (root / "index.html").is_file():
        raise ValueError("Original JM web bundle is unavailable")
    manifest = pinned_jm_static_assets(root)
    if "/montara.js" not in manifest or "/companion.js" not in manifest:
        raise ValueError("Not a complete original Chema editor bundle")
    bp = Blueprint("urano_original_jm_owner_assets", __name__,
                   url_prefix="/urano/v1/editor/projects")

    def authorize(project_id: str):
        if request.host_url.rstrip("/") != https_origin:
            abort(403)
        session = sessions.verify(request.cookies.get(SESSION_COOKIE))
        if session is None:
            abort(401)
        try:
            return catalog.get(session.owner_id, project_id)
        except (ValueError, ProjectNotFound):
            abort(404)

    def deliver(relative: str):
        response = make_response(send_from_directory(root, relative))
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @bp.get("/<project_id>/")
    def index(project_id: str):
        authorize(project_id)
        if not enable_browser_pilot:
            return deliver("index.html")
        # Never edit Chema's original source or insert a new editor. Inject a
        # separately removable, reviewed URL adapter BEFORE its existing JS.
        original=(root / "index.html").read_text(encoding="utf-8")
        first_script='<script src="mix-levels.js"></script>'
        if original.count(first_script)!=1:
            abort(503)
        bootstrap=(
            '<script src="owner-bridge.js" data-owner-project="'
            +project_id+'"></script>'
            '<script src="/urano/v1/entry/picker.js"></script>'
        )
        if "</head>" in original:
            original = original.replace("</head>",
                '<link rel="stylesheet" href="/urano/v1/entry/picker.css"></head>', 1)
        # Keep Chema's native Home intro when the logo is clicked.
        # Suppress only the redundant first intro when Stage is launched
        # from the already-authenticated Home/Video chooser.
        # The pinned Chema page still advertises the old proxy-only test
        # export. Owner SMART has a native Companion handoff: original media
        # stays local, the cloud editor works on lightweight proxy files.
        old_note = ("Companion connected: your videos stay on your computer "
                    "and only small versions are uploaded. In this test the "
                    "final video is made from those small versions.")
        new_note = ("Companion connected. Originals stay on your computer. "
                    "Only lightweight proxies are sent for online editing. "
                    "Final export uses local originals through Companion "
                    "when native rendering is available.")
        if original.count(old_note)==1:
            original=original.replace(old_note,new_note,1)
        # Chema's Plans preview is bundled with the original editor. In
        # Owner it must remain inside this authenticated project's static
        # asset scope; the global /montara/plans endpoint is intentionally
        # NOT exposed to anonymous users.
        plans_link = 'href="/montara/plans"'
        if original.count(plans_link) == 1 and "/plans.html" in manifest:
            original = original.replace(plans_link, 'href="plans.html"', 1)
        # Owner has its own catalog title; this field names the exported video.
        output_name = 'Project name <input id="videoName"'
        if original.count(output_name) == 1:
            original = original.replace(output_name,
                'Output video name <input id="videoName"', 1)
        if request.args.get("start") == "stage":
            original = original.replace(
                "<html lang=\"en\">",
                '<html lang="en" class="montara-owner-stage-entry">', 1)
        response=make_response(original.replace(
            first_script, bootstrap+"\\n"+first_script, 1))
        response.headers["Content-Type"]="text/html; charset=utf-8"
        response.headers["Cache-Control"]="private, no-store"
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["X-Frame-Options"]="DENY"
        return response

    @bp.get("/<project_id>/owner-bridge.js")
    def bridge(project_id: str):
        authorize(project_id)
        if not enable_browser_pilot:
            abort(404)
        source=Path(__file__).with_name("owner_browser_bridge.js")
        return Response(source.read_bytes(),mimetype="application/javascript",
                        headers={"Cache-Control":"private, no-store",
                                 "X-Content-Type-Options":"nosniff"})

    @bp.get("/<project_id>/<path:filename>")
    def static(project_id: str, filename: str):
        authorize(project_id)
        path = "/" + filename
        if path not in manifest:
            abort(404)
        # Root and every reviewed asset are pinned by the manifest. Detect
        # substitutions since startup rather than following new symlinks.
        selected = root / filename
        if (selected.is_symlink() or not selected.is_file()
                or any(part.is_symlink() for part in selected.parents if part == root
                       or root in part.parents)):
            abort(404)
        return deliver(filename)

    return bp
