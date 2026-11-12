"""Authenticated Owner -> private Chema New/Latest gateway, no project picker.

Owner verifies Google session + rotating CSRF + stable workspace ID.
The root broker independently verifies those same credentials, generation,
project ownership and the DynamicUser/cgroup before granting a worker FD.
The worker then validates native project and media paths against its own
per-owner data_root. No shared Engine or public native JM endpoints.

Only a small, explicitly reviewed set of original Chema JSON routes is
forwarded here. Uploads, previews, native exports, Music/Push/Show APIs and
large media are NOT enabled by this first H3 gate.
"""
from __future__ import annotations

import json
import re
from contextlib import closing
from http.client import HTTPException

from flask import Blueprint, Response, jsonify, request

from urano.native_owner_new_latest_http import native_new_latest_target
from urano.native_owner_workspace_registry import (
    NativeOwnerWorkspaceRegistry, ExistingOwnerProjects,
)
from urano.owner_broker_preview import broker_request
from urano.owner_private_http_client import authenticated_private_jm_connection
from urano.session_auth import SESSION_COOKIE, SessionStore

_GEN = re.compile(r"[1-9][0-9]{0,9}\Z")
_MAX_BODY = 256_000
_MAX_REPLY = 1_000_000


def native_owner_gateway_blueprint(
        sessions: SessionStore, registry: NativeOwnerWorkspaceRegistry,
        *, https_origin: str, ensure_worker=broker_request,
        connect_worker=authenticated_private_jm_connection,
) -> Blueprint:
    bp = Blueprint("urano_native_chema_owner_gateway", __name__,
                   url_prefix="/urano/v1/native")

    def verified():
        if request.host_url.rstrip("/") != https_origin:
            return None, None, (jsonify(error="Trusted HTTPS origin required"),403)
        origin = request.headers.get("Origin")
        if (request.method not in ("GET","HEAD") and origin != https_origin or
                request.method in ("GET","HEAD") and origin not in (None,https_origin)):
            return None, None, (jsonify(error="Trusted HTTPS origin required"),403)
        token = request.cookies.get(SESSION_COOKIE)
        session = sessions.verify(token)
        if session is None:
            return None,None,(jsonify(error="Authentication required"),401)
        csrf = request.headers.get("X-Urano-CSRF")
        if not session.matches_csrf(csrf):
            return None,None,(jsonify(error="Invalid private session"),403)
        return token,csrf,None

    def owned_workspace(token):
        session = sessions.verify(token)
        if session is None:
            return None
        return registry.get(session.owner_id)

    @bp.post("/ensure")
    def ensure():
        token,csrf,error = verified()
        if error is not None:
            return error
        if request.content_length not in (None,0) or request.headers.get("Transfer-Encoding"):
            return jsonify(error="Body unsupported"),400
        session = sessions.verify(token)
        try:
            workspace = registry.get(session.owner_id)
            if workspace is None:
                # Only new Owners can be enrolled automatically. Existing beta
                # projects must be reconciled by the operator, never silently
                # chosen or modified by browser login.
                workspace = registry.reserve_new(session.owner_id)
        except ExistingOwnerProjects:
            return jsonify(error=(
                "Existing private projects require a safe one-time migration; "
                "nothing has been changed")),409
        try:
            result = ensure_worker("ensure_owner",token,csrf,workspace.workspace_id)
        except (OSError,ValueError,RuntimeError,TimeoutError):
            return jsonify(error="Private Engine unavailable"),503
        if (not isinstance(result,dict) or result.get("ok") is not True or
                result.get("project_id") != workspace.workspace_id or
                result.get("state") != "ready" or
                type(result.get("generation")) is not int or
                not 1 <= result["generation"] < 2**31):
            return jsonify(error="Private Engine not ready"),503
        response = jsonify(state="ready",generation=result["generation"])
        response.headers["Cache-Control"] = "no-store"
        return response

    @bp.route("/rpc/<path:operation>",
              methods=["GET","POST"])
    def native_rpc(operation: str):
        path = "/" + operation
        target = native_new_latest_target(
            request.method,path,request.query_string.decode("ascii","strict")
            if request.query_string.isascii() else "")
        if target is None:
            return jsonify(error="Original editor operation not enabled"),404
        token,csrf,error = verified()
        if error is not None:
            return error
        workspace = owned_workspace(token)
        if workspace is None:
            return jsonify(error="Private workspace unavailable"),409
        generation = request.headers.get("X-Montara-Engine-Generation","")
        if not _GEN.fullmatch(generation) or int(generation)>=2**31:
            return jsonify(error="Private Engine generation required"),409
        if request.headers.get("Transfer-Encoding"):
            return jsonify(error="Unsupported request framing"),400
        if request.method == "GET":
            if request.content_length not in (None,0):
                return jsonify(error="Body unsupported"),400
            body = None
        else:
            length = request.content_length
            if (type(length) is not int or length < 2 or
                    length > _MAX_BODY or request.mimetype != "application/json"):
                return jsonify(error="Expected bounded JSON body"),400
            body = request.get_data(cache=False)
            if len(body) != length:
                return jsonify(error="Incomplete native request"),400
            try:
                value=json.loads(body)
            except (ValueError,TypeError):
                return jsonify(error="Invalid native JSON"),400
            if not isinstance(value,dict):
                return jsonify(error="Invalid native JSON object"),400
        try:
            with closing(connect_worker(token,csrf,workspace.workspace_id,
                                         int(generation))) as conn:
                headers={"Cache-Control":"no-store"}
                if body is not None:
                    headers["Content-Type"]="application/json"
                    headers["Content-Length"]=str(len(body))
                conn.request(request.method,target,body=body,headers=headers)
                upstream=conn.getresponse()
                reply=upstream.read(_MAX_REPLY+1)
                code=upstream.status
                content_type=upstream.getheader("Content-Type","application/json")
        except (OSError,ValueError,TimeoutError,RuntimeError,HTTPException):
            return jsonify(error="Private original editor unavailable"),503
        if (len(reply)>_MAX_REPLY or not 100<=code<=599 or
                not content_type.lower().startswith("application/json") or
                any(c in content_type for c in "\r\n")):
            return jsonify(error="Unexpected native worker response"),503
        response=Response(reply,status=code,content_type=content_type)
        response.headers["Cache-Control"]="no-store"
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["X-Montara-Engine-Generation"]=generation
        return response

    return bp
