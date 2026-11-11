"""I32 private Engine read-only Stage snapshot, with fake in-process Engine.

No network, systemd, subprocess, real user data, media or deployed services.
"""
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from urano.engine_worker_process import run


PROJECT = "6c894f7c-6d97-44f3-8520-f78fa942b310"


class FakeResponse:
    def __init__(self, status_code, data=None):
        self.status_code = status_code
        self.data = data

    def get_json(self):
        return self.data


class FakeEngine:
    def __init__(self, root, *, change_folder=False):
        self.root = root
        self.change_folder = change_folder
        self.application = SimpleNamespace(config={
            "ZUCKER_STATE": SimpleNamespace(project=SimpleNamespace(folder=None))
        })
        self.visits = []

    def post(self, url, json=None):
        self.visits.append(("POST", url))
        if url != "/api/v1/wizard/projects/open":
            return FakeResponse(404)
        self.application.config["ZUCKER_STATE"].project.folder = json["path"]
        return FakeResponse(200)

    def get(self, url):
        self.visits.append(("GET", url))
        if url != "/api/v1/project":
            return FakeResponse(404)
        if self.change_folder:
            self.application.config["ZUCKER_STATE"].project.folder = str(self.root / "Projects" / "wrong")
        return FakeResponse(200, {
            "stages": {
                "ingest": {"status": "done"},
                "sync": {"status": "running"},
                "cut": {"status": "pending"},
                "edit": {"status": "pending"},
                "export": {"status": "not_started"},
            },
            "inputs": {
                "videos": [
                    {"path": "/PRIVATE/alice-secret-video.mp4", "size": 900000},
                    {"path": "/PRIVATE/another-secret-video.mov"},
                ]
            },
            "private_access_token": "NEVER RETURN",
        })


class StageSnapshotWorkerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        folder = self.root / "Projects" / PROJECT
        folder.mkdir(parents=True)
        (folder / "project.json").write_text("{}", encoding="utf-8")

    def execute(self, commands, *, change_folder=False):
        engine = FakeEngine(self.root, change_folder=change_folder)
        stdin = io.StringIO("".join(json.dumps(command) + "\n" for command in commands))
        stdout = io.StringIO()
        run(stdin, stdout, engine_dir=self.root, data_root=self.root,
            make_client=lambda engine_dir, root: engine)
        rows = [json.loads(line) for line in stdout.getvalue().splitlines()]
        return rows, engine

    def test_snapshot_is_private_redacted_and_statuses_are_real(self):
        rows, engine = self.execute([
            {"op": "open", "folder": PROJECT},
            {"op": "stage_snapshot"},
            {"op": "stop"},
        ])
        self.assertEqual(rows[1], {"ok": True, "type": "opened", "folder": PROJECT})
        status = rows[2]
        self.assertEqual(status, {
            "ok": True, "type": "stage_snapshot", "project": PROJECT,
            "camera_count": 2,
            "stages": {
                "ingest": "done", "sync": "running", "cut": "pending",
                "edit": "pending", "export": "not_started",
            },
        })
        self.assertEqual(rows[3], {"ok": True, "type": "stopped"})
        rendered = json.dumps(rows)
        self.assertNotIn("PRIVATE", rendered)
        self.assertNotIn("NEVER RETURN", rendered)
        self.assertNotIn(str(self.root), rendered)
        self.assertEqual(engine.visits[-1], ("GET", "/api/v1/project"))

    def test_snapshot_requires_opened_project(self):
        rows, engine = self.execute([{"op": "stage_snapshot"}, {"op": "stop"}])
        self.assertEqual(rows[1], {"ok": False, "error": "Invalid worker command"})
        self.assertEqual(engine.visits, [])

    def test_snapshot_rejects_arbitrary_parameters(self):
        rows, _ = self.execute([
            {"op": "open", "folder": PROJECT},
            {"op": "stage_snapshot", "project": "other", "path": "/etc/passwd"},
            {"op": "stop"},
        ])
        self.assertEqual(rows[2], {"ok": False, "error": "Invalid worker command"})

    def test_snapshot_rejects_drifted_engine_project(self):
        rows, _ = self.execute([
            {"op": "open", "folder": PROJECT},
            {"op": "stage_snapshot"},
            {"op": "stop"},
        ], change_folder=True)
        # Opening is deliberately rejected if the Engine's active folder drifts.
        self.assertNotEqual(rows[1].get("type"), "opened")
        self.assertNotEqual(rows[2].get("type"), "stage_snapshot")


if __name__ == "__main__":
    unittest.main()
