"""Negative security contracts for U16A: Google-owner -> real Engine folder visibility.

No engine startup, render, upload, or media files are exposed.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from flask import Flask

from urano.engine_bindings import EngineProjectRegistry
from urano.google_oidc import GoogleIdentity
from urano.google_owner import GoogleOwnerStore
from urano.http_engine_status import owner_engine_status_blueprint
from urano.http_projects import project_blueprint
from urano.project_catalog import ProjectCatalog, ProjectNotFound
from urano.session_auth import SESSION_COOKIE, SessionStore


class OwnerEngineStatusContract(unittest.TestCase):
    def setUp(self):
        private = tempfile.TemporaryDirectory(prefix="urano-u16a-")
        self.addCleanup(private.cleanup)
        self.root = Path(private.name)
        self.engine_root = self.root / "engine-data"
        (self.engine_root / "Projects").mkdir(parents=True)
        for folder in ("first-camera.zuckervid", "second-camera.zuckervid"):
            p = self.engine_root / "Projects" / folder
            p.mkdir()
            (p / "project.json").write_text('{"name":"synthetic"}')
        self.catalog = ProjectCatalog(self.root / "projects.sqlite3")
        self.sessions = SessionStore(self.root / "sessions.sqlite3")
        self.owners = GoogleOwnerStore(self.root / "google-owners.sqlite3")
        self.registry = EngineProjectRegistry(self.root / "links.sqlite3",
                                             self.engine_root, self.catalog)
        allowlist = frozenset({"first@example.test", "second@example.test"})
        self.a_owner = self.owners.resolve_beta_owner(
            GoogleIdentity("google-sub-first", "first@example.test"), allowed_emails=allowlist)
        self.b_owner = self.owners.resolve_beta_owner(
            GoogleIdentity("google-sub-second", "second@example.test"), allowed_emails=allowlist)
        self.a_project = self.catalog.create(self.a_owner, "First Stage")
        self.b_project = self.catalog.create(self.b_owner, "Second Stage")
        self.unbound = self.catalog.create(self.a_owner, "Never activated")
        self.registry.bind_trusted(self.a_owner, self.a_project.id, "first-camera.zuckervid")
        self.registry.bind_trusted(self.b_owner, self.b_project.id, "second-camera.zuckervid")
        app = Flask("test-u16a")
        app.register_blueprint(project_blueprint(self.catalog, self.sessions))
        app.register_blueprint(owner_engine_status_blueprint(self.registry, self.sessions))
        self.a, self.b, self.stranger = app.test_client(), app.test_client(), app.test_client()
        self.a.set_cookie(SESSION_COOKIE, self.sessions.issue(self.a_owner).token, secure=True)
        self.b.set_cookie(SESSION_COOKIE, self.sessions.issue(self.b_owner).token, secure=True)

    @staticmethod
    def path(project_id):
        return f"/urano/v1/projects/{project_id}/engine"

    def test_owner_sees_only_non_sensitive_binding_status(self):
        response = self.a.get(self.path(self.a_project.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {
            "linked": True, "status": "linked_not_activated",
            "engine_access": False, "render_access": False})
        self.assertNotIn(str(self.engine_root), response.get_data(as_text=True))
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(self.b.get(self.path(self.b_project.id)).status_code, 200)

    def test_cross_account_and_unauthenticated_denied(self):
        self.assertEqual(self.a.get(self.path(self.b_project.id)).status_code, 404)
        self.assertEqual(self.b.get(self.path(self.a_project.id)).status_code, 404)
        self.assertEqual(self.stranger.get(self.path(self.a_project.id)).status_code, 401)
        self.assertEqual(self.a.get(self.path(self.unbound.id)).status_code, 404)
        self.assertEqual(self.a.get(self.path("not-a-uuid")).status_code, 404)
        self.assertEqual(self.a.get(self.path(self.b_project.id)).json,
                         self.a.get(self.path(self.unbound.id)).json)

    def test_visitor_cannot_bind_open_render_or_override_owner(self):
        data = {"owner_id": self.b_owner, "folder": "second-camera.zuckervid"}
        self.assertEqual(self.a.post(self.path(self.a_project.id), json=data).status_code, 405)
        self.assertEqual(self.a.put(self.path(self.a_project.id), json=data).status_code, 405)
        self.assertEqual(self.a.delete(self.path(self.a_project.id)).status_code, 405)
        self.assertEqual(self.a.get(self.path(self.b_project.id),
                                    headers={"X-Owner-ID": self.b_owner}).status_code, 404)
        self.assertEqual(self.a.get(self.path(self.b_project.id),
                                    query_string={"owner_id": self.b_owner,
                                                  "path": str(self.engine_root)}).status_code, 404)
        with self.assertRaises(ProjectNotFound):
            self.registry.resolve_internal(self.a_owner, self.b_project.id)

    def test_symlink_removed_and_cross_owner_collision_fail_closed(self):
        physical = self.engine_root / "Projects" / "first-camera.zuckervid"
        (physical / "project.json").unlink()
        (physical / "project.json").symlink_to(self.engine_root / "Projects" /
                                                 "second-camera.zuckervid" / "project.json")
        self.assertEqual(self.a.get(self.path(self.a_project.id)).status_code, 404)
        with self.assertRaises(ValueError):
            self.registry.bind_trusted(self.a_owner, self.unbound.id, "second-camera.zuckervid")

    def test_restart_and_revocation(self):
        # Persistence across closing and reopening the registry.
        registry2 = EngineProjectRegistry(self.root / "links.sqlite3",
                                          self.engine_root, self.catalog)
        self.assertEqual(registry2.resolve_internal(self.a_owner, self.a_project.id).name,
                         "first-camera.zuckervid")
        token = self.a.get_cookie(SESSION_COOKIE).value
        self.sessions.revoke(token)
        self.assertEqual(self.a.get(self.path(self.a_project.id)).status_code, 401)


if __name__ == "__main__":
    unittest.main()
