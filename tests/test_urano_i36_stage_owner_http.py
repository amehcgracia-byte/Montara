"""I36 authenticated Owner Stage read through independent broker admission.

Uses ephemeral SQLite and a mock broker transport, not real Google credentials.
"""
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from flask import Flask

from urano.project_catalog import ProjectCatalog
from urano.session_auth import SessionStore, SESSION_COOKIE
from urano.owner_broker_preview import owner_engine_preview_blueprint
from urano.private_stage_owner_admission import (
    verify_stage_owner_request, ReadOnlyOwnerCatalog,
)
from urano.private_broker_service import dispatch_owner
from urano.private_owner_admission import OwnerAdmissionDenied


ORIGIN = "https://owner.example.test"


class OwnerStageReadTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.catalog = ProjectCatalog(self.root / "projects.sqlite3")
        self.sessions = SessionStore(self.root / "sessions.sqlite3")
        self.owner = "owner-a"
        self.project = self.catalog.create(
            self.owner, "Stage one",
            recipe={"montara_beta_workspace": {"mode": "stage"}},
        )
        self.other = self.catalog.create(
            "owner-b", "Stage B",
            recipe={"montara_beta_workspace": {"mode": "stage"}},
        )
        self.push = self.catalog.create(
            self.owner, "Push one",
            recipe={"montara_beta_workspace": {"mode": "push"}},
        )
        self.session = self.sessions.issue(self.owner)
        app = Flask("owner-stage")
        app.register_blueprint(owner_engine_preview_blueprint(
            self.catalog, self.sessions, https_origin=ORIGIN))
        self.client = app.test_client()
        self.client.set_cookie(SESSION_COOKIE, self.session.token,
                               domain="owner.example.test")

    def packet(self, **overrides):
        payload = {
            "op": "stage_snapshot_owner", "session": self.session.token,
            "csrf": self.session.csrf,
            "project_id": self.project.id, "generation": 3,
        }
        payload.update(overrides)
        return json.dumps(payload, separators=(",", ":")).encode()

    def url(self, project=None, generation="3"):
        return f"/urano/v1/projects/{project or self.project.id}/stage-status?generation={generation}"

    def test_independent_readonly_broker_session_checks(self):
        self.assertEqual(
            verify_stage_owner_request(self.packet(), owner_db_root=self.root),
            (self.owner, self.project.id, 3),
        )
        self.assertEqual(ReadOnlyOwnerCatalog(self.root).get(
            self.owner, self.project.id).id, self.project.id)
        for changes in (
            {"project_id": self.other.id},
            {"session": "a"*64}, {"csrf": "b"*64},
        ):
            with self.subTest(changes=changes), self.assertRaises(OwnerAdmissionDenied):
                verify_stage_owner_request(self.packet(**changes),
                                           owner_db_root=self.root)
        for changes in (
            {"generation": False}, {"generation": 0},
            {"generation": "3"}, {"unit": "/run/owner-worker"},
            {"op": "close_owner"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                verify_stage_owner_request(self.packet(**changes),
                                           owner_db_root=self.root)

    def test_broker_peer_checks_before_stage_dispatch(self):
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        broker = Mock()
        broker.stage_snapshot_owner.return_value = {
            "ok": True, "project_id": self.project.id,
            "generation": 3, "stages": {}, "camera_count": 0,
        }
        right.sendall(self.packet())
        result = dispatch_owner(left, os.getuid(), self.root, broker)
        self.assertEqual(result["generation"], 3)
        broker.stage_snapshot_owner.assert_called_once_with(
            self.owner, self.project.id, 3, self.root)
        other_left, other_right = socket.socketpair()
        self.addCleanup(other_left.close)
        self.addCleanup(other_right.close)
        other_right.sendall(self.packet())
        with self.assertRaises(PermissionError):
            dispatch_owner(other_left, os.getuid()+1, self.root, broker)

    def test_authenticated_http_owner_stage_read(self):
        result = {"ok": True, "project_id": self.project.id,
                  "generation": 3, "camera_count": 2,
                  "stages": {"ingest": "pending"}}
        with patch("urano.owner_broker_preview.broker_stage_request",
                   return_value=result) as sender:
            reply = self.client.get(
                self.url(), base_url=ORIGIN,
                headers={"X-Urano-CSRF": self.session.csrf})
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json["camera_count"], 2)
        sender.assert_called_once_with(
            self.session.token, self.session.csrf, self.project.id, 3)

    def test_rejects_foreign_project_bad_csrf_push_and_generation(self):
        with patch("urano.owner_broker_preview.broker_stage_request") as sender:
            for url, headers in (
                (self.url(self.other.id), {"X-Urano-CSRF": self.session.csrf}),
                (self.url(self.push.id), {"X-Urano-CSRF": self.session.csrf}),
                (self.url(), {}),
                (self.url(generation="not-an-int"),
                 {"X-Urano-CSRF": self.session.csrf}),
            ):
                with self.subTest(url=url):
                    reply = self.client.get(url, base_url=ORIGIN, headers=headers)
                    self.assertIn(reply.status_code, (400,403,404))
            sender.assert_not_called()

    def test_no_session_no_stage_read(self):
        self.sessions.revoke(self.session.token)
        with patch("urano.owner_broker_preview.broker_stage_request") as sender:
            reply = self.client.get(self.url(), base_url=ORIGIN,
                headers={"X-Urano-CSRF": self.session.csrf})
            self.assertEqual(reply.status_code,401)
            sender.assert_not_called()


if __name__ == "__main__":
    unittest.main()
