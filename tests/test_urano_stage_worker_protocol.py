"""U20 real worker JSONL dispatcher with fake Engine HTTP client.

Actual Engine Ingest (with media) is separately gated in disposable Docker CI.
"""
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from urano.engine_worker_process import run


class Response:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._json = body
    def get_json(self):
        return self._json


class EngineClient:
    def __init__(self, project_folder, *, accept=True):
        self.active = SimpleNamespace(project=SimpleNamespace(folder=None))
        self.application = SimpleNamespace(config={"ZUCKER_STATE":self.active})
        self.folder = project_folder
        self.accept = accept
        self.stage = "pending"
        self.count = 0
    def post(self, endpoint, json=None):
        if endpoint=="/api/v1/wizard/projects/open":
            self.active.project.folder = str(self.folder)
            return Response(200,{})
        if endpoint=="/api/v1/stages/ingest/run":
            if not self.accept: return Response(400,{"error":"/Users/private/path"})
            self.stage="running"
            return Response(202,{})
        raise AssertionError("Unapproved Engine endpoint")
    def get(self,endpoint):
        assert endpoint=="/api/v1/project"
        if self.stage=="running":
            self.count += 1
            if self.count >= 2:self.stage="done"
        return Response(200,{"stages":{"ingest":{"status":self.stage,
                                                  "error":"/Users/private.mp4"}}})


class WorkerStageProtocol(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.folder=self.root/"Projects"/"A"
        self.folder.mkdir(parents=True)
        (self.folder/"project.json").write_text("{}")

    def execute(self,commands,accept=True):
        stdout=io.StringIO()
        engine=EngineClient(self.folder,accept=accept)
        stdin=io.StringIO("".join(json.dumps(x)+"\n" for x in commands))
        run(stdin,stdout,engine_dir=self.root,data_root=self.root,
            make_client=lambda *_:engine)
        return [json.loads(line) for line in stdout.getvalue().splitlines()]

    def test_open_ingest_start_status_complete(self):
        responses=self.execute([
            {"op":"open","folder":"A"},
            {"op":"ingest_start"},
            {"op":"ingest_status"},
            {"op":"ingest_status"},
            {"op":"stop"}])
        self.assertEqual(responses[1],{"ok":True,"type":"opened","folder":"A"})
        self.assertEqual(responses[2],{"ok":True,"type":"ingest_started"})
        self.assertEqual(responses[3]["status"],"running")
        self.assertEqual(responses[4]["status"],"done")

    def test_no_paths_or_arguments_in_stage_and_fail_closed(self):
        responses=self.execute([
            {"op":"ingest_start"},
            {"op":"open","folder":"A"},
            {"op":"ingest_start","path":"/Users/private.mp4"},
            {"op":"ingest_start"},
            {"op":"stop"}],accept=False)
        self.assertEqual(responses[1]["ok"],False)
        self.assertEqual(responses[3]["ok"],False)
        self.assertEqual(responses[4],{"ok":False,"type":"ingest_start_rejected","http_status":400})
        self.assertNotIn("/Users",json.dumps(responses))

    def test_stale_project_folder_cannot_run_ingest(self):
        responses=self.execute([
            {"op":"open","folder":".."},
            {"op":"ingest_status"},
            {"op":"stop"}])
        self.assertFalse(responses[1]["ok"])
        self.assertFalse(responses[2]["ok"])


if __name__=="__main__":
    unittest.main()
