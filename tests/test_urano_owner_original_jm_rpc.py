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

    def test_real_proxy_bytes_and_original_jm_followup(self):
        video=b"proxy-video-bytes"*7000
        headers=dict(self.headers,**{"X-Zucker-Filename":"camera.small.mp4"})
        upload=self.post("wizard/upload",video,headers,
                         "application/octet-stream")
        self.assertEqual(upload.status_code,200)
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
