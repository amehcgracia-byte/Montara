"""Opt-in local-only HTTP preview of existing cached proxies.

No arbitrary filesystem paths in HTTP requests; no files are transcoded here.
Not suitable as a public/multiuser API without authentication.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from flask import abort, jsonify, request, send_file, Response

from local_media.proxies import proxy_signature, stamp

_SOURCE_ID = re.compile(r"[a-f0-9]{24}\Z")
_LOOPBACK = {"127.0.0.1", "::1"}


def register_local_proxy_preview(app, data_root):
    cache = Path(data_root).resolve() / "LocalProxyCache"

    @app.before_request
    def _local_proxy_guard():
        if request.path.startswith("/montara/local-preview/"):
            if request.remote_addr not in _LOOPBACK:
                return jsonify(error={"message": "Local-only preview."}), 403

    def resolve(source_id):
        if not _SOURCE_ID.fullmatch(source_id):
            abort(404)
        manifest = cache / (source_id + ".local.json")
        proxy = cache / (source_id + ".mp4")
        try:
            record = json.loads(manifest.read_text())
            original = Path(record["original"]).resolve()
            if (record.get("source_id") != source_id
                or record.get("proxy") != str(proxy)
                or record.get("original_stamp") != stamp(original)
                or not proxy.is_file()
                or proxy.stat().st_size == 0
                or record.get("proxy_signature") != proxy_signature(proxy)):
                abort(404)
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            abort(404)
        return record, proxy

    @app.get("/montara/local-preview/<source_id>/metadata")
    def local_proxy_metadata(source_id):
        record, _ = resolve(source_id)
        return jsonify(record["public"])

    @app.get("/montara/local-preview/<source_id>/video")
    def local_proxy_video(source_id):
        _, proxy = resolve(source_id)
        response = send_file(proxy, mimetype="video/mp4", conditional=True)
        response.headers["Cache-Control"] = "private, no-store"
        return response

    @app.get("/montara/local-preview/<source_id>/view")
    def local_proxy_view(source_id):
        record, _ = resolve(source_id)
        # Standalone playback integration smoke page; not the production editor.
        video_path = "/montara/local-preview/" + source_id + "/video"
        document = (
            "<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>Montara local proxy preview</title>"
            "<body style='margin:2rem;background:#171717;color:white;font-family:sans-serif'>"
            "<h1>Montara — cached preview</h1>"
            "<video controls playsinline preload='metadata' style='max-width:100%;max-height:75vh' src='"
            + video_path + "'></video>"
            "<p>This is the cached preview. Final exports still use original sources.</p>"
            "</body></html>"
        )
        return Response(document, mimetype="text/html", headers={"Cache-Control": "private, no-store"})
