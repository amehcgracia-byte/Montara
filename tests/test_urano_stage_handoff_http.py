"""U20: strict pathless Companion edit descriptor and session-owner endpoints."""
import json
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from urano.companion_handoff import project_handoff, UnsafeCompanionPlan
from urano.http_owner_runtime import owner_runtime_blueprint
from urano.owner_runtime_controller import OwnerRuntimeController
from urano.project_catalog import ProjectCatalog, ProjectNotFound
from urano.session_auth import SESSION_COOKIE, SessionStore

ORIGIN = "https://lab.example.test"


class CompanionHandoffContract(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="urano-u20-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.catalog = ProjectCatalog(root / "projects.sqlite3")
        self.sessions = SessionStore(root / "sessions.sqlite3")
        self.alice = self.catalog.create("owner-alice", "Alice")
        self.bob = self.catalog.create("owner-bob", "Bob")
        app = Flask("u20")
        app.register_blueprint(owner_runtime_blueprint(
            OwnerRuntimeController(), self.sessions, https_origin=ORIGIN,
            catalog=self.catalog))
        self.client = app.test_client()
        self.session = self.sessions.issue("owner-alice")
        self.client.set_cookie(SESSION_COOKIE, self.session.token,
                               domain="lab.example.test", secure=True)

    def get(self, project_id):
        return self.client.get(f"/urano/v1/runtime/projects/{project_id}/companion-handoff",
                               base_url=ORIGIN)

    def test_valid_descriptor_has_no_local_paths_and_not_renderable(self):
        recipe = {"notes":"private user notes must not be leaked",
                  "urano_edits_v1": {"cuts": [
                      {"source_slot":0,"start_ms":0,"end_ms":1800},
                      {"source_slot":1,"start_ms":200,"end_ms":2500}]}}
        saved = self.catalog.save_recipe(
            "owner-alice", self.alice.id, recipe, expected_revision=0)
        r = self.get(self.alice.id)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        plan = r.json["plan"]
        self.assertEqual(plan["project_revision"], saved.revision)
        self.assertEqual(len(plan["cuts"]), 2)
        self.assertFalse(plan["render_ready"])
        self.assertFalse(plan["local_source_resolution_verified"])
        self.assertTrue(plan["requires_local_originals"])
        self.assertEqual(r.headers["Cache-Control"], "no-store")
        self.assertNotIn("private user notes", r.get_data(as_text=True))
        self.assertNotIn("path", r.get_data(as_text=True))

    def test_foreign_id_and_revoked_cookie_denied(self):
        self.assertEqual(self.get(self.bob.id).status_code,404)
        self.sessions.revoke(self.session.token)
        self.assertEqual(self.get(self.alice.id).status_code,401)

    def test_malformed_recipe_or_paths_fail_closed(self):
        bad = [
            {"source_files":{"0":"/Users/alice/private.mp4"}},
            {"urano_edits_v1":{"cuts":[{"source_slot":0,"start_ms":0,
                                       "end_ms":200,"path":"/Users/alice/secret"}]}},
            {"urano_edits_v1":{"cuts":[{"source_slot":0,"start_ms":200,"end_ms":200}]}},
            {"urano_edits_v1":{"cuts":[{"source_slot":True,"start_ms":0,"end_ms":100}]}},
            {"urano_edits_v1":{"cuts":[{"source_slot":0,"start_ms":0,"end_ms":100000000}]}},
            {"urano_edits_v1":{"cuts":"wrong"}},
        ]
        for recipe in bad:
            current = self.catalog.get("owner-alice",self.alice.id)
            self.catalog.save_recipe("owner-alice",self.alice.id,recipe,
                                     expected_revision=current.revision)
            result = self.get(self.alice.id)
            self.assertEqual(result.status_code,409, result.get_data(as_text=True))
            self.assertNotIn("/Users",result.get_data(as_text=True))

    def test_ingest_for_unprovisioned_owner_is_404_and_no_input_body(self):
        path=f"/urano/v1/runtime/projects/{self.alice.id}/ingest"
        r=self.client.post(path,base_url=ORIGIN,headers={
            "Origin":ORIGIN, "X-Urano-CSRF":self.session.csrf})
        self.assertEqual(r.status_code,404)
        no_csrf=self.client.post(path,base_url=ORIGIN,headers={"Origin":ORIGIN})
        self.assertEqual(no_csrf.status_code,403)
        body=self.client.post(path,base_url=ORIGIN,json={"paths":["/tmp/x"]},
                              headers={"Origin":ORIGIN,"X-Urano-CSRF":self.session.csrf})
        self.assertEqual(body.status_code,400)
        self.assertEqual(self.client.get(path,base_url=ORIGIN).status_code,404)


if __name__ == "__main__":
    unittest.main()
