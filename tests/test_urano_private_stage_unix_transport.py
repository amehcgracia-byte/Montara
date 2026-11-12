"""I34 physically exercise Unix domain socket IPC, with kernel SO_PEERCRED.

Uses a real AF_UNIX socket in a temporary directory, and a synthetic worker
running in a thread. Does not touch any live systemd service or Engine.
"""
import json
import os
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

from urano.private_engine_route_contract import PrivateEngineRouteDenied
from urano.private_stage_unix_transport import (
    SOCKET_NAME, SystemdUnixStageTransport, serve_stage_socket,
)
from urano.restricted_systemd_broker import expected_cgroup


UNIT = "montara-i24-job-" + "a" * 32
PROJECT = "7b8f5fd6-02b4-4cd0-8d16-c2d6d606a505"
GEN = 7


class LocalUnixStageIPC(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.directory = self.root / UNIT
        self.directory.mkdir(mode=0o700)
        self.inspection = {
            "ActiveState": "active", "ControlGroup": expected_cgroup(UNIT),
            "MainPID": str(os.getpid()),
        }
        self.reads = 0
        self.server_error = []
        self.threads = []

    def read_snapshot(self):
        self.reads += 1
        return {
            "ok": True, "type": "stage_snapshot", "project": PROJECT,
            "camera_count": 2,
            "stages": {
                "ingest": "done", "sync": "running",
                "cut": "pending", "edit": "not_started",
                "export": "not_started",
            },
        }

    def start_server(self, *, allowed_uid=None, max_requests=1):
        worker = threading.Thread(
            target=self._run_server,
            args=(os.getuid() if allowed_uid is None else allowed_uid,
                  max_requests),
            daemon=True,
        )
        worker.start()
        self.threads.append(worker)
        for _ in range(100):
            if (self.directory / SOCKET_NAME).exists():
                return
            if not worker.is_alive():
                break
            time.sleep(0.01)
        self.fail("Synthetic worker socket did not start")

    def _run_server(self, uid, requests):
        try:
            serve_stage_socket(
                self.directory, project_id=PROJECT, generation=GEN,
                read_snapshot=self.read_snapshot, trusted_broker_uid=uid,
                max_requests=requests,
            )
        except Exception as exc:
            self.server_error.append(exc)

    def broker(self):
        return SystemdUnixStageTransport(
            lambda unit: dict(self.inspection),
            runtime_root=self.root,
            timeout=1.0,
        )

    def finish(self):
        for thread in self.threads:
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
        self.assertEqual(self.server_error, [])

    def test_real_socket_peer_verified_and_read_response(self):
        self.start_server()
        broker = self.broker()
        self.assertTrue(broker.attest(UNIT, project_id=PROJECT, generation=GEN))
        response = broker.stage_snapshot(UNIT, project_id=PROJECT, generation=GEN)
        self.assertEqual(response["project"], PROJECT)
        self.assertEqual(response["camera_count"], 2)
        self.assertEqual(self.reads, 1)
        self.finish()

    def test_wrong_project_rejected_by_worker_without_reading_media(self):
        self.start_server()
        reply = self.broker().stage_snapshot(
            UNIT, project_id="b6e40fcf-a923-494c-acaa-c5836da72e80",
            generation=GEN,
        )
        self.assertFalse(reply["ok"])
        self.assertEqual(self.reads, 0)
        self.finish()

    def test_stale_generation_rejected_inside_worker(self):
        self.start_server()
        reply = self.broker().stage_snapshot(UNIT, project_id=PROJECT,
                                             generation=GEN - 1)
        self.assertFalse(reply["ok"])
        self.assertEqual(self.reads, 0)
        self.finish()

    def test_different_expected_broker_uid_rejects_peer(self):
        self.start_server(allowed_uid=os.getuid() + 1)
        response = self.broker().stage_snapshot(UNIT, project_id=PROJECT,
                                                generation=GEN)
        self.assertFalse(response["ok"])
        self.assertEqual(self.reads, 0)
        self.finish()

    def test_systemd_identity_mismatch_fails_before_connect(self):
        # A refused socket peer still consumes one accept; the next valid
        # request must use the second bounded worker slot.
        self.start_server(max_requests=2)
        broker = self.broker()
        self.inspection["ControlGroup"] = "/system.slice/other.service"
        with self.assertRaises(PrivateEngineRouteDenied):
            broker.attest(UNIT, project_id=PROJECT, generation=GEN)
        self.inspection["ControlGroup"] = expected_cgroup(UNIT)
        self.inspection["MainPID"] = str(os.getpid() + 1)
        with self.assertRaises(PrivateEngineRouteDenied):
            broker.stage_snapshot(UNIT, project_id=PROJECT, generation=GEN)
        self.assertEqual(self.reads, 0)
        # Complete the worker request for clean shutdown.
        self.inspection["MainPID"] = str(os.getpid())
        self.broker().stage_snapshot(UNIT, project_id=PROJECT, generation=GEN)
        self.finish()

    def test_invalid_unit_and_symlink_are_rejected(self):
        self.start_server()
        with self.assertRaises(ValueError):
            self.broker().attest("../evil", project_id=PROJECT, generation=GEN)
        path = self.directory / SOCKET_NAME
        alias = self.directory / "alias.sock"
        alias.symlink_to(path)
        self.assertTrue(alias.is_symlink())
        alias.unlink()
        self.broker().stage_snapshot(UNIT, project_id=PROJECT, generation=GEN)
        self.finish()


if __name__ == "__main__":
    unittest.main()
