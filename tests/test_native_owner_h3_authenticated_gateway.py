"""H3 real Owner cookie/CSRF -> independent admission -> Unix FD -> Chema recovery.

Workers here are original Flask recovery handlers and controlled wizard
fixtures (NOT video renders). Private sockets and SQLite session, catalog and
workspace registry are real. This test does not touch GCP or production.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

from flask import Flask, jsonify, request
from recovery import register_recovery

from urano.native_owner_web_gateway import native_owner_gateway_blueprint
from urano.native_owner_workspace_gate import NativeOwnerWorkspaceGate
from urano.native_owner_workspace_registry import (
    NativeOwnerWorkspaceRegistry,
)
from urano.private_jm_wsgi_socket import (
    VerifiedJMUnixConnection, create_private_jm_wsgi_server,
)
from urano.private_owner_admission import verify_owner_and_project
from urano.private_editor_connect_admission import verify_editor_connect_request
from urano.project_catalog import ProjectCatalog
from urano.session_auth import SESSION_COOKIE, SessionStore

ORIGIN="https://montara.test"


class NativeOwnerH3AuthenticatedGatewayTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="montara-h3-owner-")
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.catalog=ProjectCatalog(self.root/"projects.sqlite3")
        self.registry=NativeOwnerWorkspaceRegistry(self.catalog)
        self.sessions=SessionStore(self.root/"sessions.sqlite3")
        self.a=self.sessions.issue("owner-a")
        self.b=self.sessions.issue("owner-b")
        self.workers={}
        self.ensure_calls=[]
        self.native_calls=[]
        self.app=Flask(__name__)

        def ensure_worker(operation,token,csrf,workspace):
            raw=json.dumps({"op":operation,"session":token,"csrf":csrf,
                            "project_id":workspace}).encode()
            verified,owner,identity=verify_owner_and_project(
                raw,owner_db_root=self.root)
            self.assertEqual(verified,"ensure_owner")
            self.assertEqual(identity,workspace)
            self.ensure_calls.append((owner,workspace))
            if workspace not in self.workers:
                self.create_worker(owner,workspace)
            return {"ok":True,"project_id":workspace,
                    "generation":1,"state":"ready"}

        def connect_worker(token,csrf,workspace,generation):
            raw=json.dumps({"op":"connect_editor","session":token,
                            "csrf":csrf,"project_id":workspace,
                            "generation":generation}).encode()
            owner,claimed,requested=verify_editor_connect_request(
                raw,owner_db_root=self.root)
            if requested!=1 or claimed!=workspace:
                raise PermissionError("Stale worker generation")
            directory=self.workers[workspace][1]
            return VerifiedJMUnixConnection(
                directory/"jm-editor-http.sock",
                expected_pid=os.getpid(),expected_uid=os.getuid())

        self.app.register_blueprint(native_owner_gateway_blueprint(
            self.sessions,self.registry,https_origin=ORIGIN,
            ensure_worker=ensure_worker,connect_worker=connect_worker))
        self.client=self.app.test_client()

    def create_worker(self,owner,workspace):
        home=self.root/"worker-data"/workspace
        runtime=self.root/"worker-run"/workspace
        for directory in (home,runtime):
            directory.mkdir(parents=True,mode=0o700)
        for sub in ("Projects","Sessions","WizardUploads"):
            (home/sub).mkdir()
        (home/"WizardUploads"/"camera.mp4").write_bytes(b"private-camera")
        worker=Flask("worker-"+workspace)
        register_recovery(worker,home)

        @worker.post("/api/v1/wizard/projects/new")
        def new():
            self.native_calls.append((owner,"new"))
            return jsonify(ok=True)

        @worker.post("/api/v1/wizard/draft")
        def draft():
            body=request.get_json()
            self.native_calls.append((owner,"draft"))
            saved=home/"Projects"/"new.zuckervid"
            saved.mkdir(exist_ok=True)
            (saved/"project.json").write_text(json.dumps({
                "name":"New edit","inputs":{"videos":[{"path":"camera.mp4"}]},
                "stages":{}
            }))
            return jsonify(project_id=str(saved))

        @worker.post("/api/v1/wizard/projects/open")
        def open_project():
            self.native_calls.append((owner,"open"))
            return jsonify(ok=True)

        @worker.get("/api/v1/wizard/status")
        def status():
            self.native_calls.append((owner,"status"))
            return jsonify(status="idle")

        worker.wsgi_app=NativeOwnerWorkspaceGate(worker.wsgi_app,data_root=home)
        server,socketpath=create_private_jm_wsgi_server(worker,runtime)
        process=threading.Thread(target=server.serve_forever,daemon=True)
        process.start()
        self.workers[workspace]=(home,runtime,server,process)
        self.addCleanup(self.stop_worker,workspace)

    def stop_worker(self,workspace):
        home,runtime,server,thread=self.workers[workspace]
        server.shutdown()
        server.server_close()
        thread.join(timeout=4)
        (runtime/"jm-editor-http.sock").unlink(missing_ok=True)

    def user(self,session):
        self.client.set_cookie(SESSION_COOKIE,session.token,domain="montara.test")
        return {"Origin":ORIGIN,"X-Urano-CSRF":session.csrf}

    def ensure(self,headers):
        return self.client.post("/urano/v1/native/ensure",
                                headers=headers,base_url=ORIGIN)

    def rpc(self,method,operation,headers,**kwargs):
        return self.client.open("/urano/v1/native/rpc/"+operation,
            method=method,headers=headers,base_url=ORIGIN,**kwargs)

    def test_two_independent_users_new_draft_and_latest(self):
        aheaders=self.user(self.a)
        start=self.ensure(aheaders)
        self.assertEqual(start.status_code,200,start.get_json())
        self.assertEqual(start.json["state"],"ready")
        first_workspace=self.registry.get("owner-a")
        self.assertIsNotNone(first_workspace)
        self.assertEqual(self.ensure(aheaders).status_code,200)
        self.assertEqual(len(self.catalog.list_for("owner-a")),1)
        gen={**aheaders,"X-Montara-Engine-Generation":"1"}
        fresh=self.rpc("GET","montara/recovery/latest",gen)
        self.assertEqual(fresh.status_code,404)
        new=self.rpc("POST","api/v1/wizard/projects/new",gen,json={})
        self.assertEqual(new.status_code,200,new.get_json())
        folder=self.workers[first_workspace.workspace_id][0]
        saved=self.rpc("POST","api/v1/wizard/draft",gen,json={
            "project_id":None,"name":"New edit",
            "videos":[str(folder/"WizardUploads"/"camera.mp4")]})
        self.assertEqual(saved.status_code,200,saved.get_json())
        latest=self.rpc("GET","montara/recovery/latest",gen)
        self.assertEqual(latest.status_code,200)
        self.assertEqual(latest.json["kind"],"project")
        self.assertEqual(latest.json["path"],saved.json["project_id"])
        self.assertEqual(self.rpc("POST","api/v1/wizard/projects/new",
                                 gen,json={}).status_code,200)
        self.assertEqual(self.rpc("GET","montara/recovery/latest",gen).status_code,200)

        bheaders=self.user(self.b)
        self.assertEqual(self.ensure(bheaders).status_code,200)
        other=self.registry.get("owner-b")
        self.assertNotEqual(other.workspace_id,first_workspace.workspace_id)
        bgen={**bheaders,"X-Montara-Engine-Generation":"1"}
        self.assertEqual(self.rpc("GET","montara/recovery/latest",bgen).status_code,404)
        openforeign=self.rpc("POST","api/v1/wizard/projects/open",bgen,
                             json={"path":saved.json["project_id"]})
        self.assertEqual(openforeign.status_code,403)
        self.assertNotIn("owner-a",openforeign.get_data(as_text=True))
        self.assertEqual([who for who,method in self.native_calls
                          if method=="new"],["owner-a","owner-a"])

    def test_no_cookie_csrf_or_wrong_origin_never_reaches_broker(self):
        initial=self.ensure({
            "Origin":ORIGIN,"X-Urano-CSRF":self.a.csrf})
        self.assertEqual(initial.status_code,401)
        self.assertFalse(self.ensure_calls)
        self.user(self.a)
        for headers in (
            {"Origin":ORIGIN},
            {"Origin":ORIGIN,"X-Urano-CSRF":"0"*64},
            {"Origin":"https://untrusted.test","X-Urano-CSRF":self.a.csrf},
        ):
            with self.subTest(headers=headers):
                self.assertEqual(self.ensure(headers).status_code,403)
        self.assertFalse(self.ensure_calls)

    def test_legacy_owner_is_fail_closed_without_automatic_migration(self):
        self.catalog.create("owner-a","Existing Stage")
        headers=self.user(self.a)
        rejected=self.ensure(headers)
        self.assertEqual(rejected.status_code,409)
        self.assertIsNone(self.registry.get("owner-a"))
        self.assertEqual(len(self.catalog.list_for("owner-a")),1)
        self.assertFalse(self.ensure_calls)

    def test_stale_generation_and_unreviewed_routes_rejected(self):
        headers=self.user(self.a)
        self.assertEqual(self.ensure(headers).status_code,200)
        valid={**headers,"X-Montara-Engine-Generation":"1"}
        stale={**headers,"X-Montara-Engine-Generation":"2"}
        self.assertEqual(self.rpc("GET","montara/recovery/latest",stale).status_code,503)
        self.assertEqual(self.rpc("POST","api/v1/wizard/upload",valid,
                                  json={}).status_code,404)
        self.assertEqual(self.rpc("GET","api/v1/secret",valid).status_code,404)
        self.assertEqual(self.rpc("POST","api/v1/wizard/projects/new",
                                  valid,json=[]).status_code,400)
        self.assertEqual(self.rpc("GET","api/v1/wizard/status",valid,
                          query_string={"owner_id":"owner-b"}).status_code,404)

    def test_foreign_media_paths_are_denied_by_the_private_worker(self):
        aheaders=self.user(self.a)
        self.assertEqual(self.ensure(aheaders).status_code,200)
        a=self.registry.get("owner-a")
        bheaders=self.user(self.b)
        self.assertEqual(self.ensure(bheaders).status_code,200)
        own=self.registry.get("owner-b")
        bgen={**bheaders,"X-Montara-Engine-Generation":"1"}
        aroot=self.workers[a.workspace_id][0]
        attempt=self.rpc("POST","api/v1/wizard/draft",bgen,json={
            "project_id":None,"videos":[str(aroot/"WizardUploads"/"camera.mp4")]})
        self.assertEqual(attempt.status_code,403)
        self.assertNotIn(("owner-b","draft"),self.native_calls)


if __name__=="__main__":
    unittest.main()
