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

from flask import Flask, jsonify, request, send_file
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
        self.transport_timeouts=[]
        self.app=Flask(__name__)
        self.app.config["MAX_CONTENT_LENGTH"]=300_000

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
            owner_test=self
            class AuditedConnection(VerifiedJMUnixConnection):
                def request(self, method, url, *args, **kwargs):
                    owner_test.transport_timeouts.append(
                        (method,url,self.timeout))
                    return super().request(method,url,*args,**kwargs)
            return AuditedConnection(
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
        (home/"WizardUploads"/"song.wav").write_bytes(b"RIFF"+b"\x00"*64)
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

        @worker.post("/api/v1/wizard/upload")
        def direct_upload():
            received=request.get_data()
            self.native_calls.append((owner,"direct-upload",len(received),
                                      request.headers.get("X-Zucker-Filename")))
            return jsonify(videos=[{"path":str(home/"WizardUploads"/"camera.mp4")}])

        @worker.get("/montara/audio")
        def native_audio():
            return send_file(request.args["path"],mimetype="audio/x-wav")

        @worker.post("/montara/branding")
        def branding():
            self.native_calls.append((owner,"branding",request.get_json().get("mode")))
            return jsonify(mode=request.get_json()["mode"],has_logo=False)

        @worker.get("/montara/uploads")
        def native_upload_limits():
            self.native_calls.append((owner,"upload-limits"))
            return jsonify(max_file_bytes=256*1024*1024,
                          max_original_file_bytes=256*1024*1024,
                          chunk_bytes=16*1024*1024,free_bytes=128*1024*1024)

        @worker.post("/montara/uploads")
        def start_resumable():
            payload=request.get_json()
            self.native_calls.append((owner,"upload-init",payload.get("name")))
            return jsonify(id="b"*32,received=0,size=1000,
                           complete=False,chunk_size=16*1024*1024)

        @worker.get("/montara/uploads/<uid>")
        def resume_upload(uid):
            self.native_calls.append((owner,"upload-resume",uid))
            return jsonify(id=uid,received=640,size=1000,
                           complete=False,chunk_size=16*1024*1024)

        @worker.put("/montara/uploads/<uid>")
        def upload_chunk(uid):
            chunk=request.get_data()
            self.native_calls.append((owner,"upload-chunk",uid,len(chunk),
                                      request.headers.get("Upload-Offset")))
            return b"",204

        @worker.post("/montara/uploads/<uid>/finish")
        def finish_upload(uid):
            self.native_calls.append((owner,"upload-finish",uid))
            return jsonify(path=str(home/"WizardUploads"/"camera.mp4"))

        @worker.get("/api/v1/wizard/review")
        def review():
            self.native_calls.append((owner,"review"))
            return jsonify(items=[{
                "index":0,
                "thumbnail":"/api/v1/wizard/review/thumbnail/assets-v2/frame-0.jpg",
                "preview":"/api/v1/wizard/review/preview/0?v=123abc",
            }],platform="youtube")

        @worker.get("/api/v1/wizard/review/thumbnail/assets-v2/frame-0.jpg")
        def thumbnail():
            self.native_calls.append((owner,"thumbnail"))
            return b"jpeg-frame",200,{"Content-Type":"image/jpeg"}

        @worker.get("/api/v1/wizard/review/preview/0")
        def preview():
            range_request=request.headers.get("Range")
            self.native_calls.append((owner,"preview",range_request))
            if range_request=="bytes=0-1":
                return b"mp",206,{
                    "Content-Type":"video/mp4",
                    "Content-Range":"bytes 0-1/10",
                    "Accept-Ranges":"bytes",
                }
            return b"mp4-preview",200,{"Content-Type":"video/mp4"}

        @worker.get("/api/v1/edit/native-recipe")
        def native_recipe():
            self.native_calls.append((owner,"native-recipe"))
            return jsonify(version=1,engine="a"*40,revision="a"*20,
                           platform="youtube",
                           sources=[{"key":0,"path":str(home/"WizardUploads"/"camera.mp4"),
                                     "preview":True}],
                           segments=[{"source":0}],fallbacks={})

        @worker.get("/api/v1/edit/native-master")
        def native_master():
            self.native_calls.append((owner,"native-master"))
            return send_file(home/"WizardUploads"/"song.wav",mimetype="audio/x-wav")

        @worker.get("/api/v1/edit/native-source/<int:index>")
        def native_source(index):
            self.native_calls.append((owner,"native-source",index,request.method))
            return send_file(home/"WizardUploads"/"camera.mp4",mimetype="video/mp4")

        @worker.get("/api/v1/edit/shot")
        def shot_document():
            self.native_calls.append((owner,"shot-get",request.args.get("index")))
            return jsonify(project_id=str(home/"Projects"/"new.zuckervid"),
                           index=int(request.args["index"]),
                           revision="a"*20,choices=[{"label":"Camera 1","spherical":False}])

        @worker.patch("/api/v1/edit/shot")
        def save_shot():
            payload=request.get_json()
            self.native_calls.append((owner,"shot-patch",payload["index"]))
            return jsonify(ok=True,index=payload["index"])

        @worker.get("/api/v1/edit/shot/frame")
        def shot_frame():
            self.native_calls.append((owner,"shot-frame",request.args.get("index")))
            return b"\xff\xd8\xff\xd9",200,{"Content-Type":"image/jpeg"}

        @worker.get("/api/v1/artifacts/sync")
        def sync():
            self.native_calls.append((owner,"sync"))
            return jsonify(status="pending",clips={})

        @worker.post("/api/v1/settings/camera-types")
        def camera_types():
            self.native_calls.append((owner,"camera-types"))
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
        # The route is now enabled for validated proxy bytes; a JSON
        # object is not a legal direct media upload and must fail before
        # any worker descriptor is used.
        self.assertEqual(self.rpc("POST","api/v1/wizard/upload",valid,
                                  json={}).status_code,400)
        self.assertEqual(self.rpc("GET","api/v1/secret",valid).status_code,404)
        self.assertEqual(self.rpc("POST","api/v1/wizard/projects/new",
                                  valid,json=[]).status_code,400)
        self.assertEqual(self.rpc("GET","api/v1/wizard/status",valid,
                          query_string={"owner_id":"owner-b"}).status_code,404)

    def test_original_chema_branding_post_is_authenticated_and_bounded(self):
        headers=self.user(self.a)
        self.assertEqual(self.ensure(headers).status_code,200)
        scope={**headers,"X-Montara-Engine-Generation":"1"}
        ok=self.rpc("POST","montara/branding",scope,json={"mode":"montara"})
        self.assertEqual(ok.status_code,200,ok.get_json())
        self.assertEqual(ok.json["mode"],"montara")
        self.assertIn(("owner-a","branding","montara"),self.native_calls)
        before=len(self.native_calls)
        for payload in ({"mode":"invalid"},{"mode":"montara","path":"/etc/passwd"},
                        {"mode":["montara"]},{}):
            self.assertEqual(self.rpc("POST","montara/branding",scope,
                                      json=payload).status_code,400)
        self.assertEqual(len(self.native_calls),before)
        self.assertEqual(self.rpc("POST","montara/branding",{
            "Origin":ORIGIN,"X-Montara-Engine-Generation":"1"},
            json={"mode":"montara"}).status_code,403)
        self.assertEqual(self.rpc("GET","montara/branding",scope).status_code,404)

    def test_companion_proxy_direct_and_resumable_stage_upload(self):
        headers=self.user(self.a)
        self.assertEqual(self.ensure(headers).status_code,200)
        scope={**headers,"X-Montara-Engine-Generation":"1"}
        limits=self.rpc("GET","montara/uploads",scope)
        self.assertEqual(limits.status_code,200)
        self.assertEqual(limits.json["chunk_bytes"],4*1024*1024)
        self.assertEqual(limits.json["free_bytes"],128*1024*1024)
        self.assertIn(("owner-a","upload-limits"),self.native_calls)
        metadata={
            "name":"camera.small.mp4","size":1000,"fingerprint":"f"*64,
            "video_preview":True,"original":{"filename":"camera.mov"},
        }
        started=self.rpc("POST","montara/uploads",scope,json=metadata)
        self.assertEqual(started.status_code,200,started.get_json())
        uid=started.json["id"]
        self.assertEqual(started.json["chunk_size"],4*1024*1024)
        self.assertEqual(started.json["received"],0)
        resumed=self.rpc("GET","montara/uploads/"+uid,scope)
        self.assertEqual(resumed.status_code,200,resumed.get_json())
        self.assertEqual(resumed.json["received"],640)
        self.assertEqual(resumed.json["chunk_size"],4*1024*1024)
        part=self.rpc("PUT","montara/uploads/"+uid,{
            **scope,"Content-Type":"application/octet-stream",
            "Upload-Offset":"0"},data=b"proxy-part")
        self.assertEqual(part.status_code,204)
        done=self.rpc("POST","montara/uploads/"+uid+"/finish",
                      scope,json={})
        self.assertEqual(done.status_code,200)
        direct=self.rpc("POST","api/v1/wizard/upload",{
            **scope,"Content-Type":"application/octet-stream",
            "X-Zucker-Filename":"clip.small.mp4",
        },data=b"tiny-video")
        self.assertEqual(direct.status_code,200)
        sync=self.rpc("GET","api/v1/artifacts/sync",scope)
        self.assertEqual(sync.status_code,200)
        events=[event[1] for event in self.native_calls]
        self.assertIn("upload-init",events)
        self.assertIn("upload-chunk",events)
        self.assertIn("upload-finish",events)
        self.assertIn("direct-upload",events)
        self.assertIn("sync",events)
        media_timeouts=[(url,timeout) for method,url,timeout
                        in self.transport_timeouts
                        if method in ("PUT","POST") and
                        (url.startswith("/montara/uploads/") or
                         url=="/api/v1/wizard/upload")]
        self.assertTrue(media_timeouts)
        self.assertTrue(all(timeout==35.0 for _,timeout in media_timeouts),
                        media_timeouts)
        self.assertTrue(any(timeout<=10 for method,url,timeout
                            in self.transport_timeouts
                            if url=="/montara/uploads"),
                        self.transport_timeouts)

    def test_streaming_proxy_exceeds_control_plane_limit_without_buffering(self):
        headers=self.user(self.a)
        self.assertEqual(self.ensure(headers).status_code,200)
        scope={**headers,"X-Montara-Engine-Generation":"1"}
        large=b"p"*350_000  # larger than the Owner portal JSON cap
        direct=self.rpc("POST","api/v1/wizard/upload",{
            **scope,"Content-Type":"application/octet-stream",
            "X-Zucker-Filename":"camera.small.mp4",
        },data=large)
        self.assertEqual(direct.status_code,200,direct.get_json())
        uid="b"*32
        chunk=self.rpc("PUT","montara/uploads/"+uid,{
            **scope,"Content-Type":"application/octet-stream",
            "Upload-Offset":"0"},data=large)
        self.assertEqual(chunk.status_code,204)
        self.assertIn(("owner-a","direct-upload",350_000,
                       "camera.small.mp4"),self.native_calls)
        self.assertIn(("owner-a","upload-chunk",uid,350_000,"0"),
                      self.native_calls)

    def test_invalid_proxy_metadata_and_unsafe_direct_names_blocked(self):
        headers=self.user(self.a)
        self.assertEqual(self.ensure(headers).status_code,200)
        scope={**headers,"X-Montara-Engine-Generation":"1"}
        malformed={
            "name":"camera.small.mp4","size":1000,"fingerprint":"f"*64,
            "video_preview":True,"original":{"filename":"camera.mov"},
        }
        for payload in (
            {**malformed,"name":"../../etc/passwd"},
            {**malformed,"size":3*1024**3},
            {**malformed,"fingerprint":"bad"},
            {**malformed,"video_preview":False,
             "size":600*1024**2},
        ):
            with self.subTest(payload=payload):
                count=len(self.native_calls)
                response=self.rpc("POST","montara/uploads",scope,json=payload)
                self.assertEqual(response.status_code,400)
                self.assertEqual(len(self.native_calls),count)
        for filename in ("../../secret.mp4","file.exe","\\x00.mp4"):
            with self.subTest(filename=filename):
                count=len(self.native_calls)
                result=self.rpc("POST","api/v1/wizard/upload",{
                    **scope,"Content-Type":"application/octet-stream",
                    "X-Zucker-Filename":filename,
                },data=b"one-byte-proxy")
                self.assertEqual(result.status_code,400)
                self.assertEqual(len(self.native_calls),count)

    def test_native_export_recipe_master_and_source_scoped_to_owner(self):
        a=self.user(self.a)
        self.assertEqual(self.ensure(a).status_code,200)
        aw=self.registry.get("owner-a").workspace_id
        folder=self.workers[aw][0]
        scope={**a,"X-Montara-Engine-Generation":"1"}
        saved=self.rpc("POST","api/v1/wizard/draft",scope,json={
            "project_id":None,"videos":[str(folder/"WizardUploads"/"camera.mp4")]})
        self.assertEqual(saved.status_code,200)
        project=saved.json["project_id"]
        qs={"project_id":project}
        recipe=self.rpc("GET","api/v1/edit/native-recipe",scope,query_string=qs)
        self.assertEqual(recipe.status_code,200,recipe.get_data(as_text=True))
        self.assertEqual(recipe.json["sources"][0]["key"],0)
        mediaq={**qs,"revision":"a"*20}
        master=self.rpc("GET","api/v1/edit/native-master",scope,query_string=mediaq)
        self.assertEqual(master.status_code,200,master.data)
        self.assertTrue(master.data.startswith(b"RIFF"))
        self.assertEqual(master.mimetype,"audio/x-wav")
        head=self.rpc("HEAD","api/v1/edit/native-source/0",scope,query_string=mediaq)
        self.assertEqual(head.status_code,200,head.data)
        self.assertEqual(head.data,b"")
        media=self.rpc("GET","api/v1/edit/native-source/0",scope,query_string=mediaq)
        self.assertEqual(media.status_code,200,media.data)
        self.assertEqual(media.data,b"private-camera")
        before=len(self.native_calls)
        for operation in ("api/v1/edit/native-recipe",
                          "api/v1/edit/native-master",
                          "api/v1/edit/native-source/0"):
            extra=qs if operation.endswith("recipe") else mediaq
            self.assertEqual(self.rpc("GET",operation,scope,
                    query_string={**extra,"other":"x"}).status_code,404)
            self.assertEqual(self.rpc("GET",operation,scope,
                    query_string={**extra,"project_id":"/etc/passwd"}).status_code,403)
        self.assertEqual(len(self.native_calls),before)
        b=self.user(self.b)
        self.assertEqual(self.ensure(b).status_code,200)
        foreign={**b,"X-Montara-Engine-Generation":"1"}
        for operation in ("api/v1/edit/native-recipe",
                          "api/v1/edit/native-master",
                          "api/v1/edit/native-source/0"):
            extra=qs if operation.endswith("recipe") else mediaq
            self.assertEqual(self.rpc("GET",operation,foreign,
                    query_string=extra).status_code,403)

    def test_shot_editor_read_patch_and_private_frame_are_owner_scoped(self):
        a=self.user(self.a)
        self.assertEqual(self.ensure(a).status_code,200)
        aw=self.registry.get("owner-a").workspace_id
        own_project=str(self.workers[aw][0]/"Projects"/"new.zuckervid")
        scope={**a,"X-Montara-Engine-Generation":"1"}
        created=self.rpc("POST","api/v1/wizard/draft",scope,json={
            "project_id":None,"name":"Stage shot",
            "videos":[str(self.workers[aw][0]/"WizardUploads"/"camera.mp4")]})
        self.assertEqual(created.status_code,200)
        self.assertEqual(created.json["project_id"],own_project)
        read=self.rpc("GET","api/v1/edit/shot",scope,
                      query_string={"index":"3"})
        self.assertEqual(read.status_code,200,read.get_data(as_text=True))
        self.assertEqual(read.json["index"],3)
        frame=self.rpc("GET","api/v1/edit/shot/frame",scope,
                       query_string={"index":"3","choice":"0",
                                     "revision":"a"*20})
        self.assertEqual(frame.status_code,200,frame.data)
        self.assertEqual(frame.mimetype,"image/jpeg")
        changed=self.rpc("PATCH","api/v1/edit/shot",scope,json={
            "project_id":own_project,"revision":"a"*20,"index":3,
            "choice":0,"edit_component":"movement","movement":True,
            "apply_to_source":False,"playback_speed":1.0})
        self.assertEqual(changed.status_code,200,changed.get_data(as_text=True))
        tunneled=self.rpc("POST","api/v1/edit/shot/save",scope,json={
            "project_id":own_project,"revision":"a"*20,"index":3,
            "choice":0,"edit_component":"movement","movement":True,
            "apply_to_source":False,"playback_speed":1.0})
        self.assertEqual(tunneled.status_code,200,tunneled.get_data(as_text=True))
        before=len(self.native_calls)
        self.assertEqual(self.rpc("POST","api/v1/edit/shot",scope,json={
            "project_id":own_project,"revision":"a"*20,"index":3,
            "choice":0,"apply_to_source":False,
            "edit_component":"movement"}).status_code,404)
        self.assertEqual(self.rpc("POST","api/v1/edit/shot/save",scope,
            query_string={"index":"3"},json={}).status_code,404)
        for query in ({"index":"0","another":"bad"},
                      {"index":"-1"},{"index":"x"}):
            self.assertEqual(self.rpc("GET","api/v1/edit/shot",scope,
                         query_string=query).status_code,404)
        for query in ({"index":"3","choice":"0","revision":"a"*20,
                       "path":"/etc/passwd"},
                      {"index":"3","choice":"0","revision":"bad"}):
            self.assertEqual(self.rpc("GET","api/v1/edit/shot/frame",scope,
                         query_string=query).status_code,404)
        self.assertEqual(self.rpc("PATCH","api/v1/edit/shot",scope,json={
            "project_id":"/etc/passwd","revision":"a"*20,"index":3,
            "choice":0,"apply_to_source":False,
            "edit_component":"movement"}).status_code,403)
        self.assertEqual(self.rpc("PATCH","api/v1/edit/shot",scope,json={
            "project_id":own_project,"revision":"a"*20,"index":3,
            "choice":0,"apply_to_source":True,
            "edit_component":"movement"}).status_code,400)
        self.assertEqual(len(self.native_calls),before)
        b=self.user(self.b)
        self.assertEqual(self.ensure(b).status_code,200)
        foreign={**b,"X-Montara-Engine-Generation":"1"}
        self.assertEqual(self.rpc("PATCH","api/v1/edit/shot",foreign,json={
            "project_id":own_project,"revision":"a"*20,"index":3,
            "choice":0,"apply_to_source":False,
            "edit_component":"movement"}).status_code,403)
        self.assertEqual(self.rpc("POST","api/v1/edit/shot/save",foreign,json={
            "project_id":own_project,"revision":"a"*20,"index":3,
            "choice":0,"apply_to_source":False,
            "edit_component":"movement"}).status_code,403)

    def test_private_audio_playback_rejects_foreign_and_arbitrary_paths(self):
        a=self.user(self.a)
        self.assertEqual(self.ensure(a).status_code,200)
        aw=self.registry.get("owner-a").workspace_id
        own=str(self.workers[aw][0]/"WizardUploads"/"song.wav")
        scope={**a,"X-Montara-Engine-Generation":"1"}
        ok=self.rpc("GET","montara/audio",scope,query_string={"path":own})
        self.assertEqual(ok.status_code,200,ok.get_data(as_text=True))
        self.assertEqual(ok.data[:4],b"RIFF")
        self.assertEqual(ok.mimetype,"audio/x-wav")
        for query in ({"path":"/etc/passwd"},{"path":own,"other":"x"},
                      {"path":own+"../bad"},{"path":own,"owner_id":"owner-b"}):
            response=self.rpc("GET","montara/audio",scope,query_string=query)
            self.assertIn(response.status_code,(403,404))
        b=self.user(self.b)
        self.assertEqual(self.ensure(b).status_code,200)
        other={**b,"X-Montara-Engine-Generation":"1"}
        foreign=self.rpc("GET","montara/audio",other,query_string={"path":own})
        self.assertEqual(foreign.status_code,403)
        self.assertEqual(self.rpc("GET","montara/audio",
                         {"Origin":ORIGIN},query_string={"path":own}).status_code,403)

    def test_private_review_thumbnails_and_video_range_keep_google_csrf(self):
        headers=self.user(self.a)
        self.assertEqual(self.ensure(headers).status_code,200)
        scope={**headers,"X-Montara-Engine-Generation":"1"}
        review=self.rpc("GET","api/v1/wizard/review",scope,
                        query_string={"render":"0"})
        self.assertEqual(review.status_code,200)
        self.assertEqual(review.json["items"][0]["index"],0)
        thumb=self.rpc("GET",
            "api/v1/wizard/review/thumbnail/assets-v2/frame-0.jpg",scope)
        self.assertEqual(thumb.status_code,200)
        self.assertEqual(thumb.data,b"jpeg-frame")
        self.assertTrue(thumb.content_type.startswith("image/jpeg"))
        preview=self.rpc("GET","api/v1/wizard/review/preview/0",
            {**scope,"Range":"bytes=0-1"},query_string={"v":"123abc"})
        self.assertEqual(preview.status_code,206)
        self.assertEqual(preview.data,b"mp")
        self.assertEqual(preview.headers.get("Content-Range"),"bytes 0-1/10")
        # The test client still carries owner-a's cookie, so the request
        # without CSRF must be denied 403. Without a cookie it must be 401.
        self.assertEqual(self.rpc("GET",
            "api/v1/wizard/review/thumbnail/assets-v2/frame-0.jpg",
            {"Origin":ORIGIN}).status_code,403)
        self.client.delete_cookie(SESSION_COOKIE,domain="montara.test")
        self.assertEqual(self.rpc("GET",
            "api/v1/wizard/review/thumbnail/assets-v2/frame-0.jpg",
            scope).status_code,401)
        self.user(self.a)
        self.assertEqual(self.rpc("GET","api/v1/wizard/review/preview/0",
            {**scope,"Range":"bytes=0-1,2-3"}).status_code,416)
        self.assertEqual(self.rpc("GET","api/v1/wizard/review/preview/0",
            scope,query_string={"source":"/etc/passwd"}).status_code,404)

    def test_stage_settings_reject_other_users_camera_paths(self):
        headers=self.user(self.a)
        self.assertEqual(self.ensure(headers).status_code,200)
        wa=self.registry.get("owner-a")
        foreign=str(self.workers[wa.workspace_id][0]/
                    "WizardUploads"/"camera.mp4")
        bh=self.user(self.b)
        self.assertEqual(self.ensure(bh).status_code,200)
        scope={**bh,"X-Montara-Engine-Generation":"1"}
        bad=self.rpc("POST","api/v1/settings/camera-types",scope,
                     json={"camera_types":{foreign:"wide"}})
        self.assertEqual(bad.status_code,403)
        self.assertNotIn(("owner-b","camera-types"),self.native_calls)
        wb=self.registry.get("owner-b")
        own=str(self.workers[wb.workspace_id][0]/
                "WizardUploads"/"camera.mp4")
        ok=self.rpc("POST","api/v1/settings/camera-types",scope,
                    json={"camera_types":{own:"wide"}})
        self.assertEqual(ok.status_code,200)
        self.assertIn(("owner-b","camera-types"),self.native_calls)

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
