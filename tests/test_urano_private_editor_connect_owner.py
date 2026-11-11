"""I47 root Owner session -> broker -> AF_UNIX SCM_RIGHTS (real kernel)."""
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from urano.project_catalog import ProjectCatalog
from urano.session_auth import SessionStore
from urano.private_owner_admission import OwnerAdmissionDenied
from urano.private_editor_connect_admission import verify_editor_connect_request
from urano.private_broker_service import dispatch_owner
from urano.private_editor_fd_handoff import (
    EditorFdLease, send_editor_fd, recv_editor_fd,
    PrivateEngineRouteDenied,
)


class OwnerEditorDescriptorAdmissionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.catalog = ProjectCatalog(self.root / "projects.sqlite3")
        self.sessions = SessionStore(self.root / "sessions.sqlite3")
        self.project = self.catalog.create("owner-a", "My Stage")
        self.foreign = self.catalog.create("owner-b", "Other Stage")
        self.auth = self.sessions.issue("owner-a")
        self.generation = 7

    def frame(self, **overrides):
        payload = {
            "op": "connect_editor", "session": self.auth.token,
            "csrf": self.auth.csrf, "project_id": self.project.id,
            "generation": self.generation,
        }
        payload.update(overrides)
        return json.dumps(payload, separators=(",", ":")).encode()

    def test_exact_session_and_generation_required(self):
        self.assertEqual(
            verify_editor_connect_request(self.frame(), owner_db_root=self.root),
            ("owner-a", self.project.id, 7))
        for extra in (
            {"generation": False}, {"generation": "7"},
            {"generation": 0}, {"unit": "montara-root"},
            {"socket": "/run/other.sock"}, {"op": "open_owner"},
        ):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                verify_editor_connect_request(self.frame(**extra),
                                              owner_db_root=self.root)
        for extra in (
            {"project_id": self.foreign.id},
            {"csrf": "a" * 64},
            {"session": "b" * 64},
        ):
            with self.subTest(extra=extra), self.assertRaises(OwnerAdmissionDenied):
                verify_editor_connect_request(self.frame(**extra),
                                              owner_db_root=self.root)

    def test_broker_passes_connected_fd_without_video_bytes(self):
        # Two independent kernel socket pairs: trusted web↔root and root↔worker.
        root, web = socket.socketpair()
        root_to_worker, worker = socket.socketpair()
        self.addCleanup(root.close)
        self.addCleanup(web.close)
        self.addCleanup(worker.close)
        broker = Mock()
        lease = EditorFdLease(self.project.id, self.generation, root_to_worker)
        broker.editor_connect_owner.return_value = lease
        web.sendall(self.frame())
        returned = dispatch_owner(root, os.getuid(), self.root, broker)
        self.assertIs(returned, lease)
        broker.editor_connect_owner.assert_called_once_with(
            "owner-a", self.project.id, self.generation)
        send_editor_fd(root, returned)
        self.assertEqual(root_to_worker.fileno(), -1)
        fd = recv_editor_fd(
            web, expected_broker_uid=os.getuid(),
            project_id=self.project.id, generation=self.generation)
        self.addCleanup(fd.close)
        fd.sendall(b"private synthetic proxy bytes")
        self.assertEqual(worker.recv(256), b"private synthetic proxy bytes")

    def test_foreign_or_revoked_cannot_request_worker_fd(self):
        for packet in (self.frame(project_id=self.foreign.id),
                       self.frame(csrf="a" * 64)):
            root, web = socket.socketpair()
            self.addCleanup(root.close)
            self.addCleanup(web.close)
            web.sendall(packet)
            broker = Mock()
            with self.assertRaises(OwnerAdmissionDenied):
                dispatch_owner(root, os.getuid(), self.root, broker)
            broker.editor_connect_owner.assert_not_called()
        self.sessions.revoke(self.auth.token)
        root, web = socket.socketpair()
        self.addCleanup(root.close)
        self.addCleanup(web.close)
        web.sendall(self.frame())
        with self.assertRaises(OwnerAdmissionDenied):
            dispatch_owner(root, os.getuid(), self.root, Mock())


if __name__ == "__main__":
    unittest.main()
