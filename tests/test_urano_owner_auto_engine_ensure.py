"""First-valid-upload Engine ensure reuses same Owner unit, never starts twice."""
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from flask import Flask
from urano.job_recovery_ledger import JobRecoveryLedger, BusyOwner
from urano.project_catalog import ProjectCatalog
from urano.session_auth import SessionStore, SESSION_COOKIE
from urano.private_owner_admission import verify_owner_and_project
from urano.private_broker_service import DemoBroker, dispatch_owner
from urano.owner_broker_preview import owner_engine_preview_blueprint


ORIGIN = "https://owner-upload.invalid"


class EnsureOnUploadTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.root = root
        self.catalog = ProjectCatalog(root / "projects.sqlite3")
        self.sessions = SessionStore(root / "sessions.sqlite3")
        self.mine = self.catalog.create("owner-a", "One")
        self.other = self.catalog.create("owner-b", "Foreign")
        self.auth = self.sessions.issue("owner-a")
        app = Flask("ensure-preview")
        app.register_blueprint(owner_engine_preview_blueprint(
            self.catalog, self.sessions, https_origin=ORIGIN))
        self.http = app.test_client()
        self.http.set_cookie(
            SESSION_COOKIE, self.auth.token, domain="owner-upload.invalid")
        self.headers = {"Origin": ORIGIN, "X-Urano-CSRF": self.auth.csrf}

    def packet(self, project=None):
        return json.dumps({
            "op": "ensure_owner",
            "project_id": self.mine.id if project is None else project,
            "session": self.auth.token,
            "csrf": self.auth.csrf,
        }, separators=(",", ":")).encode()

    def test_http_rejects_foreign_missing_csrf_or_untrusted_origin(self):
        with patch("urano.owner_broker_preview.broker_request") as broker:
            for target, headers, status in [
                (self.other.id, self.headers, 404),
                (self.mine.id, {"Origin": ORIGIN}, 403),
                (self.mine.id, {"Origin": "https://evil.invalid",
                                "X-Urano-CSRF": self.auth.csrf}, 403),
            ]:
                result = self.http.post(
                    f"/urano/v1/projects/{target}/ensure",
                    base_url=ORIGIN, headers=headers)
                self.assertEqual(result.status_code, status)
            broker.assert_not_called()

    def test_http_only_sends_existing_project_token_and_csrf(self):
        with patch("urano.owner_broker_preview.broker_request",
                   return_value={"ok": True, "project_id": self.mine.id,
                                 "state": "ready", "generation": 4}) as broker:
            reply = self.http.post(
                f"/urano/v1/projects/{self.mine.id}/ensure",
                base_url=ORIGIN, headers=self.headers)
            self.assertEqual(reply.status_code, 200)
            self.assertEqual(reply.json["generation"], 4)
            broker.assert_called_once_with(
                "ensure_owner", self.auth.token, self.auth.csrf, self.mine.id)

    def test_root_broker_revalidates_session_and_dispatches_ensure(self):
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        broker = Mock()
        broker.ensure_owner.return_value = {
            "ok": True, "project_id": self.mine.id,
            "state": "ready", "generation": 2,
        }
        right.sendall(self.packet())
        self.assertEqual(dispatch_owner(
            left, os.getuid(), self.root, broker)["generation"], 2)
        broker.ensure_owner.assert_called_once_with("owner-a", self.mine.id)
        self.assertEqual(
            verify_owner_and_project(self.packet(), owner_db_root=self.root)[0],
            "ensure_owner")

    def test_broker_reuses_verified_running_owner_no_duplicate_launch(self):
        ledger = JobRecoveryLedger(self.root / "jobs.sqlite3")
        lease = ledger.start_trusted("owner-a", self.mine.id)
        unit = ledger.reserve_target_unit(lease)
        lease = ledger.mark_running(lease)
        broker = object.__new__(DemoBroker)
        broker.ledger = ledger
        broker.control = Mock()
        broker.control.systemd.show.return_value = {
            "ActiveState": "active",
            "ControlGroup": "/system.slice/" + unit + ".service",
            "MainPID": "12345",
        }
        marker = {"ready": True, "folder": self.mine.id, "uid": 1234}
        with patch("urano.private_broker_service.Path") as mock_path:
            # Only marker lookup is patched; ledger uses its real Path.
            mock_path.return_value.__truediv__.return_value.__truediv__.return_value.read_text.return_value = json.dumps(marker)
            result = broker.ensure_owner("owner-a", self.mine.id)
            self.assertEqual(result["generation"], lease.generation)
            self.assertEqual(result["state"], "ready")
        with self.assertRaises(BusyOwner):
            broker.ensure_owner("owner-a", self.other.id)
        broker.control.systemd.show.assert_called_once_with(unit)

    def test_unverified_active_unit_never_restarts_or_reuses(self):
        ledger = JobRecoveryLedger(self.root / "jobs.sqlite3")
        lease = ledger.start_trusted("owner-a", self.mine.id)
        ledger.reserve_target_unit(lease)
        ledger.mark_running(lease)
        broker = object.__new__(DemoBroker)
        broker.ledger = ledger
        broker.control = Mock()
        broker.control.systemd.show.return_value = {
            "ActiveState": "inactive", "ControlGroup": "",
            "MainPID": "0",
        }
        with self.assertRaises(Exception):
            broker.ensure_owner("owner-a", self.mine.id)
        self.assertEqual(
            ledger.unverified_for_owner("owner-a")[0].state, "running")


if __name__ == "__main__":
    unittest.main()
