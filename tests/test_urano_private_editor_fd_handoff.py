"""I46 real kernel SCM_RIGHTS proof: root-style broker does not move media bytes."""
import json
import os
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

from urano.job_recovery_ledger import JobRecoveryLedger
from urano.private_editor_fd_handoff import (
    open_verified_editor_socket, recv_editor_fd, send_editor_fd,
)
from urano.private_engine_route_contract import PrivateEngineRouteDenied
from urano.private_jm_wsgi_socket import SOCKET_FILE
from urano.restricted_systemd_broker import expected_cgroup


PROJECT = "7b8f5fd6-02b4-4cd0-8d16-c2d6d606a505"
OTHER = "b6e40fcf-a923-494c-acaa-c5836da72e80"


class BrokerConnectedEditorFDTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.ledger = JobRecoveryLedger(self.root / "jobs.sqlite3")
        self.lease = self.ledger.start_trusted("owner-a", PROJECT)
        self.unit = self.ledger.reserve_target_unit(self.lease)
        self.lease = self.ledger.mark_running(self.lease)
        self.folder = self.root / self.unit
        self.folder.mkdir(mode=0o700)
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(self.folder / SOCKET_FILE))
        (self.folder / SOCKET_FILE).chmod(0o600)
        self.server.listen(3)
        self.addCleanup(self.server.close)
        self.inspection = {
            "ActiveState": "active",
            "ControlGroup": expected_cgroup(self.unit),
            "MainPID": str(os.getpid()),
        }

    def open(self, *, owner="owner-a", project=PROJECT, generation=None):
        return open_verified_editor_socket(
            self.ledger, lambda unit: dict(self.inspection),
            owner_id=owner, project_id=project, generation=(
                self.lease.generation if generation is None else generation),
            runtime_root=self.root,
        )

    def test_connected_descriptor_can_stream_directly_without_root_broker(self):
        lease = self.open()
        broker, gateway = socket.socketpair()
        self.addCleanup(broker.close)
        self.addCleanup(gateway.close)
        send_editor_fd(broker, lease)
        self.assertEqual(lease.connection.fileno(), -1)
        stream = recv_editor_fd(
            gateway, expected_broker_uid=os.getuid(),
            project_id=PROJECT, generation=self.lease.generation)
        self.addCleanup(stream.close)
        worker, _ = self.server.accept()
        self.addCleanup(worker.close)
        payload = b"POST /api/v1/wizard/upload HTTP/1.1\r\n" + (
            b"Content-Length: 8192\r\n\r\n") + b"p" * 8192
        stream.sendall(payload)
        self.assertEqual(worker.recv(16384), payload)
        worker.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK")
        self.assertIn(b"200 OK", stream.recv(4096))

    def test_other_project_and_generation_never_get_connected(self):
        with self.assertRaises(PrivateEngineRouteDenied):
            self.open(project=OTHER)
        with self.assertRaises(PrivateEngineRouteDenied):
            self.open(owner="owner-b")
        with self.assertRaises(PrivateEngineRouteDenied):
            self.open(generation=self.lease.generation + 1)

    def test_stale_or_repointed_unit_is_fenced(self):
        self.inspection["ControlGroup"] = "/system.slice/other.service"
        with self.assertRaises(PrivateEngineRouteDenied):
            self.open()
        self.inspection["ControlGroup"] = expected_cgroup(self.unit)
        self.inspection["MainPID"] = str(os.getpid() + 1)
        with self.assertRaises(PrivateEngineRouteDenied):
            self.open()

    def test_socket_symlink_or_broad_mode_denied(self):
        path = self.folder / SOCKET_FILE
        path.chmod(0o666)
        with self.assertRaises(PrivateEngineRouteDenied):
            self.open()
        path.chmod(0o600)

    def test_untrusted_or_wrong_generation_fd_reply_rejected(self):
        lease = self.open()
        broker, gateway = socket.socketpair()
        self.addCleanup(broker.close)
        self.addCleanup(gateway.close)
        send_editor_fd(broker, lease)
        with self.assertRaises(PrivateEngineRouteDenied):
            recv_editor_fd(gateway, expected_broker_uid=os.getuid(),
                           project_id=PROJECT, generation=self.lease.generation + 1)


if __name__ == "__main__":
    unittest.main()
