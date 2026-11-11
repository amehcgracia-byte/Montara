"""Stage Companion handoff: project alias stays private; master streams, no original proxy.

Run with the normal owner gateway and Werkzeug's real Unix HTTP socket.
"""
from __future__ import annotations
import io
import json
import socket
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path

from flask import Flask, jsonify, request, Response

from urano.owner_stage_native_export import OwnerStageNativeExport
from urano.owner_original_jm_rpc import initial_stage_gateway_blueprint
from urano.private_jm_wsgi_socket import create_private_jm_wsgi_server
from urano.project_catalog import ProjectCatalog
from urano.session_auth import SessionStore, SESSION_COOKIE

ORIGIN="https://montara.test"
REVISION="abcdef0123456789abcd"


class StageCompanionGateway(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root=Path(tmp.name)
        folder=root/"Data"/"Projects"/"7b8f5fd6-02b4-4cd0-8d16-c2d6d606a505"
        folder.mkdir(parents=True)
        (folder/"project.json").write_text("{}")
        self.folder=folder
        db=root/"Auth";db.mkdir(mode=0o700)
        catalog=ProjectCatalog(db/"projects.sqlite3")
        self.project=catalog.create("owner-a","Stage",recipe={
            "montara_beta_workspace":{"mode":"stage","version":1}})
        foreign=catalog.create("owner-b","Stage",recipe={
            "montara_beta_workspace":{"mode":"stage","version":1}})
        self.foreign=foreign
        sessions=SessionStore(db/"sessions.sqlite3")
        sess=sessions.issue("owner-a")
        app=Flask("actual-stage-native-JM")
        self.raw=bytes(range(256))*18000  # 4.6 MiB, above JSON cap.
        @app.get("/api/v1/edit/native-recipe")
        def recipe():
            assert request.args.get("project_id")==str(folder)
            return jsonify(engine="a"*40,revision="+REVISION+",platform="youtube",
                sources=[],segments=[])
        @app.get("/api/v1/edit/native-master")
        def audio():
            assert request.args.get("project_id")==str(folder)
            assert request.args.get("revision")=="2"
            return Response(self.raw,mimetype="audio/wav")
        @app.get("/api/v1/edit/native-source/0")
        def original():
            return Response(b"PRIVATE ORIGINAL",mimetype="video/mp4")
        work=root/"Runtime";work.mkdir(mode=0o700)
        self.server,self.sock=create_private_jm_wsgi_server(
            OwnerStageNativeExport(app,folder=folder),work)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self._stop)
        def connection(token,csrf,uuid,generation):
            if generation!=7 or uuid!=self.project.id:
                raise RuntimeError("Invalid generation")
            c=HTTPConnection("localhost",timeout=5)
            c.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
            c.sock.connect(str(self.sock))
            return c
        portal=Flask("Owner-Portal")
        portal.config["MAX_CONTENT_LENGTH"]=300_000
        portal.register_blueprint(initial_stage_gateway_blueprint(
            catalog,sessions,https_origin=ORIGIN,
            connect_worker=connection))
        self.client=portal.test_client()
        self.client.set_cookie(SESSION_COOKIE,sess.token,domain="montara.test")
        self.headers={
            "Origin":ORIGIN,"X-Urano-CSRF":sess.csrf,
            "X-Montara-Engine-Generation":"7"}
        self.url="/urano/v1/media/"+self.project.id+"/"
    def _stop(self):
        self.server.shutdown();self.server.server_close()
        self.thread.join(timeout=3)
        self.sock.unlink(missing_ok=True)

    def test_recipe_and_lossless_master_stream_to_companion(self):
        r=self.client.get(self.url+"edit/native-recipe?project_id=owner-worker",
                          base_url=ORIGIN,headers=self.headers)
        self.assertEqual(r.status_code,200,r.get_data(as_text=True)[:170])
        self.assertEqual(r.json["engine"],"a"*40)
        master=self.client.get(
            self.url+"edit/native-master?revision="+REVISION+"&project_id=owner-worker",
            base_url=ORIGIN,headers=self.headers)
        self.assertEqual(master.status_code,200,master.status)
        self.assertEqual(master.data,self.raw)
        self.assertEqual(master.headers["Content-Length"],str(len(self.raw)))
        self.assertEqual(master.headers["X-Content-Type-Options"],"nosniff")
        self.assertEqual(master.headers["X-Montara-Engine-Generation"],"7")

    def test_foreign_project_and_unapproved_paths_denied(self):
        result=self.client.get(
            "/urano/v1/media/"+self.foreign.id+
            "/edit/native-master?project_id=owner-worker&revision="+REVISION+"",
            base_url=ORIGIN,headers=self.headers)
        self.assertEqual(result.status_code,404)
        for suffix in (
            "edit/native-master?project_id=/tmp/other&revision="+REVISION+"",
            "edit/native-master?project_id=owner-worker&revision=../../",
            "edit/native-master?revision="+REVISION+"&project_id=owner-worker&path=/etc/passwd",
            "edit/native-recipe?project_id=owner-worker&path=/secret",
            "edit/native-source/0?revision="+REVISION+"&project_id=owner-worker",
        ):
            with self.subTest(suffix=suffix):
                result=self.client.get(self.url+suffix,base_url=ORIGIN,
                                       headers=self.headers)
                self.assertEqual(result.status_code,404)

    def test_no_untrusted_master_without_csrf(self):
        response=self.client.get(
            self.url+"edit/native-master?project_id=owner-worker&revision="+REVISION+"",
            base_url=ORIGIN,headers={"Origin":ORIGIN})
        self.assertEqual(response.status_code,403)


if __name__=="__main__":
    unittest.main()
