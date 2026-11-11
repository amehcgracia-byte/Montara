"""Original Chema UI static HTTP gate: real owner session, no Engine launch."""
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from urano.original_jm_owner_assets import original_editor_assets_blueprint
from urano.project_catalog import ProjectCatalog
from urano.session_auth import SESSION_COOKIE, SessionStore

ORIGIN = "https://montara-owner.test"


class OriginalJMOwningAssetsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.web = base / "web"
        self.web.mkdir()
        (self.web / "index.html").write_text(
            '<html><script src="montara.js"></script><nav id="steps"></nav></html>')
        (self.web / "montara.js").write_text("console.log('original JM');")
        (self.web / "companion.js").write_text("console.log('original companion');")
        (self.web / "montara.css").write_text("body { margin: 0; }")
        (self.web / "hidden.txt").write_text("private")
        self.catalog = ProjectCatalog(base / "projects.sqlite3")
        self.sessions = SessionStore(base / "sessions.sqlite3")
        self.project = self.catalog.create(
            "owner-a", "Stage", recipe={
                "montara_beta_workspace": {"mode": "stage", "version": 1}})
        self.other = self.catalog.create("owner-b", "Foreign")
        self.auth = self.sessions.issue("owner-a")
        app = Flask("jm-private-assets")
        app.register_blueprint(original_editor_assets_blueprint(
            self.catalog, self.sessions, https_origin=ORIGIN,
            web_root=self.web))
        self.client = app.test_client()
        self.client.set_cookie(
            SESSION_COOKIE, self.auth.token, domain="montara-owner.test")
        self.base = f"/urano/v1/editor/projects/{self.project.id}/"

    def get(self, file="", *, origin=ORIGIN):
        return self.client.get(self.base + file, base_url=origin)

    def test_existing_owner_sees_unchanged_original_html_and_assets(self):
        for name in ("", "montara.js", "companion.js", "montara.css"):
            response = self.get(name)
            self.assertEqual(response.status_code, 200, name)
            self.assertEqual(response.headers["Cache-Control"],
                             "private, no-store")
            self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertIn(b'nav id="steps"', self.get().data)

    def test_other_owner_revoked_and_wrong_origin_denied(self):
        self.assertEqual(self.client.get(
            f"/urano/v1/editor/projects/{self.other.id}/",
            base_url=ORIGIN).status_code, 404)
        self.assertEqual(self.get(origin="https://other.invalid").status_code, 403)
        self.sessions.revoke(self.auth.token)
        self.assertEqual(self.get().status_code, 401)

    def test_only_reviewed_static_bundle_assets(self):
        self.assertEqual(self.get("hidden.txt").status_code, 404)
        self.assertEqual(self.get("missing.js").status_code, 404)
        (self.web / "montara.js").unlink()
        (self.web / "montara.js").symlink_to(self.web / "hidden.txt")
        self.assertEqual(self.get("montara.js").status_code, 404)


if __name__ == "__main__":
    unittest.main()
