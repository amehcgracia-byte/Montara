"""Native Stage status stays tied to the Owner workspace when Chema switches edits."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, jsonify

from urano.native_owner_stage_snapshot import native_owner_stage_snapshot


class NativeOwnerStageSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="montara-native-stage-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.root, self.foreign = root / "owner-a", root / "owner-b"
        for base in (self.root, self.foreign):
            (base / "Projects").mkdir(parents=True)
        self.app = Flask(__name__)
        self.state = SimpleNamespace(project=None)
        self.app.config["ZUCKER_STATE"] = self.state
        self.video_count = 2
        self.stage_status = "running"

        @self.app.get("/api/v1/project")
        def project():
            return jsonify(
                inputs={"videos": [{"path": f"camera{i}.mp4"}
                                   for i in range(self.video_count)]},
                stages={"ingest": {"status": self.stage_status}},
            )

    def create(self, root: Path, name: str):
        folder = root / "Projects" / name
        folder.mkdir()
        (folder / "project.json").write_text(
            json.dumps({"name": name, "inputs": {"videos": []}}))
        return folder

    def snapshot(self):
        return native_owner_stage_snapshot(
            self.app, data_root=self.root, workspace_id="stable-owner-workspace")

    def test_new_owner_without_edit_has_valid_idle_snapshot(self):
        result = self.snapshot()
        self.assertEqual(result["project"], "stable-owner-workspace")
        self.assertEqual(result["camera_count"], 0)
        self.assertEqual(set(result["stages"]), {"ingest","sync","cut","edit","export"})
        self.assertTrue(all(v == "not_started"
                            for v in result["stages"].values()))
        self.assertEqual(set(result), {
            "ok", "type", "project", "stages", "camera_count"})

    def test_native_new_edit_does_not_switch_broker_workspace(self):
        a = self.create(self.root, "old.zuckervid")
        b = self.create(self.root, "new.zuckervid")
        self.state.project = SimpleNamespace(folder=a)
        previous = self.snapshot()
        self.assertEqual(previous["camera_count"], 2)
        self.assertEqual(previous["stages"]["ingest"], "running")
        self.assertEqual(previous["stages"]["sync"], "not_started")
        self.state.project = SimpleNamespace(folder=None)
        self.assertEqual(self.snapshot()["camera_count"],0)
        self.state.project = SimpleNamespace(folder=b)
        current = self.snapshot()
        self.assertEqual(current["project"], previous["project"])
        self.assertEqual(current["camera_count"], 2)
        self.assertNotIn(str(self.root),json.dumps(current))

    def test_foreign_project_rejected_before_reading_status(self):
        foreign=self.create(self.foreign,"secret.zuckervid")
        self.state.project=SimpleNamespace(folder=foreign)
        with self.assertRaises(ValueError):
            self.snapshot()

    def test_untrusted_symlinked_project_rejected(self):
        folder=self.create(self.foreign,"escape.zuckervid")
        link=self.root/"Projects"/"linked.zuckervid"
        link.symlink_to(folder, target_is_directory=True)
        self.state.project=SimpleNamespace(folder=link)
        with self.assertRaises(ValueError):
            self.snapshot()

    def test_missing_or_unrecognized_engine_status_fails_closed(self):
        edit=self.create(self.root,"stage.zuckervid")
        self.state.project=SimpleNamespace(folder=edit)
        self.stage_status="developer_internal"
        with self.assertRaises(ValueError):
            self.snapshot()
        self.stage_status="done"
        self.video_count=201
        with self.assertRaises(ValueError):
            self.snapshot()

    def test_missing_trusted_engine_state_rejected(self):
        del self.app.config["ZUCKER_STATE"]
        with self.assertRaises(ValueError):
            self.snapshot()


if __name__=="__main__":
    unittest.main()
