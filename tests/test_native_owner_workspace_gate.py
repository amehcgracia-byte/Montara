"""Production-shaped WSGI route tests against Chema's original Latest handler.

These are isolated temp-owner directories: no GCP/Cloudflare, no uploads
of originals, and no synthetic replacement of Chema's recovery algorithm.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from flask import Flask, jsonify, request
from recovery import register_recovery

from urano.native_owner_workspace_gate import (
    NativeOwnerWorkspaceGate,
    UntrustedNativeWorkspace,
    verified_private_media,
)


class NativeOwnerWorkspaceRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="montara-owner-ux-")
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.owner_a, self.owner_b = base / "owner-a", base / "owner-b"
        for root in (self.owner_a, self.owner_b):
            root.mkdir(mode=0o700)
            (root / "Projects").mkdir()
            (root / "WizardUploads").mkdir()
            (root / "Uploads").mkdir()
            (root / "Sessions").mkdir()
        self.a_old = self.project(self.owner_a, "old.zuckervid", "Old", saved=True)
        self.b_private = self.project(self.owner_b, "private.zuckervid", "Foreign", saved=True)
        self.a_video = self.owner_a / "WizardUploads" / "camera.mp4"
        self.a_video.write_bytes(b"video-stream")
        self.a_audio = self.owner_a / "WizardUploads" / "microphone.wav"
        self.a_audio.write_bytes(b"audio-stream")
        self.b_video = self.owner_b / "WizardUploads" / "foreign.mp4"
        self.b_video.write_bytes(b"private-stream")
        self.received = []
        app = Flask(__name__)
        register_recovery(app, self.owner_a)

        @app.post("/api/v1/wizard/projects/new")
        def new():
            self.received.append(("new", request.get_json(silent=True)))
            return jsonify(ok=True)

        @app.post("/api/v1/wizard/draft")
        def draft():
            body = request.get_json()
            self.received.append(("draft", body))
            target = self.project(self.owner_a, "new.zuckervid", "New", saved=True)
            return jsonify(project_id=str(target))

        @app.post("/api/v1/wizard/prepare")
        def prepare():
            self.received.append(("prepare", request.get_json()))
            return jsonify(ok=True)

        @app.post("/api/v1/wizard/projects/open")
        def open_():
            self.received.append(("open", request.get_json()))
            return jsonify(ok=True)

        @app.post("/api/v1/wizard/projects/delete")
        def delete():
            self.received.append(("delete", request.get_json()))
            return jsonify(ok=True)

        @app.get("/api/v1/wizard/status")
        def status():
            self.received.append(("status", request.args.get("project_id")))
            return jsonify(status="idle")

        app.wsgi_app = NativeOwnerWorkspaceGate(app.wsgi_app,
                                                data_root=self.owner_a)
        self.client = app.test_client()

    @staticmethod
    def project(root: Path, folder_name: str, title: str, *, saved=False) -> Path:
        folder = root / "Projects" / folder_name
        folder.mkdir()
        (folder / "project.json").write_text(json.dumps({
            "name": title, "inputs": {"videos": [{"path": "camera.mp4"}] if saved else []}
        }))
        return folder

    def test_original_chema_latest_and_new_leave_saved_project_intact(self):
        latest = self.client.get("/montara/recovery/latest")
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.json["kind"], "project")
        self.assertEqual(latest.json["path"], str(self.a_old))
        self.assertEqual(self.client.post("/api/v1/wizard/projects/new",
                                          json={}).status_code, 200)
        self.assertTrue((self.a_old / "project.json").exists())
        draft = self.client.post("/api/v1/wizard/draft", json={
            "name": "New", "platform": "youtube", "project_id": None,
            "videos": [str(self.a_video)], "master": str(self.a_audio),
        })
        self.assertEqual(draft.status_code, 200, draft.get_json())
        self.assertEqual(draft.json["project_id"], str(self.owner_a /
                         "Projects" / "new.zuckervid"))
        self.assertTrue(self.a_old.exists())
        self.assertEqual(self.client.get("/montara/recovery/latest").status_code, 200)
        self.assertEqual(len([x for x in self.received if x[0] == "new"]), 1)
        self.assertEqual(len([x for x in self.received if x[0] == "draft"]), 1)

    def test_cross_owner_open_delete_and_status_are_denied_before_chema(self):
        for route in ("open", "delete"):
            before=len(self.received)
            response=self.client.post("/api/v1/wizard/projects/"+route,
                                      json={"path":str(self.b_private)})
            self.assertEqual(response.status_code, 403)
            self.assertEqual(len(self.received),before)
            self.assertNotIn(str(self.owner_b),response.get_data(as_text=True))
        foreign_status=self.client.get("/api/v1/wizard/status",
                            query_string={"project_id": str(self.b_private)})
        self.assertEqual(foreign_status.status_code,403)

    def test_legitimate_native_open_and_status_are_unchanged(self):
        response=self.client.post("/api/v1/wizard/projects/open",
                                  json={"path":str(self.a_old)})
        self.assertEqual(response.status_code,200)
        status=self.client.get("/api/v1/wizard/status",
                          query_string={"project_id":str(self.a_old)})
        self.assertEqual(status.status_code,200)
        self.assertEqual(self.received[-1],("status",str(self.a_old)))

    def test_outside_owner_media_and_symlinks_are_denied_before_native(self):
        outside = self.owner_a / "WizardUploads" / "foreign.mp4"
        outside.symlink_to(self.b_video)
        for path in (str(self.b_video),str(outside),
                     str(self.a_video) + "/../camera.mp4", "/etc/passwd"):
            with self.subTest(path=path):
                before=len(self.received)
                result=self.client.post("/api/v1/wizard/draft",json={
                    "name":"Untrusted","platform":"youtube","project_id":None,
                    "videos":[path],"master":str(self.a_audio),
                })
                self.assertEqual(result.status_code,403)
                self.assertEqual(len(self.received),before)

    def test_wrong_owner_project_id_blocked_even_with_own_uploads(self):
        response=self.client.post("/api/v1/wizard/draft",json={
            "project_id":str(self.b_private),"platform":"youtube",
            "videos":[str(self.a_video)],"master":str(self.a_audio)})
        self.assertEqual(response.status_code,403)

    def test_prepare_requires_a_saved_private_project(self):
        base={"platform":"youtube","videos":[str(self.a_video)],
              "master":str(self.a_audio)}
        self.assertEqual(self.client.post("/api/v1/wizard/prepare",
                         json=base).status_code,403)
        self.assertEqual(self.client.post("/api/v1/wizard/prepare",
                         json={**base,"project_id":str(self.a_old)}).status_code,200)

    def test_upload_metadata_must_confirm_complete_owner_file(self):
        upload = self.owner_a / "Uploads" / ("e"*32)
        upload.mkdir()
        file=upload / "proxy.mp4"
        file.write_bytes(b"proxy")
        metadata=upload/"upload.json"
        with self.assertRaises(UntrustedNativeWorkspace):
            verified_private_media(self.owner_a,str(file))
        metadata.write_text(json.dumps({"complete": True, "name": "proxy.mp4"}))
        self.assertEqual(verified_private_media(self.owner_a,str(file)),file)
        metadata.write_text(json.dumps({"complete": False, "name":"proxy.mp4"}))
        with self.assertRaises(UntrustedNativeWorkspace):
            verified_private_media(self.owner_a,str(file))

    def test_private_session_generated_audio_and_foreign_session_rejected(self):
        session=self.owner_a/"Sessions"/("f"*12)
        session.mkdir()
        (session/"session.json").write_text(json.dumps({"id":"f"*12}))
        guide=session/"guide.wav"
        guide.write_bytes(b"internal-audio")
        self.assertEqual(verified_private_media(self.owner_a,str(guide)),guide)
        self.assertEqual(self.client.post("/api/v1/wizard/draft",json={
            "project_id":None,"videos":[str(self.a_video)],"master":str(guide),
        }).status_code,200)
        with self.assertRaises(UntrustedNativeWorkspace):
            verified_private_media(self.owner_b,str(guide))

    def test_new_cannot_select_foreign_project_as_side_effect(self):
        response=self.client.post("/api/v1/wizard/projects/new",json={
            "path":str(self.b_private)})
        self.assertEqual(response.status_code,403)
        self.assertFalse(self.received)

    def test_denied_request_does_not_poison_next_native_request(self):
        self.client.post("/api/v1/wizard/projects/open",json={
            "path":str(self.b_private)})
        self.assertEqual(self.client.post("/api/v1/wizard/projects/new",
                                          json={}).status_code,200)

    def test_denies_untrusted_workspace_root_permission(self):
        os.chmod(self.owner_a,0o755)
        try:
            with self.assertRaises(UntrustedNativeWorkspace):
                NativeOwnerWorkspaceGate(lambda e,s: [],data_root=self.owner_a)
        finally:
            os.chmod(self.owner_a,0o700)


if __name__=="__main__":
    unittest.main()
