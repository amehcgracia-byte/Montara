"""I54 real original Chema resumable Companion proxy through Owner HTTP gateway.

Actual Flask JM+Engine, private AF_UNIX WSGI, Owner session+CSRF,
operator-injected ensure/connection (real root broker is tested separately).
Tiny synthetic MP4, original protocol create->PUT->finish->Stage draft.
Never modifies live beta or Chema main.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
from http.client import HTTPConnection
from pathlib import Path


PROJECT="7b8f5fd6-02b4-4cd0-8d16-c2d6d606a505"


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--bundle",type=Path,required=True)
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args()
    if not args.execute: parser.error("Operator-only --execute required")
    bundle=args.bundle.resolve(strict=True)
    if (bundle.parent!=Path("/opt/montara/bundles")
            or not bundle.name.startswith("engine-") or len(bundle.name)!=47
            or any(c not in "0123456789abcdef" for c in bundle.name[7:])):
        parser.error("Pinned real Engine required")
    checkout=Path(__file__).resolve().parents[1]
    if not (checkout/"app.py").is_file() or not (checkout/"resumable_upload.py").is_file():
        parser.error("Original Chema JM checkout required")
    sys.path[:0]=[str(checkout),str(bundle/"site"),str(bundle/"app"),str(bundle/"engine")]
    from flask import Flask
    from app import create_montara_app
    from core.project import new_project_document
    from urano.owner_first_stage_wizard import OwnerFirstStageWizard
    from urano.original_jm_owner_assets import original_editor_assets_blueprint
    from urano.owner_original_jm_rpc import initial_stage_gateway_blueprint
    from urano.project_catalog import ProjectCatalog
    from urano.session_auth import SessionStore,SESSION_COOKIE
    from urano.private_jm_wsgi_socket import create_private_jm_wsgi_server

    with tempfile.TemporaryDirectory(prefix="montara-i54-resumable-") as tmp:
        root=Path(tmp)
        data=root/"durable-Owner-A"
        runtime=root/"runtime"
        data.mkdir(mode=0o700)
        runtime.mkdir(mode=0o700)
        folder=data/"Projects"/PROJECT
        folder.mkdir(parents=True)
        (folder/"project.json").write_text(
            json.dumps(new_project_document(PROJECT)),encoding="utf-8")
        media=root/"camera.small.mp4"
        subprocess.run([
            "ffmpeg","-hide_banner","-loglevel","error","-y",
            "-f","lavfi","-i","testsrc2=size=640x360:rate=12:duration=3",
            "-c:v","libx264","-preset","ultrafast","-pix_fmt","yuv420p",
            str(media),
        ],check=True,stderr=subprocess.PIPE,timeout=45)
        content=media.read_bytes()
        digest=hashlib.sha256(content[:65536]+content[-65536:]).hexdigest()
        os.environ["MONTARA_SESSION_TOKEN"]="x"*64
        app=create_montara_app(data,samples=False)
        os.environ.pop("MONTARA_SESSION_TOKEN",None)
        opened=app.test_client().post(
            "/api/v1/wizard/projects/open",json={"path":str(folder)})
        if opened.status_code!=200:
            raise RuntimeError("Real JM Engine did not open Owner project")
        server,sock=create_private_jm_wsgi_server(
            OwnerFirstStageWizard(app,owner_project_folder=folder),runtime)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            owner_db=root/"owner"
            owner_db.mkdir()
            catalog=ProjectCatalog(owner_db/"projects.sqlite3")
            with catalog._connect() as ignored:
                pass
            # The Owner catalog UUID is normally minted independently. For
            # this lab use the created catalog's actual UUID and mirror it in
            # worker project folder only when it is the same literal project.
            import sqlite3
            with sqlite3.connect(catalog.db_path) as connection:
                connection.execute(
                    "INSERT INTO urano_projects (project_id,owner_id,title,recipe,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (PROJECT,"owner-a","Stage A",
                     '{"montara_beta_workspace":{"mode":"stage","version":1}}',
                     1,1))
            sessions=SessionStore(owner_db/"sessions.sqlite3")
            auth=sessions.issue("owner-a")
            checks=[]
            def ensure(op,session,csrf,project):
                checks.append(("ensure",project))
                return {"ok":True,"state":"ready",
                        "project_id":project,"generation":5}
            def connect(session,csrf,project,generation):
                if generation!=5:
                    raise RuntimeError("Wrong Engine generation")
                conn=HTTPConnection("localhost",timeout=5)
                unix=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
                unix.connect(str(sock))
                conn.sock=unix
                return conn
            owner=Flask("owner-jm-real-resumable")
            owner.register_blueprint(initial_stage_gateway_blueprint(
                catalog,sessions,https_origin="https://owner.test",
                ensure_worker=ensure,connect_worker=connect))
            client=owner.test_client()
            client.set_cookie(SESSION_COOKIE,auth.token,domain="owner.test")
            headers={"Origin":"https://owner.test","X-Urano-CSRF":auth.csrf}
            base="/urano/v1/media/"+PROJECT+"/"
            def call(method,suffix,**kwargs):
                return client.open(
                    base+suffix,method=method,base_url="https://owner.test",
                    headers={**headers,**kwargs.pop("headers",{})},**kwargs)
            limits=call("GET","uploads")
            if limits.status_code!=200 or checks:
                raise RuntimeError("GET limits unnecessarily started Engine")
            if limits.json.get("max_file_bytes")!=256*1024**2:
                raise RuntimeError("Mismatched remote media size limit")
            init=call("POST","uploads",json={
                "name":"camera.small.mp4","size":len(content),
                "fingerprint":digest,
                "video_preview":True,
                "original":{"name":"camera.mp4","size":len(content)*5,
                            "fingerprint":"f"*64},
            })
            if init.status_code!=201:
                raise RuntimeError("Original JM upload create failed: "+str(init.json))
            upload_id=init.json["id"]
            if checks!=[("ensure",PROJECT)]:
                raise RuntimeError("First proxy metadata did not trigger Owner Engine")
            h={"X-Montara-Engine-Generation":"5","Upload-Offset":"0"}
            put=call("PUT","uploads/"+upload_id,data=content,
                     content_type="application/octet-stream",headers=h)
            if put.status_code not in (200,204):
                raise RuntimeError("Real original JM chunk rejected: "+str(put.json))
            h={"X-Montara-Engine-Generation":"5"}
            finished=call("POST","uploads/"+upload_id+"/finish",
                          data="{}",content_type="application/json",
                          headers=h)
            if finished.status_code!=200:
                raise RuntimeError("Original JM finish rejected: "+str(finished.json))
            videos=finished.json.get("videos") or []
            if len(videos)!=1:
                raise RuntimeError("Original JM did not classify video proxy: "+str(finished.json)[:500])
            path=videos[0]["path"]
            started=call("POST","wizard/projects/new",
                         data="{}",content_type="application/json",headers=h)
            draft=call("POST","wizard/draft",json={
                "name":"Real resumable Stage","platform":"youtube",
                "project_id":None,"master":"","audio_paths":[],"videos":[path],
            },headers=h)
            if (started.status_code!=200 or draft.status_code!=200
                    or draft.json.get("project_id")!=str(folder)):
                raise RuntimeError("Resumable video did not bind to Owner Stage")
            if checks!=[("ensure",PROJECT)]:
                raise RuntimeError("Unexpected duplicate Engine starts")
            print(json.dumps({
                "real_chema_resumable_upload":True,
                "original_engine_classified_synthetic_video":True,
                "owner_session_and_csrf":True,
                "first_valid_create_triggered_one_engine_ensure":True,
                "original_chunk_put_and_finish":True,
                "original_stage_draft_owner_uuid":True,
                "broker_kernel_connection_stubbed":True,
                "real_windows_companion":False,
                "public_cloud_beta_changed":False,
            },sort_keys=True))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=4)
            sock.unlink(missing_ok=True)


if __name__=="__main__":
    main()
