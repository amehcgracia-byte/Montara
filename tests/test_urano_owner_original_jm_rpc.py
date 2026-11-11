"""I51 live AF_UNIX HTTP RPC through Owner-scoped Flask endpoint.

Checks two Owner identities, CSRF, wrong project, stale generation,
unsupported paths, unchanged JM APIs and actual proxy bytes. Tests inject
trusted lab callbacks instead of touching root systemd.
"""
import json
import socket
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path

from flask import Flask, jsonify, request

from urano.owner_original_jm_rpc import initial_stage_gateway_blueprint
from urano.private_jm_wsgi_socket import create_private_jm_wsgi_server
from urano.project_catalog import ProjectCatalog
from urano.session_auth import SESSION_COOKIE, SessionStore

ORIGIN="https://montara.test"


class JMRealHTTPRPCContracts(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root=Path(temp.name)
        self.catalog=ProjectCatalog(root/"projects.sqlite3")
        self.sessions=SessionStore(root/"sessions.sqlite3")
        self.a=self.catalog.create("owner-a","Stage A",recipe={
            "montara_beta_workspace":{"mode":"stage","version":1}})
        self.b=self.catalog.create("owner-b","Stage B",recipe={
            "montara_beta_workspace":{"mode":"stage","version":1}})
        self.push=self.catalog.create("owner-a","Push",recipe={
            "montara_beta_workspace":{"mode":"push","version":1}})
        self.session=self.sessions.issue("owner-a")
        self.events=[]
        worker=Flask("original-jm-http-worker-lab")
        @worker.post("/api/v1/wizard/upload")
        def upload():
            data=request.get_data()
            self.events.append(("upload",len(data)))
            return jsonify(videos=[{"path":"/private/mock/video.mp4"}],size=len(data))
        @worker.post("/api/v1/wizard/projects/new")
        def new():
            self.events.append(("new",None))
            return jsonify(ok=True)
        @worker.post("/api/v1/wizard/draft")
        def draft():
            body=request.get_json()
            self.events.append(("draft",body))
            return jsonify(project_id="/private/mock/project")
        @worker.post("/api/v1/wizard/prepare")
        def prepare():
            self.events.append(("prepare",request.get_json()))
            return jsonify(status="running"),202

        @worker.post("/api/v1/wizard/start")
        def start():
            self.events.append(("start",request.get_json()))
            return jsonify(status="running"),202

        @worker.post("/api/v1/settings/fillers")
        def fillers():
            self.events.append(("fillers",request.get_json()))
            return jsonify(ok=True)

        @worker.get("/api/v1/wizard/status")
        def poll():
            self.events.append(("poll",dict(request.args)))
            return jsonify(status="waiting_choice")

        @worker.get("/api/v1/artifacts/sync")
        def sync():
            self.events.append(("sync",None))
            return jsonify(clips={},status="done")

        @worker.get("/api/v1/wizard/review")
        def review():
            self.events.append(("review",dict(request.args)))
            return jsonify(items=[{
                "index":0, "thumbnail":"/api/v1/wizard/review/thumbnail/assets-v2/frame-0.jpg",
                "preview":"/api/v1/wizard/review/preview/0?v=abcdef00",
                "duration_sec":3.0}], platform="youtube")

        @worker.post("/api/v1/wizard/review/replace")
        def replace_shot():
            self.events.append(("replace",request.get_json()))
            return jsonify(replaced=[0])

        @worker.post("/api/v1/wizard/review/render")
        def render_review():
            self.events.append(("render",request.get_json()))
            return jsonify(status="running"),202

        @worker.get("/api/v1/wizard/review/thumbnail/assets-v2/frame-0.jpg")
        def thumbnail():
            self.events.append(("thumbnail",None))
            return b"jpeg-thumbnail",200,{"Content-Type":"image/jpeg"}

        @worker.get("/api/v1/wizard/review/preview/0")
        def preview():
            self.events.append(("preview",request.headers.get("Range")))
            if request.headers.get("Range")=="bytes=0-1":
                return b"mp",206,{
                    "Content-Type":"video/mp4","Content-Range":"bytes 0-1/10",
                    "Accept-Ranges":"bytes"}
            return b"mp4-preview",200,{"Content-Type":"video/mp4"}

        @worker.get("/api/v1/edit/timeline")
        def timeline():
            self.events.append(("timeline",dict(request.args)))
            return jsonify(kind="music",revision=1,boundaries=[])

        @worker.patch("/api/v1/edit/timeline")
        def timeline_patch():
            self.events.append(("timeline_patch",request.get_json()))
            return jsonify(kind="music",revision=2,boundaries=[])

        @worker.get("/api/v1/edit/shot")
        def shot():
            self.events.append(("shot",dict(request.args)))
            return jsonify(index=0,revision=1,cameras=[0])

        @worker.patch("/api/v1/edit/shot")
        def shot_patch():
            self.events.append(("shot_patch",request.get_json()))
            return jsonify(ok=True,revision=2)

        @worker.get("/api/v1/edit/shot/frame")
        def shot_frame():
            self.events.append(("shot_frame",dict(request.args)))
            return b"jpeg-stage-frame",200,{"Content-Type":"image/jpeg"}

        @worker.get("/api/v1/project")
        def status():
            self.events.append(("status",None))
            return jsonify(stages={"ingest":{"status":"pending"}})
        directory=root/"worker"
        directory.mkdir(mode=0o700)
        self.server,self.socket=create_private_jm_wsgi_server(worker,directory)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.ensured=[]
        self.connected=[]
        def ensure(op,session,csrf,project):
            self.ensured.append((op,project))
            return {"ok":True,"state":"ready",
                    "project_id":project,"generation":9}
        def connect(session,csrf,project,generation):
            self.connected.append((project,generation))
            if generation!=9:
                raise RuntimeError("stale generation")
            conn=HTTPConnection("localhost",timeout=3)
            sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
            sock.connect(str(self.socket))
            conn.sock=sock
            return conn
        gateway=Flask("owner-private-jm-rpc")
        gateway.register_blueprint(initial_stage_gateway_blueprint(
            self.catalog,self.sessions,https_origin=ORIGIN,
            ensure_worker=ensure,connect_worker=connect))
        self.client=gateway.test_client()
        self.client.set_cookie(
            SESSION_COOKIE,self.session.token,domain="montara.test")
        self.headers={"Origin":ORIGIN,"X-Urano-CSRF":self.session.csrf}

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.socket.unlink(missing_ok=True)

    def url(self,operation,project=None):
        return "/urano/v1/media/"+(project or self.a.id)+"/"+operation

    def post(self,operation,data,headers=None,content_type="application/json",
             project=None):
        return self.client.post(
            self.url(operation,project),
            data=data,headers=headers or self.headers,
            content_type=content_type,base_url=ORIGIN)

    def test_mp3_first_upload_and_readable_error_for_native_chema_xhr(self):
        # No private media or live user project; one synthetic MP3 wire request.
        audio=b"fake-mp3-test-bytes"*9000
        header={**self.headers,"X-Zucker-Filename":"4._Minor_7th.mp3"}
        uploaded=self.post("wizard/upload",audio,header,"application/octet-stream")
        self.assertEqual(uploaded.status_code,200,uploaded.get_data(as_text=True))
        self.assertEqual(uploaded.json["size"],len(audio))
        self.assertEqual(self.ensured,[("ensure_owner",self.a.id)])
        bad=self.post("wizard/upload",b"invalid",{
            **self.headers,"X-Zucker-Filename":"bad.exe"
        },"application/octet-stream")
        self.assertEqual(bad.status_code,400)
        self.assertIsInstance(bad.json["error"],dict)
        self.assertIn("message",bad.json["error"])

    def test_real_proxy_bytes_and_original_jm_followup(self):
        video=b"proxy-video-bytes"*7000
        headers=dict(self.headers,**{"X-Zucker-Filename":"camera.small.mp4"})
        upload=self.post("wizard/upload",video,headers,
                         "application/octet-stream")
        self.assertEqual(upload.status_code,200,upload.get_data(as_text=True))
        self.assertEqual(upload.json["size"],len(video))
        self.assertEqual(upload.headers["X-Montara-Engine-Generation"],"9")
        self.assertEqual(self.ensured,[("ensure_owner",self.a.id)])
        follow=dict(self.headers,**{"X-Montara-Engine-Generation":"9"})
        created=self.post("wizard/projects/new","{}",follow)
        self.assertEqual(created.status_code,200)
        draft=self.post("wizard/draft",json.dumps({
            "name":"Stage","platform":"youtube","videos":["/private/mock/video.mp4"],
        }),follow)
        self.assertEqual(draft.status_code,200)
        self.assertEqual(self.events[0],("upload",len(video)))
        self.assertEqual(self.events[1][0],"new")
        self.assertEqual(self.events[2][0],"draft")
        self.assertEqual(self.ensured,[("ensure_owner",self.a.id)])

    def test_real_megabyte_proxy_crosses_owner_300kb_control_plane_cap(self):
        # Mirror the actual beta Flask MAX_CONTENT_LENGTH. A valid media
        # request can stream, but all normal Owner routes retain 300 KB.
        self.client.application.config["MAX_CONTENT_LENGTH"]=300_000
        payload=b"synthetic-proxy"*100_000
        headers={**self.headers,"X-Zucker-Filename":"camera.small.mp4"}
        response=self.post("wizard/upload",payload,headers,
                           "application/octet-stream")
        self.assertEqual(response.status_code,200,response.get_data(as_text=True))
        self.assertEqual(response.json["size"],len(payload))
        self.assertEqual(self.ensured,[("ensure_owner",self.a.id)])
        self.assertIn(("upload",len(payload)),self.events)

    def test_project_and_csrf_rejected_before_any_worker(self):
        cases=[
            (self.b.id,self.headers,404),
            (self.push.id,self.headers,404),
            (self.a.id,{"Origin":ORIGIN},403),
            (self.a.id,{"Origin":"https://evil.test",
                        "X-Urano-CSRF":self.session.csrf},403),
        ]
        for project,headers,expected in cases:
            with self.subTest(project=project,headers=headers):
                res=self.post("wizard/upload",b"x",headers,
                              "application/octet-stream",project)
                self.assertEqual(res.status_code,expected)
        self.assertEqual(self.ensured,[])
        self.assertEqual(self.connected,[])

    def test_opt_in_large_companion_proxy_but_never_large_original(self):
        # Reuses the same private lab worker callbacks; no multi-GB bytes
        # are materialized, only a bounded JSON metadata request.
        from urano.owner_original_jm_rpc import initial_stage_gateway_blueprint
        app=Flask("larger-private-proxy")
        app.register_blueprint(initial_stage_gateway_blueprint(
            self.catalog,self.sessions,https_origin=ORIGIN,
            ensure_worker=lambda op,session,csrf,project:{
                "ok":True,"state":"ready","generation":9,"project_id":project},
            connect_worker=lambda *args: (_ for _ in ()).throw(
                RuntimeError("no media transfer in metadata policy test")),
            private_preview_limit_mib=2048))
        test=app.test_client()
        test.set_cookie(
            SESSION_COOKIE,self.session.token,domain="montara.test")
        url="/urano/v1/media/"+self.a.id+"/uploads"
        limits=test.get(url,base_url=ORIGIN,headers=self.headers)
        self.assertEqual(limits.status_code,200)
        self.assertEqual(limits.json["max_file_bytes"],2048*1024**2)
        self.assertEqual(limits.json["max_original_file_bytes"],256*1024**2)
        accepted=test.post(url,base_url=ORIGIN,headers=self.headers,json={
            "name":"camera.small.mp4","size":650*1024**2,
            "fingerprint":"f"*64,"video_preview":True,
            "original":{"name":"camera.mp4","size":4*1024**3,
                        "fingerprint":"e"*64}})
        self.assertEqual(accepted.status_code,503)  # passed metadata gate
        original=test.post(url,base_url=ORIGIN,headers=self.headers,json={
            "name":"camera.mp4","size":650*1024**2,
            "fingerprint":"f"*64,"original_video_consent":True})
        self.assertEqual(original.status_code,400)

    def test_real_chema_continue_sync_status_is_fenced_to_owner(self):
        headers=dict(self.headers,**{"X-Montara-Engine-Generation":"9"})
        for operation,body,expected in (
            ("settings/fillers",{"fillers":[],"cutaways":[]},200),
            ("wizard/prepare",{"platform":"youtube","videos":["private"]},202),
            ("wizard/start",{"platform":"youtube","videos":["private"]},202),
        ):
            with self.subTest(operation=operation):
                reply=self.client.post(self.url(operation),
                    base_url=ORIGIN,headers=headers,json=body)
                self.assertEqual(reply.status_code,expected)
        poll=self.client.get(
            self.url("wizard/status")+"?project_id=%2Ftmp%2Fother-owner",
            base_url=ORIGIN,headers=headers)
        self.assertEqual(poll.status_code,200)
        self.assertEqual(self.events[-1],("poll",{}))
        sync=self.client.get(self.url("artifacts/sync"),
            base_url=ORIGIN,headers=headers)
        self.assertEqual(sync.status_code,200)
        self.assertEqual(self.events[-1][0],"sync")
        self.assertEqual(self.ensured,[])
        denied=self.client.get(
            self.url("wizard/status")+"?project_id=x&project_id=y",
            base_url=ORIGIN,headers=headers)
        self.assertEqual(denied.status_code,404)
        foreign=self.client.get(
            self.url("artifacts/sync",self.b.id),
            base_url=ORIGIN,headers=headers)
        self.assertEqual(foreign.status_code,404)

    def test_authenticated_review_images_video_range_and_render(self):
        headers={**self.headers,"X-Montara-Engine-Generation":"9"}
        review=self.client.get(self.url("wizard/review")+"?render=1&shot=0",
                               base_url=ORIGIN,headers=headers)
        self.assertEqual(review.status_code,200,review.get_data(as_text=True))
        self.assertEqual(self.events[-1],("review",{"render":"1","shot":"0"}))
        self.assertEqual(review.json["items"][0]["index"],0)
        thumb=self.client.get(
            self.url("wizard/review/thumbnail/assets-v2/frame-0.jpg"),
            base_url=ORIGIN,headers=headers)
        self.assertEqual(thumb.status_code,200)
        self.assertEqual(thumb.data,b"jpeg-thumbnail")
        preview=self.client.get(self.url("wizard/review/preview/0?v=abcdef00"),
            base_url=ORIGIN,headers={**headers,"Range":"bytes=0-1"})
        self.assertEqual(preview.status_code,206)
        self.assertEqual(preview.headers["Content-Range"],"bytes 0-1/10")
        self.assertEqual(preview.data,b"mp")
        swapped=self.client.post(self.url("wizard/review/replace"),
            base_url=ORIGIN,headers=headers,json={"rejected":[0]})
        self.assertEqual(swapped.status_code,200)
        render=self.client.post(self.url("wizard/review/render"),
            base_url=ORIGIN,headers=headers,json={})
        self.assertEqual(render.status_code,202)
        self.assertEqual(self.events[-1][0],"render")
        for url in (
            self.url("wizard/review")+"?render=1&shot=../../etc/passwd",
            self.url("wizard/review")+"?render=1&render=0",
            self.url("wizard/review/preview/0?path=/tmp/other"),
            self.url("wizard/review/thumbnail/other-file/foreign.jpg"),
        ):
            with self.subTest(url=url):
                result=self.client.get(url,base_url=ORIGIN,headers=headers)
                self.assertEqual(result.status_code,404)
        forbidden=self.client.get(
            self.url("wizard/review/preview/0",self.b.id),
            base_url=ORIGIN,headers=headers)
        self.assertEqual(forbidden.status_code,404)
        self.assertEqual(self.ensured,[])

    def test_original_stage_manual_shot_and_music_cut_edit(self):
        headers={**self.headers,"X-Montara-Engine-Generation":"9"}
        timeline=self.client.get(
            self.url("edit/timeline")+"?kind=music",
            base_url=ORIGIN,headers=headers)
        self.assertEqual(timeline.status_code,200)
        self.assertEqual(self.events[-1],("timeline",{"kind":"music"}))
        doc=self.client.get(self.url("edit/shot")+"?index=0",
            base_url=ORIGIN,headers=headers)
        self.assertEqual(doc.status_code,200)
        shot=self.client.patch(self.url("edit/shot"),
            base_url=ORIGIN,headers=headers,
            json={"project_id":"/private/owner-folder","revision":1,
                  "index":0,"choice":0,"movement":True})
        self.assertEqual(shot.status_code,200)
        self.assertEqual(self.events[-1][0],"shot_patch")
        moved=self.client.patch(self.url("edit/timeline"),
            base_url=ORIGIN,headers=headers,
            json={"kind":"music","project_id":"/private/owner-folder",
                  "revision":1,"index":1,"at":2.5})
        self.assertEqual(moved.status_code,200)
        frame=self.client.get(self.url("edit/shot/frame")
            +"?index=0&choice=0&revision=1",
            base_url=ORIGIN,headers=headers)
        self.assertEqual(frame.status_code,200)
        self.assertEqual(frame.data,b"jpeg-stage-frame")
        for forbidden in (
            self.url("edit/timeline")+"?kind=show",
            self.url("edit/shot")+"?index=../other",
            self.url("edit/shot/frame")+"?index=0&choice=0&revision=1&path=/tmp",
        ):
            with self.subTest(forbidden=forbidden):
                response=self.client.get(forbidden,base_url=ORIGIN,headers=headers)
                self.assertEqual(response.status_code,404)
        self.assertEqual(self.ensured,[])

    def test_resumable_limits_do_not_start_engine_and_bad_metadata_denied(self):
        limits=self.client.get(self.url("uploads"),
            base_url=ORIGIN,headers=self.headers)
        self.assertEqual(limits.status_code,200)
        self.assertEqual(limits.json["max_file_bytes"],256*1024**2)
        self.assertEqual(self.ensured,[])
        for body in (
            {"name":"../../other-owner.mp4","size":30,
             "fingerprint":"f"*64},
            {"name":"cam.small.mp4","size":False,
             "fingerprint":"f"*64},
            {"name":"cam.small.mp4","size":600*1024**2,
             "fingerprint":"f"*64},
            {"name":"cam.small.mp4","size":30,
             "fingerprint":"not-a-hash"},
        ):
            with self.subTest(body=body):
                reply=self.client.post(self.url("uploads"),
                    base_url=ORIGIN,headers=self.headers,json=body)
                self.assertEqual(reply.status_code,400)
        self.assertEqual(self.ensured,[])
        self.assertEqual(self.connected,[])
        invalid_chunk=dict(self.headers,**{
            "X-Montara-Engine-Generation":"9","Upload-Offset":"-1"})
        reply=self.client.put(
            self.url("uploads/"+"a"*32),
            base_url=ORIGIN,headers=invalid_chunk,
            data=b"chunk",content_type="application/octet-stream")
        self.assertEqual(reply.status_code,400)
        self.assertEqual(self.connected,[])

    def test_missing_stale_generation_and_unreviewed_path_denied(self):
        no_gen=self.post("wizard/draft","{}")
        self.assertEqual(no_gen.status_code,409)
        stale=dict(self.headers,**{"X-Montara-Engine-Generation":"8"})
        reply=self.post("wizard/draft","{}",stale)
        self.assertEqual(reply.status_code,503)
        wrong=self.post("show/references/open","{}",stale)
        self.assertEqual(wrong.status_code,404)
        self.assertEqual(self.events,[])

    def test_get_project_never_starts_worker(self):
        headers=dict(self.headers,**{"X-Montara-Engine-Generation":"9"})
        response=self.client.get(self.url("project"),
            base_url=ORIGIN,headers=headers)
        self.assertEqual(response.status_code,200)
        self.assertIn("stages",response.json)
        self.assertEqual(self.ensured,[])

    def test_bad_filename_and_empty_media_do_not_start_engine(self):
        for data,name in [(b"","cam.mp4"),(b"video","../../a.mp4"),
                          (b"video","malware.exe")]:
            with self.subTest(name=name):
                headers=dict(self.headers,**{"X-Zucker-Filename":name})
                res=self.post("wizard/upload",data,headers,
                              "application/octet-stream")
                self.assertEqual(res.status_code,400)
        self.assertEqual(self.ensured,[])


if __name__=="__main__":
    unittest.main()
