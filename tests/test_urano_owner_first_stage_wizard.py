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
        uploads = self.folder.parent.parent / "WizardUploads"
        uploads.mkdir()
        self.proxy = uploads / "proxy-0.mp4"
        self.proxy.write_bytes(b"synthetic-proxy")

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

        for operation in ("prepare", "start"):
            def handler(op=operation):
                body=request.get_json()
                self.calls.append((op,body))
                return jsonify(ok=True,project_id=body.get("project_id"))
            app.add_url_rule("/api/v1/wizard/"+operation,
                             endpoint="mock_"+operation,
                             view_func=handler,methods=["POST"])

        @app.post("/api/v1/settings/fillers")
        def original_fillers():
            body=request.get_json()
            self.calls.append(("fillers",body))
            return jsonify(ok=True)

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
            "project_id": None, "videos": [str(self.proxy)], **kwargs,
        })

    def test_original_new_and_first_draft_stay_on_same_owner_uuid(self):
        self.assertEqual(self.new().status_code, 200)
        self.assertIsNotNone(self.app.config["ZUCKER_STATE"].project)
        result = self.draft()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["project_id"], str(self.folder))
        self.assertEqual(self.calls[0][0], "draft")
        self.assertEqual(self.calls[0][1]["project_id"], str(self.folder))
        self.assertEqual(self.current.data["inputs"]["videos"], [str(self.proxy)])

    def test_saved_project_can_resume_but_not_be_silently_replaced(self):
        self.new()
        self.assertEqual(self.draft().status_code, 200)
        self.assertEqual(self.new().status_code, 409)
        self.assertEqual(self.draft().status_code, 400)
        resumed = self.client.post("/api/v1/wizard/draft", json={
            "name": "Stage", "platform": "youtube",
            "project_id": str(self.folder), "videos": [str(self.proxy)],
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

    def test_rejects_external_video_and_unfinished_resumable_upload(self):
        self.new()
        foreign = self.folder.parent.parent.parent / "outside.mp4"
        foreign.write_bytes(b"private-original")
        self.assertEqual(self.draft(videos=[str(foreign)]).status_code, 400)
        upload = self.folder.parent.parent / "Uploads" / ("a" * 32)
        upload.mkdir(parents=True)
        media = upload / "proxy.small.mp4"
        media.write_bytes(b"partial")
        (upload / "upload.json").write_text(
            '{"name":"proxy.small.mp4","complete":false}')
        self.assertEqual(self.draft(videos=[str(media)]).status_code, 400)
        (upload / "upload.json").write_text(
            '{"name":"proxy.small.mp4","complete":true}')
        self.assertEqual(self.draft(videos=[str(media)]).status_code, 200)

    def test_no_audio_field_can_escape_verified_owner_uploads(self):
        self.new()
        foreign=self.folder.parent.parent.parent/"foreign-master.wav"
        foreign.write_bytes(b"private-audio")
        for field in (
            {"master":str(foreign)},
            {"songs":str(foreign)},
            {"audio_paths":[str(foreign)]},
            {"audio_paths":str(self.proxy)},
            {"audio_paths":[str(self.proxy),str(foreign)]},
        ):
            with self.subTest(field=field):
                self.assertEqual(self.draft(**field).status_code,400)
        self.assertEqual(self.calls,[])
        self.assertEqual(self.draft(master=str(self.proxy),
                                    audio_paths=[str(self.proxy)]).status_code,200)

    def test_stage_continue_uses_only_registered_owner_inputs(self):
        self.new()
        self.assertEqual(self.draft().status_code,200)
        self.current.data["inputs"]["videos"]=[{"path":str(self.proxy)}]
        body={"platform":"youtube","project_id":str(self.folder),
              "name":"Stage","videos":[str(self.proxy)],"master":""}
        prepared=self.client.post("/api/v1/wizard/prepare",json=body)
        self.assertEqual(prepared.status_code,200)
        started=self.client.post("/api/v1/wizard/start",json=body)
        self.assertEqual(started.status_code,200)
        self.assertEqual(self.calls[-2][0],"prepare")
        self.assertEqual(self.calls[-1][0],"start")
        self.assertEqual(self.calls[-1][1]["project_id"],str(self.folder))

    def test_stage_continue_and_filler_cannot_reopen_foreign_media(self):
        self.new()
        self.assertEqual(self.draft().status_code,200)
        self.current.data["inputs"]["videos"]=[{"path":str(self.proxy)}]
        foreign=self.folder.parent.parent.parent/"outside.mp4"
        foreign.write_bytes(b"private-original")
        valid={"platform":"youtube","project_id":str(self.folder),
               "videos":[str(self.proxy)],"master":""}
        before=len(self.calls)
        for route,body in (
            ("wizard/prepare",{**valid,"videos":[str(foreign)]}),
            ("wizard/start",{**valid,"videos":[str(foreign)]}),
            ("wizard/start",{**valid,"project_id":"/other/owner"}),
            ("wizard/start",{**valid,"platform":"show"}),
            ("wizard/prepare",{**valid,"spherical_source_path":str(foreign)}),
            ("settings/fillers",{"fillers":[str(foreign)]}),
            ("settings/fillers",{"cutaways":[str(foreign)]}),
        ):
            with self.subTest(route=route,body=body):
                result=self.client.post("/api/v1/"+route,json=body)
                self.assertEqual(result.status_code,400)
        self.assertEqual(len(self.calls),before)
        self.assertEqual(self.client.post("/api/v1/settings/fillers",
                                         json={"fillers":[str(self.proxy)],
                                               "cutaways":[]}).status_code,200)

    def test_no_private_data_leaked_on_error(self):
        self.current.data["inputs"]["videos"] = ["private-original.mp4"]
        reply = self.new()
        self.assertEqual(reply.status_code, 409)
        self.assertNotIn(str(self.folder), reply.get_data(as_text=True))
        self.assertNotIn("private-original.mp4", reply.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
