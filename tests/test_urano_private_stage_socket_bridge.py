"""I34: broker ledger -> real AF_UNIX -> fake isolated Engine snapshot.

Only one actual local Unix socket: no deployed services, root or media.
"""
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from urano.job_recovery_ledger import JobRecoveryLedger
from urano.project_catalog import ProjectCatalog
from urano.private_stage_payload import private_stage_snapshot
from urano.private_stage_snapshot_bridge import trusted_stage_snapshot
from urano.private_stage_unix_transport import (
    SystemdUnixStageTransport, serve_stage_socket, SOCKET_NAME,
)
from urano.private_engine_route_contract import PrivateEngineRouteDenied
from urano.restricted_systemd_broker import expected_cgroup


ENGINE = "a" * 40


class FakeResponse:
    status_code = 200

    def get_json(self):
        return {
            "stages": {"ingest": {"status": "done"},
                       "sync": {"status": "running"}},
            "inputs": {"videos": [
                {"path": "/home/someone/secret.mov"},
                {"path": "/private/other.mp4"},
            ]},
            "credentials": "must-never-exit-the-worker",
        }


class FakeEngine:
    def __init__(self, folder):
        self.application = SimpleNamespace(config={
            "ZUCKER_STATE": SimpleNamespace(
                project=SimpleNamespace(folder=folder)
            )
        })

    def get(self, route):
        if route != "/api/v1/project":
            raise AssertionError("Unapproved Engine route")
        return FakeResponse()


class ActualSocketBridgeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.catalog = ProjectCatalog(self.root / "projects.sqlite3")
        self.ledger = JobRecoveryLedger(self.root / "jobs.sqlite3")
        self.project = self.catalog.create(
            "owner-a", "A Stage",
            recipe={"montara_beta_workspace": {"mode": "stage"}},
        )
        self.foreign = self.catalog.create(
            "owner-b", "B Stage",
            recipe={"montara_beta_workspace": {"mode": "stage"}},
        )
        self.lease = self.ledger.start_trusted("owner-a", self.project.id)
        self.unit = self.ledger.reserve_target_unit(self.lease)
        self.lease = self.ledger.mark_running(self.lease)
        self.folder = self.root / self.unit / "Projects" / self.project.id
        self.folder.mkdir(parents=True, exist_ok=True)
        engine = FakeEngine(self.folder)
        self.calls = 0

        def snapshot():
            self.calls += 1
            return private_stage_snapshot(engine, self.folder)

        self.worker = threading.Thread(
            target=serve_stage_socket,
            args=(self.folder.parent.parent,),
            kwargs={
                "project_id": self.project.id,
                "generation": self.lease.generation,
                "read_snapshot": snapshot,
                "trusted_broker_uid": os.getuid(),
                "max_requests": 1,
            },
            daemon=True,
        )
        self.worker.start()
        for _ in range(100):
            if (self.root / self.unit / SOCKET_NAME).exists():
                break
            time.sleep(0.01)
        else:
            self.fail("Local worker socket never started")
        self.transport = SystemdUnixStageTransport(
            lambda unit: {
                "ActiveState": "active",
                "ControlGroup": expected_cgroup(unit),
                "MainPID": str(os.getpid()),
            },
            runtime_root=self.root,
        )

    def test_full_broker_ledger_unix_worker_read_is_redacted(self):
        result = trusted_stage_snapshot(
            "owner-a", self.project.id, generation=self.lease.generation,
            catalog=self.catalog, ledger=self.ledger,
            engine_sha=ENGINE, transport=self.transport,
        )
        self.assertEqual(result["camera_count"], 2)
        self.assertEqual(result["stages"]["sync"], "running")
        self.assertNotIn("secret", str(result))
        self.assertNotIn("/private/", str(result))
        self.assertEqual(self.calls, 1)
        self.worker.join(timeout=2)
        self.assertFalse(self.worker.is_alive())

    def test_foreign_owner_rejected_before_socket_read(self):
        with self.assertRaises(PrivateEngineRouteDenied):
            trusted_stage_snapshot(
                "owner-b", self.project.id, generation=self.lease.generation,
                catalog=self.catalog, ledger=self.ledger,
                engine_sha=ENGINE, transport=self.transport,
            )
        self.assertEqual(self.calls, 0)
        # Cleanly let the synthetic worker complete its one permitted request.
        self.transport.stage_snapshot(
            self.unit, project_id=self.project.id,
            generation=self.lease.generation,
        )
        self.worker.join(timeout=2)
        self.assertFalse(self.worker.is_alive())


if __name__ == "__main__":
    unittest.main()
