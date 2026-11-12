"""Exercise Chema's native New/Latest lifecycle through the worker binding.

The factory here simulates only the original Flask engine's control side
effects, while /montara/recovery/latest is the REAL recovery.py unchanged.
No alternate Owner editor or routes are created in product code.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, jsonify, request
from recovery import register_recovery

from urano.native_owner_worker_binding import (
    NativeWorkerBindingError,
    bind_native_owner_application,
)

WORKSPACE_ID = "c78b8a03-e9c4-450c-8491-7ce8843957f3"


class NativeWorkerBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="montara-worker-binding-")
        self.addCleanup(self.temp.cleanup)
        home = Path(self.temp.name)
        self.root, self.other = home / "owner-a", home / "owner-b"
        for item in (self.root, self.other):
            item.mkdir(mode=0o700)
            (item / "Projects").mkdir()
            (item / "Sessions").mkdir()
            (item / "WizardUploads").mkdir()
        self.calls = []
        self.state = SimpleNamespace(project=None)

    @staticmethod
    def existing(root: Path, name: str) -> Path:
        folder = root / "Projects" / name
        folder.mkdir()
        (folder / "project.json").write_text(json.dumps({
            "name": name, "inputs": {"videos": [{"path": "cam.mp4"}]},
            "stages": {"ingest": {"status": "done"}}
        }))
        return folder

    def app_factory(self, root: Path, *, samples=False):
        self.calls.append((root,samples))
        app = Flask(__name__)
        app.config["ZUCKER_STATE"] = self.state
        register_recovery(app, root)

        @app.post("/api/v1/wizard/projects/new")
        def new():
            self.state.project = None
            return jsonify(ok=True)

        @app.post("/api/v1/wizard/projects/open")
        def open_():
            self.state.project = SimpleNamespace(
                folder=Path(request.get_json()["path"]))
            return jsonify(ok=True)

        @app.post("/api/v1/wizard/draft")
        def draft():
            entry = request.get_json()
            folder = root / "Projects" / (entry.get("name","New")+".zuckervid")
            folder.mkdir(exist_ok=False)
            (folder / "project.json").write_text(json.dumps({
                "name": entry.get("name","New"), "inputs": {
                    "videos": [{"path":path} for path in entry.get("videos",[])]},
                "stages": {"ingest": {"status": "pending"}},
            }))
            self.state.project = SimpleNamespace(folder=folder)
            return jsonify(project_id=str(folder))

        @app.get("/api/v1/project")
        def project():
            if not self.state.project:
                return jsonify(error="No active edit"),404
            p=Path(self.state.project.folder)
            return jsonify(json.loads((p/"project.json").read_text()))

        return app

    def bind(self):
        return bind_native_owner_application(
            app_factory=self.app_factory, data_root=self.root,
            workspace_id=WORKSPACE_ID)

    def test_no_synthetic_editor_project_is_created_during_boot(self):
        app,snapshot=self.bind()
        self.assertEqual(self.calls,[(self.root,False)])
        self.assertEqual(list((self.root/"Projects").iterdir()),[])
        self.assertIsNone(self.state.project)
        self.assertEqual(snapshot()["project"],WORKSPACE_ID)
        self.assertEqual(snapshot()["camera_count"],0)
        self.assertEqual(app.test_client().get("/montara/recovery/latest").status_code,404)

    def test_original_new_then_latest_then_resume_uses_same_workspace(self):
        old=self.existing(self.root,"Old.zuckervid")
        app,snapshot=self.bind()
        c=app.test_client()
        first=c.get("/montara/recovery/latest")
        self.assertEqual(first.status_code,200)
        self.assertEqual(first.json["path"],str(old))
        self.assertEqual(c.post("/api/v1/wizard/projects/open",
            json={"path":str(old)}).status_code,200)
        self.assertEqual(snapshot()["stages"]["ingest"],"done")
        self.assertEqual(c.post("/api/v1/wizard/projects/new",json={}).status_code,200)
        self.assertEqual(snapshot()["camera_count"],0)
        media=self.root/"WizardUploads"/"video.mp4"
        media.write_bytes(b"video-clip")
        result=c.post("/api/v1/wizard/draft",json={
            "name":"New","project_id":None,"videos":[str(media)],
            "platform":"youtube",
        })
        self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(snapshot()["project"],WORKSPACE_ID)
        self.assertTrue(old.exists())
        self.assertTrue((self.root/"Projects"/"New.zuckervid").exists())
        self.assertEqual(len(list((self.root/"Projects").iterdir())),2)

    def test_foreign_preopened_project_rejected_before_attaching_gateway(self):
        outsider=self.existing(self.other,"not-yours.zuckervid")
        self.state.project=SimpleNamespace(folder=outsider)
        with self.assertRaises(NativeWorkerBindingError):
            self.bind()

    def test_resumed_private_native_project_can_start_without_reopening(self):
        old=self.existing(self.root,"continued.zuckervid")
        self.state.project=SimpleNamespace(folder=old)
        app,snapshot=self.bind()
        self.assertEqual(snapshot()["stages"]["ingest"],"done")
        self.assertEqual(snapshot()["project"],WORKSPACE_ID)

    def test_invalid_workspace_id_and_world_readable_root_fail_closed(self):
        with self.assertRaises(NativeWorkerBindingError):
            bind_native_owner_application(app_factory=self.app_factory,
                data_root=self.root,workspace_id="invalid-workspace")
        self.assertFalse(self.calls)
        self.root.chmod(0o755)
        with self.assertRaises(NativeWorkerBindingError):
            self.bind()
        self.assertFalse(self.calls)
        self.root.chmod(0o700)


if __name__=="__main__":
    unittest.main()
