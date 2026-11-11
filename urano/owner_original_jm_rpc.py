"""I51 opt-in Owner-scoped first Stage RPC gateway to ORIGINAL Chema APIs.

One authenticated browser project URL -> independently attested broker and
one private Unix connection per request; NO global /api/v1 shared Engine.
Does not alter any original JM handler, Engine, UI or Companion code.

Only the initial Stage operations are admitted. The browser may send an exact
project UUID in the URL but cannot choose owner, backend host, socket, PID,
worker generation or filesystem path. Generation for non-upload requests must
match the broker's current worker. Originals remain Companion-local by default.

IMPORTANT: this is an opt-in bridge not registered in the live beta. A separate
browser adapter must map Chema's current absolute URLs into this gateway.
"""
from __future__ import annotations

import json
import re
from http.client import HTTPException

from flask import Blueprint, Response, jsonify, request

from urano.first_valid_upload_gate import valid_first_upload
from urano.owner_broker_preview import broker_request
from urano.owner_private_http_client import authenticated_private_jm_connection
from urano.project_catalog import ProjectCatalog, ProjectNotFound
from urano.session_auth import SESSION_COOKIE, SessionStore

_ALLOWED = {
    ("POST", "wizard/upload"): "/api/v1/wizard/upload",
    ("POST", "wizard/projects/new"): "/api/v1/wizard/projects/new",
    ("POST", "wizard/draft"): "/api/v1/wizard/draft",
    ("GET", "wizard/status"): "/api/v1/wizard/status",
    ("GET", "project"): "/api/v1/project",
}
_GEN = re.compile(r"[1-9][0-9]{0,9}\Z")
_FILE = re.compile(r"[^\\/\x00-\x1f]{1,200}\Z")
_MAX_JSON = 256_000
_MAX_VIDEO = 256 * 1024 * 1024
_MAX_RESULT = 1_000_000


def initial_stage_gateway_blueprint(
    catalog: ProjectCatalog, sessions: SessionStore, *,
    https_origin: str,
    ensure_worker=broker_request,
    connect_worker=authenticated_private_jm_connection,
) -> Blueprint:
    """Only explicit provider-neutral control-plane callbacks are injected."""
    bp=Blueprint("urano_i51_original_jm_rpc", __name__,
                 url_prefix="/urano/v1/media")

    @bp.route("/<project_id>/<path:operation>", methods=["GET", "POST"])
    def relay(project_id: str, operation: str):
        path=_ALLOWED.get((request.method,operation))
        if path is None or request.query_string:
            return jsonify(error="Unsupported original editor operation"),404
        if request.host_url.rstrip("/") != https_origin:
            return jsonify(error="Trusted HTTPS host required"),403
        if request.headers.get("Origin") != https_origin:
            # All calls including read-only API are authenticated and CSRF
            # gated. Same-origin JS can reliably supply these headers.
            return jsonify(error="Trusted HTTPS origin required"),403
        token=request.cookies.get(SESSION_COOKIE)
        owner=sessions.verify(token)
        if owner is None:
            return jsonify(error="Authentication required"),401
        csrf=request.headers.get("X-Urano-CSRF")
        if not owner.matches_csrf(csrf):
            return jsonify(error="Invalid CSRF token"),403
        try:
            project=catalog.get(owner.owner_id,project_id)
            from urano.editor_project_bridge import project_mode
            if project_mode(project)!="stage":
                raise ProjectNotFound("Not a Stage project")
        except (ProjectNotFound, ValueError):
            return jsonify(error="Private Stage project unavailable"),404
        content_length=request.content_length
        if request.headers.get("Transfer-Encoding") or (
                request.method=="GET" and content_length not in (None,0)):
            return jsonify(error="Unsupported request framing"),400
        if request.method=="POST":
            if type(content_length) is not int or content_length<=0:
                return jsonify(error="Expected bounded request body"),400
            if operation=="wizard/upload":
                if (not valid_first_upload(request.environ)
                        or content_length>_MAX_VIDEO):
                    return jsonify(error="Invalid private video upload"),400
            elif (content_length>_MAX_JSON
                  or request.mimetype!="application/json"):
                return jsonify(error="Invalid original editor JSON"),400
        if operation=="wizard/upload":
            try:
                admitted=ensure_worker("ensure_owner",token,csrf,project_id)
            except (OSError,ValueError,RuntimeError,TimeoutError):
                return jsonify(error="Owner Engine unavailable"),503
            if (not isinstance(admitted,dict) or admitted.get("ok") is not True
                    or admitted.get("project_id")!=project_id
                    or admitted.get("state")!="ready"
                    or type(admitted.get("generation")) is not int
                    or admitted["generation"]<1):
                return jsonify(error="Owner Engine not ready"),503
            generation=admitted["generation"]
        else:
            raw_generation=request.headers.get("X-Montara-Engine-Generation","")
            if not _GEN.fullmatch(raw_generation):
                return jsonify(error="Engine generation required"),409
            generation=int(raw_generation)
        try:
            with connect_worker(token,csrf,project_id,generation) as conn:
                headers={"Cache-Control":"no-store"}
                if request.method=="POST":
                    headers["Content-Type"]=request.content_type
                    headers["Content-Length"]=str(content_length)
                    if operation=="wizard/upload":
                        filename=request.headers.get("X-Zucker-Filename","")
                        from urllib.parse import unquote
                        if not _FILE.fullmatch(unquote(filename)):
                            return jsonify(error="Invalid media filename"),400
                        headers["X-Zucker-Filename"]=filename
                    body=request.stream
                else:
                    body=None
                conn.request(request.method,path,body=body,headers=headers)
                reply=conn.getresponse()
                data=reply.read(_MAX_RESULT+1)
                if len(data)>_MAX_RESULT:
                    raise ValueError("Oversized private JM response")
                status=reply.status
                content_type=reply.getheader("Content-Type","application/json")
        except (OSError,ValueError,TimeoutError,HTTPException,RuntimeError):
            return jsonify(error="Private original editor unavailable"),503
        if not 100<=status<=599 or "\r" in content_type or "\n" in content_type:
            return jsonify(error="Invalid private editor response"),503
        # Never pass through Set-Cookie, CORS, redirects or backend headers.
        result=Response(data,status=status,content_type=content_type)
        result.headers["Cache-Control"]="no-store"
        result.headers["X-Content-Type-Options"]="nosniff"
        result.headers["X-Montara-Engine-Generation"]=str(generation)
        return result

    return bp
