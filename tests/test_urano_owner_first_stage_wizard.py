"""I42 original JM Stage wizard keeps Owner UUID without changing Chema's UI."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, jsonify, request
from werkzeug.test import Client
from werkzeug.wrappers import Response

from urano.owner_first_stage_wizard import OwnerFirstStageWizard


PROJECT = "7b8f5fd6-02b4-4cd0-8d16-c2d6d606a505"


class OwnerFirstWizardContracts(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.folder = Path(t.name) / "Projects" / PROJECT
        self.folder.mkdir(parents=True)
        (self.folder / "project.json").write_text("{}")
        self.current = SimpleNamespace(
            folder=self.folder,
            data={
                "inputs": {"master": None, "songs": None, "videos": []},
                "stages": {"ingest": {"status": "pending"}},
                "settings": {},
            },
        )
        self.calls = []
        app = Flask("jm-first-wizard")
        app.config["ZUCKER_STATE"] = SimpleNamespace(project=self.current)

        @app.post("/api/v1/wizard/projects/new")
        def original_new():
            self.calls.append(("unexpected new", None))
            app.config["ZUCKER_STATE"].project = None
            return jsonify(ok=True)

        @app.post("/api/v1/wizard/draft")
        def original_draft():
            body = request.get_json()
            self.calls.append(("draft", body.copy()))
            if body.get("project_id") != str(self.folder):
                return jsonify(error="wrong project"), 409
            self.current.data["inputs"]["videos"] = body["videos"]
            return jsonify(project_id=str(self.folder))

        self.app = app
        self.client = Client(
            OwnerFirstStageWizard(app, owner_project_folder=self.folder),
            Response,
        )

    def new(self):
        return self.client.post("/api/v1/wizard/projects/new", json={})

    def draft(self, **kwargs):
        return self.client.post("/api/v1/wizard/draft", json={
            "name": "Stage", "platform": "youtube",
            "project_id": None, "videos": ["proxy-0.mp4"], **kwargs,
        })

    def test_original_new_and_first_draft_stay_on_same_owner_uuid(self):
        self.assertEqual(self.new().status_code, 200)
        self.assertIsNotNone(self.app.config["ZUCKER_STATE"].project)
        result = self.draft()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["project_id"], str(self.folder))
        self.assertEqual(self.calls[0][0], "draft")
        self.assertEqual(self.calls[0][1]["project_id"], str(self.folder))
        self.assertEqual(self.current.data["inputs"]["videos"], ["proxy-0.mp4"])

    def test_saved_project_can_resume_but_not_be_silently_replaced(self):
        self.new()
        self.assertEqual(self.draft().status_code, 200)
        self.assertEqual(self.new().status_code, 409)
        self.assertEqual(self.draft().status_code, 400)
        resumed = self.client.post("/api/v1/wizard/draft", json={
            "name": "Stage", "platform": "youtube",
            "project_id": str(self.folder), "videos": ["proxy-0.mp4"],
        })
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual(len(self.calls), 2)

    def test_wrong_project_mode_and_unopened_engine_denied(self):
        self.new()
        self.assertEqual(self.draft(project_id="/other/user/project").status_code, 400)
        self.assertEqual(self.draft(platform="show").status_code, 400)
        self.app.config["ZUCKER_STATE"].project = None
        self.assertEqual(self.draft().status_code, 409)
        self.assertEqual(self.calls, [])

    def test_no_private_data_leaked_on_error(self):
        self.current.data["inputs"]["videos"] = ["private-original.mp4"]
        reply = self.new()
        self.assertEqual(reply.status_code, 409)
        self.assertNotIn(str(self.folder), reply.get_data(as_text=True))
        self.assertNotIn("private-original.mp4", reply.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
