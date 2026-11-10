"""I27 optional HTTPS Owner -> independently authorized private broker socket.

The browser supplies ONLY a canonical project UUID from the route. The broker
verifies the opaque Google session and rotating CSRF independently in readonly
SQLite. No systemd flags, IDs, PIDs or paths from the user.
"""
from __future__ import annotations

import json
import socket

from flask import Blueprint, jsonify, request

from urano.project_catalog import ProjectCatalog,ProjectNotFound
from urano.session_auth import SESSION_COOKIE,SessionStore

SOCKET="/run/montara-i27-admission/control.sock"


def broker_request(operation: str, session: str, csrf: str, project: str) -> dict:
    frame=json.dumps({"op":operation,"session":session,
        "csrf":csrf,"project_id":project},separators=(",",":")).encode()
    if len(frame)>384:
        raise ValueError("Invalid owner frame")
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
        client.settimeout(38)
        client.connect(SOCKET)
        client.sendall(frame)
        reply=client.recv(2048)
    result=json.loads(reply)
    if not isinstance(result,dict):
        raise RuntimeError("Invalid broker response")
    return result


def owner_engine_preview_blueprint(catalog:ProjectCatalog,sessions:SessionStore,
                                   *,https_origin:str)->Blueprint:
    bp=Blueprint("urano_i27_owner_engine_preview",__name__,url_prefix="/urano/v1")

    @bp.post("/projects/<project_id>/open")
    @bp.post("/projects/<project_id>/close")
    def dispatch(project_id:str):
        if (request.host_url.rstrip("/")!=https_origin or
            request.headers.get("Origin")!=https_origin):
            return jsonify(error="Trusted HTTPS origin required"),403
        if (request.content_length not in (None,0) or
            request.headers.get("Transfer-Encoding")):
            return jsonify(error="Request body unsupported"),400
        token=request.cookies.get(SESSION_COOKIE)
        user=sessions.verify(token)
        if user is None:
            return jsonify(error="Authentication required"),401
        csrf=request.headers.get("X-Urano-CSRF")
        if not user.matches_csrf(csrf):
            return jsonify(error="Invalid CSRF token"),403
        try:
            catalog.get(user.owner_id,project_id)
        except (ProjectNotFound,ValueError):
            return jsonify(error="Project not found"),404
        op="open_owner" if request.path.endswith("/open") else "close_owner"
        try:
            outcome=broker_request(op,token,csrf,project_id)
        except (ValueError,OSError,RuntimeError,TimeoutError,json.JSONDecodeError):
            return jsonify(error="Private Engine unavailable"),503
        if not outcome.get("ok"):
            kind=outcome.get("error")
            if kind in ("BusyOwner","RuntimeBusy"):
                return jsonify(error="Engine already busy"),409
            if kind in ("OwnerAdmissionDenied","StaleJob"):
                return jsonify(error="Private project unavailable"),404
            return jsonify(error="Private Engine unavailable"),503
        if outcome.get("project_id")!=project_id:
            return jsonify(error="Engine identity mismatch"),503
        response=jsonify(project_id=project_id,state=outcome.get("state"),
                         generation=outcome.get("generation"))
        response.headers["Cache-Control"]="no-store"
        return response

    return bp

