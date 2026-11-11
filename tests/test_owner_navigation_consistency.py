"""Navigation contract against the real pinned Chema HTML.

No browser session, production project or Engine is needed for these checks.
"""
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from urano.owner_mode_entry import owner_mode_entry_blueprint
from urano.original_jm_owner_assets import original_editor_assets_blueprint
from urano.project_catalog import ProjectCatalog
from urano.session_auth import SESSION_COOKIE, SessionStore

ORIGIN = "https://montara-owner.test"


class OwnerNavigationConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.catalog = ProjectCatalog(base / "projects.sqlite3")
        self.sessions = SessionStore(base / "sessions.sqlite3")
        self.project = self.catalog.create("a" * 32, "Stage", recipe={
            "montara_beta_workspace": {"mode": "stage", "version": 1}})
        auth = self.sessions.issue("a" * 32)
        self.app = Flask(__name__)
        self.web = Path(__import__("os").environ["MONTARA_JM_WEB_ROOT"])
        self.app.register_blueprint(owner_mode_entry_blueprint(
            sessions=self.sessions, https_origin=ORIGIN, web_root=self.web))
        self.app.register_blueprint(original_editor_assets_blueprint(
            self.catalog, self.sessions, https_origin=ORIGIN,
            web_root=self.web, enable_browser_pilot=True))
        self.client = self.app.test_client()
        self.client.set_cookie(SESSION_COOKIE, auth.token,
                               domain="montara-owner.test")

    def get(self, path):
        return self.client.get(path, base_url=ORIGIN)

    def test_home_reuses_chema_animated_logo_and_mode(self):
        result = self.get("/urano/v1/entry")
        self.assertEqual(result.status_code, 200)
        self.assertIn(b'id="home"', result.data)
        self.assertIn(b'intro-name', result.data)
        self.assertIn(b'id="mode" hidden', result.data)
        script = self.get("/urano/v1/entry.js").data
        self.assertIn(b'showHome()', script)
        self.assertIn(b'homeTimer', script)
        self.assertIn(b'document.body.classList.add(\'is-intro\')', script)

    def test_stage_launch_hides_only_redundant_first_intro(self):
        path = f"/urano/v1/editor/projects/{self.project.id}/"
        stage = self.get(path + "?start=stage")
        self.assertEqual(stage.status_code, 200)
        self.assertIn(b'montara-owner-stage-entry', stage.data)
        self.assertIn(b'data-go="home"', stage.data)
        self.assertIn(b'Output video name <input id="videoName"', stage.data)
        recovery = self.get(path + "?resume=footage")
        self.assertEqual(recovery.status_code, 200)
        self.assertNotIn(b'class="montara-owner-stage-entry"', recovery.data)
        self.assertIn(b'data-go="home"', recovery.data)
        self.assertIn(b'/urano/v1/entry/picker.js', recovery.data)

    def test_scripts_are_original_and_editable_by_chema(self):
        stage = self.get(f"/urano/v1/editor/projects/{self.project.id}/?start=stage")
        original = (self.web / "index.html").read_bytes()
        self.assertIn(b'Project name <input id="videoName"', original)
        self.assertIn(b'data-go="home"', original)
        self.assertIn(b'montara.js', stage.data)
        self.assertIn(b'owner-bridge.js', stage.data)


if __name__ == "__main__":
    unittest.main()
