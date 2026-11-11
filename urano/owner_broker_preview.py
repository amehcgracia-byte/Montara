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


def _broker_frame_request(payload: dict) -> dict:
    frame=json.dumps(payload,separators=(",",":")).encode()
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


def broker_request(operation: str, session: str, csrf: str, project: str) -> dict:
    return _broker_frame_request({
        "op":operation, "session":session, "csrf":csrf, "project_id":project
    })


def broker_stage_request(session: str, csrf: str, project: str,
                         generation: int) -> dict:
    if type(generation) is not int or generation < 1:
        raise ValueError("Invalid private Engine generation")
    return _broker_frame_request({
        "op":"stage_snapshot_owner", "session":session,
        "csrf":csrf, "project_id":project, "generation":generation
    })

def owner_engine_preview_blueprint(catalog:ProjectCatalog,sessions:SessionStore,
                                   *,https_origin:str)->Blueprint:
    bp=Blueprint("urano_i27_owner_engine_preview",__name__,url_prefix="/urano/v1")

    @bp.get("/projects/<project_id>/stage-status")
    def stage_status(project_id: str):
        # No Engine unit, worker address, backend URL or filesystem path from
        # the browser. Even read-only operations require current CSRF.
        if request.host_url.rstrip("/") != https_origin:
            return jsonify(error="Trusted HTTPS origin required"),403
        if request.content_length not in (None,0):
            return jsonify(error="Body unsupported"),400
        token=request.cookies.get(SESSION_COOKIE)
        user=sessions.verify(token)
        if user is None:
            return jsonify(error="Authentication required"),401
        csrf=request.headers.get("X-Urano-CSRF")
        if not user.matches_csrf(csrf):
            return jsonify(error="Invalid CSRF token"),403
        generation=request.args.get("generation", "")
        if (not generation.isascii() or not generation.isdecimal()
                or len(generation)>10 or int(generation)<1):
            return jsonify(error="Invalid Engine generation"),400
        from urano.editor_project_bridge import project_mode
        try:
            project=catalog.get(user.owner_id,project_id)
        except (ProjectNotFound, ValueError):
            return jsonify(error="Project not found"),404
        if project_mode(project)!="stage":
            return jsonify(error="Project not found"),404
        try:
            result=broker_stage_request(token,csrf,project_id,int(generation))
        except (ValueError,OSError,RuntimeError,TimeoutError,json.JSONDecodeError):
            return jsonify(error="Private Engine unavailable"),503
        if (result.get("ok") is not True or result.get("project_id") != project_id
                or result.get("generation") != int(generation)):
            return jsonify(error="Stage unavailable"),503
        if (not isinstance(result.get("stages"),dict)
                or type(result.get("camera_count")) is not int):
            return jsonify(error="Invalid private Stage status"),503
        response=jsonify(project_id=project_id,generation=int(generation),
                         stages=result["stages"],camera_count=result["camera_count"])
        response.headers["Cache-Control"]="no-store"
        return response

    @bp.post("/projects/<project_id>/ensure")
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
        op=("ensure_owner" if request.path.endswith("/ensure") else
            "open_owner" if request.path.endswith("/open") else "close_owner")
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

