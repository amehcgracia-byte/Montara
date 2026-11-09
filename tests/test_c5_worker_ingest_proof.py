"""C5 private worker emits only verified hashes from its own Stage project.

The test runs the real JSONL dispatcher with a synthetic Engine API client,
not Docker; two Docker workers have a separate CI acceptance test.
"""
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from test_urano_stage_worker_protocol import EngineClient, Response
from urano.engine_worker_process import run


class SyntheticStageProofEngine(EngineClient):
    def __init__(self, project_folder: Path, *, source: Path, normalized: Path,
                 status: str = "done"):
        super().__init__(project_folder)
        self.source, self.normalized, self.stage = source, normalized, status

    def get(self, endpoint):
        assert endpoint == "/api/v1/project"
        return Response(200, {
            "stages": {"ingest": {"status": self.stage}},
            "inputs": {"videos": [{
                "path": str(self.source),
                "normalized": {"path": str(self.normalized)}
            }]}
        })


class StageHashProofContract(unittest.TestCase):
    def setUp(self):
        scope = tempfile.TemporaryDirectory(prefix="montara-c5-worker-proof-")
        self.addCleanup(scope.cleanup)
        self.root = Path(scope.name)
        self.project = self.root / "Projects" / "OwnerA"
        self.project.mkdir(parents=True)
        (self.project / "project.json").write_text("{}")
        directory = self.project / "inputs" / "urano-staged-proxies"
        directory.mkdir(parents=True)
        self.original = b"owner-private-proxy"*600
        digest = hashlib.sha256(self.original).hexdigest()
        self.source = directory / f"camera-0-{digest}.mp4"
        self.source.write_bytes(self.original)
        self.normalized = self.root / "Cache" / "normalized.mp4"
        self.normalized.parent.mkdir()
        self.normalized.write_bytes(b"Stage normalized media differs"*300)

    def execute(self, *, stage="done", source=None, normalized=None, commands=None):
        engine = SyntheticStageProofEngine(
            self.project,source=source or self.source,
            normalized=normalized or self.normalized,status=stage)
        wire = io.StringIO()
        commands = commands or [
            {"op":"open","folder":"OwnerA"},{"op":"ingest_proof"},{"op":"stop"}
        ]
        run(io.StringIO("".join(json.dumps(x)+"\n" for x in commands)),
            wire,engine_dir=self.root,data_root=self.root,
            make_client=lambda *_:engine)
        return [json.loads(s) for s in wire.getvalue().splitlines()]

    def test_fixed_private_proof_has_only_camera_slots_and_hashes(self):
        messages = self.execute()
        self.assertEqual(messages[2]["type"],"ingest_proof")
        self.assertEqual(messages[2]["sources"], [{
            "slot":0,
            "proxy_sha256":hashlib.sha256(self.original).hexdigest(),
            "normalized_sha256":hashlib.sha256(
                self.normalized.read_bytes()).hexdigest()}])
        self.assertNotIn(str(self.root),json.dumps(messages))
        self.assertNotIn("path",json.dumps(messages[2]))

    def test_stage_not_done_or_media_changed_fails_closed(self):
        self.assertFalse(self.execute(stage="running")[2]["ok"])
        self.source.write_bytes(b"changed after registration")
        self.assertFalse(self.execute()[2]["ok"])

    def test_injection_and_cross_project_or_cache_sources_rejected(self):
        self.assertFalse(self.execute(commands=[
            {"op":"ingest_proof"},{"op":"stop"}])[1]["ok"])
        self.assertFalse(self.execute(commands=[
            {"op":"open","folder":"OwnerA"},
            {"op":"ingest_proof","path":"/tmp/foreign.mp4"},
            {"op":"stop"}])[2]["ok"])
        other=self.root/"Projects"/"Foreign"/"camera.mp4"
        other.parent.mkdir()
        other.write_bytes(self.original)
        self.assertFalse(self.execute(source=other)[2]["ok"])
        with tempfile.TemporaryDirectory(prefix="outside-owner-") as outside:
            foreign=Path(outside)/"normalized.mp4"
            foreign.write_bytes(b"video")
            self.assertFalse(self.execute(normalized=foreign)[2]["ok"])


if __name__=="__main__":
    unittest.main()
