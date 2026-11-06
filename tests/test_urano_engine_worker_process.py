"""U13C stdio protocol tests; no cloud, Engine or private user files."""
import io
import json
import tempfile
import unittest
from pathlib import Path

from urano.engine_worker_process import _project_folder, run


class FakeReply:
    def __init__(self, code=200, payload=None):
        self.status_code = code
        self.payload = payload or {}

    def get_json(self, silent=False):
        return self.payload


class FakeEngine:
    def __init__(self):
        self.active = None
        self.calls = []

    def post(self, route, json):
        self.calls.append(("post", route, json))
        if self.active == "locked":
            return FakeReply(409)
        self.active = json["path"]
        return FakeReply(200)

    def get(self, route):
        self.calls.append(("get", route))
        return FakeReply(200, {"folder": self.active})


class EngineWorkerProtocolTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.data = Path(td.name)
        (self.data / "Projects").mkdir()
        for name in ("Old", "New"):
            folder = self.data / "Projects" / name
            folder.mkdir()
            (folder / "project.json").write_text(json.dumps({"name": name}))
        self.fake = FakeEngine()

    def roundtrip(self, packets, client=None):
        stdin = io.StringIO("".join(json.dumps(p) + "\n" for p in packets))
        stdout = io.StringIO()
        run(stdin, stdout, engine_dir=self.data / "fake-engine",
            data_root=self.data, make_client=lambda _engine, _data: client or self.fake)
        return [json.loads(s) for s in stdout.getvalue().splitlines()]

    def test_real_open_route_and_verify_old_then_new(self):
        replies = self.roundtrip([{"op": "open", "folder": "Old"},
                                  {"op": "open", "folder": "New"}, {"op": "stop"}])
        self.assertEqual([r.get("type") for r in replies],
                         ["ready", "opened", "opened", "stopped"])
        self.assertEqual([r.get("folder") for r in replies[1:3]], ["Old", "New"])
        self.assertEqual(self.fake.calls[0][1], "/api/v1/wizard/projects/open")
        self.assertEqual(self.fake.calls[1][1], "/api/v1/project")
        self.assertNotEqual(self.fake.calls[0][2]["path"], self.fake.calls[2][2]["path"])

    def test_forged_paths_and_symlinks_do_not_reach_engine(self):
        outside = self.data / "external"
        outside.mkdir()
        (outside / "project.json").write_text("{}")
        (self.data / "Projects" / "alias").symlink_to(outside, target_is_directory=True)
        packets = [{"op": "open", "folder": x} for x in
                   ("../external", "/tmp", "alias", "Missing", "Old/project.json", "..")]
        replies = self.roundtrip(packets)
        self.assertEqual(len(replies), 1 + len(packets))
        self.assertTrue(all(not reply["ok"] for reply in replies[1:]))
        self.assertEqual(self.fake.calls, [])

    def test_engine_failure_and_mismatched_loaded_project_fail_closed(self):
        class WrongEngine(FakeEngine):
            def get(self, route):
                return FakeReply(200, {"folder": "/unrelated/project"})
        self.assertFalse(self.roundtrip([{"op": "open", "folder": "Old"}],
                                        WrongEngine())[1]["ok"])
        self.fake.active = "locked"
        self.assertEqual(self.roundtrip([{"op": "open", "folder": "Old"}])[1]["status"], 409)

    def test_invalid_commands_cannot_invoke_engine(self):
        replies = self.roundtrip([{"op": "delete", "folder": "Old"},
                                  {"op": "open", "folder": {"value": "Old"}}])
        self.assertTrue(all(not x["ok"] for x in replies[1:]))
        self.assertEqual(self.fake.calls, [])

    def test_engine_client_requires_pinned_submodule(self):
        from urano.engine_worker_process import make_engine_client
        with self.assertRaises(RuntimeError):
            make_engine_client(self.data / "missing-engine", self.data)


if __name__ == "__main__":
    unittest.main()
