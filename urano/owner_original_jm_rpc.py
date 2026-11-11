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
from contextlib import closing
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
    ("POST", "branding"): "/montara/branding",
    ("GET", "uploads"): "/montara/uploads",
    ("POST", "uploads"): "/montara/uploads",
}
_GEN = re.compile(r"[1-9][0-9]{0,9}\Z")
_FILE = re.compile(r"[^\\/\x00-\x1f]{1,200}\Z")
_MAX_JSON = 256_000
_MAX_VIDEO = 256 * 1024 * 1024
_MAX_RESULT = 1_000_000
_UPLOAD_PART = re.compile(r"uploads/([a-f0-9]{32})(/finish)?\Z")
_MAX_CHUNK = 16 * 1024 * 1024



def initial_stage_gateway_blueprint(
    catalog: ProjectCatalog, sessions: SessionStore, *,
    https_origin: str,
    ensure_worker=broker_request,
    connect_worker=authenticated_private_jm_connection,
) -> Blueprint:
    """Only explicit provider-neutral control-plane callbacks are injected."""
    bp=Blueprint("urano_i51_original_jm_rpc", __name__,
                 url_prefix="/urano/v1/media")

    @bp.route("/<project_id>/<path:operation>",
              methods=["GET", "POST", "PUT", "DELETE"])
    def relay(project_id: str, operation: str):
        path=_ALLOWED.get((request.method,operation))
        upload_part=_UPLOAD_PART.fullmatch(operation)
        if path is None and upload_part:
            uid, finishing=upload_part.groups()
            if (not finishing and request.method in ("GET","PUT","DELETE")
                    or finishing and request.method=="POST"):
                path="/montara/uploads/"+uid+("/finish" if finishing else "")
        if path is None or request.query_string:
            return jsonify(error="Unsupported original editor operation"),404
        if request.host_url.rstrip("/") != https_origin:
            return jsonify(error="Trusted HTTPS host required"),403
        supplied_origin=request.headers.get("Origin")
        if ((request.method!="GET" and supplied_origin!=https_origin)
                or (request.method=="GET" and supplied_origin not in
                    (None,https_origin))):
            # Browsers need not include Origin on same-origin GET; CSRF on
            # every read blocks cross-origin JS, since the token is not in a
            # readable cookie and custom headers trigger CORS preflight.
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
        if operation=="uploads" and request.method=="GET":
            # Original JM upload limits normally need a running worker.
            # This read-only preflight intentionally doesn't activate Engine.
            # Free space is not asserted: original JM checks it on POST.
            reply=jsonify(max_file_bytes=_MAX_VIDEO,
                          chunk_bytes=4*1024*1024,free_bytes=None)
            reply.headers["Cache-Control"]="no-store"
            return reply
        content_length=request.content_length
        if request.headers.get("Transfer-Encoding") or (
                request.method=="GET" and content_length not in (None,0)):
            return jsonify(error="Unsupported request framing"),400
        if request.method in ("POST","PUT"):
            if type(content_length) is not int or content_length<=0:
                return jsonify(error="Expected bounded request body"),400
            if operation in ("wizard/upload","uploads"):
                # The resumable JSON validator restores wsgi.input after
                # reading; keep that restored stream on Flask's ACTUAL
                # environ, not on a copy whose underlying input was drained.
                original_path=request.environ["PATH_INFO"]
                request.environ["PATH_INFO"]=path
                try:
                    valid=valid_first_upload(request.environ)
                finally:
                    request.environ["PATH_INFO"]=original_path
                if (not valid or content_length>_MAX_VIDEO):
                    return jsonify(error="Invalid private upload"),400
            elif request.method=="PUT":
                offset=request.headers.get("Upload-Offset","")
                if (not upload_part or upload_part.group(2)
                        or content_length>_MAX_CHUNK
                        or request.mimetype!="application/octet-stream"
                        or not offset.isascii() or not offset.isdecimal()
                        or len(offset)>16):
                    return jsonify(error="Invalid upload chunk"),400
            elif (content_length>_MAX_JSON
                  or request.mimetype!="application/json"):
                return jsonify(error="Invalid original editor JSON"),400
        elif request.method=="DELETE" and content_length not in (None,0):
            return jsonify(error="DELETE body unsupported"),400
        if request.method=="POST" and operation in ("wizard/upload","uploads"):
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
            with closing(connect_worker(token,csrf,project_id,generation)) as conn:
                headers={"Cache-Control":"no-store"}
                if request.method in ("POST","PUT"):
                    headers["Content-Type"]=request.content_type
                    headers["Content-Length"]=str(content_length)
                    if operation=="wizard/upload":
                        filename=request.headers.get("X-Zucker-Filename","")
                        from urllib.parse import unquote
                        if not _FILE.fullmatch(unquote(filename)):
                            return jsonify(error="Invalid media filename"),400
                        headers["X-Zucker-Filename"]=filename
                    if request.method=="PUT":
                        headers["Upload-Offset"]=request.headers["Upload-Offset"]
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
