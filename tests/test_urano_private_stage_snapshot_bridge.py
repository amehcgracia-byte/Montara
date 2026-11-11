"""I33 provider-neutral broker-to-private-worker Stage snapshot contract tests.

Uses a real temporary owner catalog and job ledger but a fake trusted executor.
No root, HTTP, machine settings, live Engine or media.
"""
import tempfile
import unittest
from pathlib import Path

from urano.job_recovery_ledger import JobRecoveryLedger
from urano.project_catalog import ProjectCatalog
from urano.private_stage_snapshot_bridge import (
    PrivateEngineRouteDenied, trusted_stage_snapshot,
)


SHA = "a" * 40


class FakeTransport:
    def __init__(self):
        self.calls = []
        self.good = True
        self.response = None

    def attest(self, target, *, project_id, generation):
        self.calls.append(("attest", target, project_id, generation))
        return self.good

    def stage_snapshot(self, target, *, project_id, generation):
        self.calls.append(("read", target, project_id, generation))
        return self.response or {
            "ok": True, "type": "stage_snapshot", "project": project_id,
            "camera_count": 2,
            "stages": {
                "ingest": "done", "sync": "running", "cut": "pending",
                "edit": "pending", "export": "not_started",
            },
        }


class BrokerPrivateStageSnapshotTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name)
        self.catalog = ProjectCatalog(root / "projects.sqlite3")
        self.ledger = JobRecoveryLedger(root / "jobs.sqlite3")
        self.owner = "owner-a"
        self.stage = self.catalog.create(
            self.owner, "Stage one",
            recipe={"montara_beta_workspace": {"mode": "stage", "version": 1}},
        )
        self.foreign = self.catalog.create(
            "owner-b", "Foreign",
            recipe={"montara_beta_workspace": {"mode": "stage", "version": 1}},
        )
        self.push = self.catalog.create(
            self.owner, "Push one",
            recipe={"montara_beta_workspace": {"mode": "push", "version": 1}},
        )
        self.job = self.ledger.start_trusted(self.owner, self.stage.id)
        self.target = self.ledger.reserve_target_unit(self.job)
        self.job = self.ledger.mark_running(self.job)
        self.transport = FakeTransport()

    def request(self, *, owner=None, project=None, generation=None, sha=SHA):
        return trusted_stage_snapshot(
            self.owner if owner is None else owner,
            self.stage.id if project is None else project,
            generation=self.job.generation if generation is None else generation,
            catalog=self.catalog, ledger=self.ledger,
            engine_sha=sha, transport=self.transport,
        )

    def denied(self, **kwargs):
        before = len(self.transport.calls)
        with self.assertRaises(PrivateEngineRouteDenied):
            self.request(**kwargs)
        self.assertEqual(len(self.transport.calls), before)

    def test_running_stage_returns_only_sanitized_status(self):
        result = self.request()
        self.assertEqual(result["project_id"], self.stage.id)
        self.assertEqual(result["camera_count"], 2)
        self.assertEqual(result["stages"]["sync"], "running")
        self.assertEqual([row[0] for row in self.transport.calls], ["attest", "read"])
        self.assertTrue(all(row[1] == self.target for row in self.transport.calls))
        self.assertNotIn("path", str(result))
        self.assertNotIn("unit", str(result))

    def test_other_owner_project_mode_or_generation_never_reaches_worker(self):
        self.denied(owner="owner-b")
        self.denied(project=self.foreign.id)
        self.denied(project=self.push.id)
        self.denied(generation=self.job.generation + 1)
        self.denied(generation=True)
        self.denied(sha="not-a-pinned-version")

    def test_failed_os_attestation_does_not_read(self):
        self.transport.good = False
        with self.assertRaises(PrivateEngineRouteDenied):
            self.request()
        self.assertEqual([row[0] for row in self.transport.calls], ["attest"])

    def test_stale_after_stop_is_fenced_without_contacting_worker(self):
        self.ledger.request_stop(self.job)
        self.denied()

    def test_worker_response_rejects_extra_fields_paths_or_wrong_identity(self):
        self.transport.response = {
            "ok": True, "type": "stage_snapshot", "project": self.stage.id,
            "camera_count": 1, "stages": {
                "ingest": "done", "sync": "running", "cut": "idle",
                "edit": "idle", "export": "not_started",
            },
            "secret_path": "/private/alice",
        }
        with self.assertRaises(PrivateEngineRouteDenied):
            self.request()
        self.transport.response.pop("secret_path")
        self.transport.response["project"] = self.foreign.id
        with self.assertRaises(PrivateEngineRouteDenied):
            self.request()
        self.transport.response["project"] = self.stage.id
        self.transport.response["camera_count"] = True
        with self.assertRaises(PrivateEngineRouteDenied):
            self.request()


if __name__ == "__main__":
    unittest.main()
