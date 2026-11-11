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
        self.assertIn(b'originalChemaHome', script)
        self.assertIn(b'homeSection.innerHTML = originalChemaHome', script)
        self.assertIn(b'document.body.classList.add(\'is-intro\')', script)

    def test_stage_launch_hides_only_redundant_first_intro(self):
        path = f"/urano/v1/editor/projects/{self.project.id}/"
        stage = self.get(path + "?start=stage")
        self.assertEqual(stage.status_code, 200)
        self.assertIn(b'montara-owner-stage-entry', stage.data)
        self.assertIn(b'data-go="home"', stage.data)
        self.assertIn(b'Output video name <input id="videoName"', stage.data)
        self.assertIn(b'Only lightweight proxies are sent', stage.data)
        self.assertNotIn(b'final video is made from those small versions', stage.data)
        recovery = self.get(path + "?resume=footage")
        self.assertEqual(recovery.status_code, 200)
        self.assertNotIn(b'class="montara-owner-stage-entry"', recovery.data)
        self.assertIn(b'data-go="home"', recovery.data)
        self.assertIn(b'/urano/v1/entry/picker.js', recovery.data)

    def test_chema_plans_preview_remains_private_and_link_is_functional(self):
        result=self.get(f"/urano/v1/editor/projects/{self.project.id}/")
        self.assertEqual(result.status_code,200)
        self.assertIn(b'href="plans.html"',result.data)
        plans=self.get(
            f"/urano/v1/editor/projects/{self.project.id}/plans.html")
        self.assertEqual(plans.status_code,200)
        self.assertIn(b'src="plans.js"',plans.data)
        self.assertIn(b'href="./"',plans.data)
        self.assertIn(b'SIMULADOR',plans.data)
        js=self.get(
            f"/urano/v1/editor/projects/{self.project.id}/plans.js")
        self.assertEqual(js.status_code,200)

    def test_engine_is_read_only_status_with_project_name_not_switch(self):
        script=self.get("/urano/v1/entry/picker.js").data
        self.assertIn(b"montaraOwnerEngineLabel",script)
        self.assertIn(b"montaraOwnerOpenActive",script)
        self.assertIn(b"engine-state",script)
        self.assertIn(b"Engine \xc2\xb7 ",script)
        self.assertNotIn(b"montaraOwnerEngineSwitch",script)
        self.assertNotIn(b"projects/'+encodeURIComponent(ownProject)+'/close",script)

    def test_native_chema_errors_remain_visible_in_owner_pilot(self):
        path=f"/urano/v1/editor/projects/{self.project.id}/montara.js"
        result=self.get(path)
        self.assertEqual(result.status_code,200)
        self.assertIn(b'f.kind === "error" ? escapeHtml(f.error || "Transfer failed")',
                      result.data)
        self.assertNotIn(
            b'f.small ? "Ready \xc2\xb7 lossless" : f.kind === "error"',
            result.data)
        original=(self.web/"montara.js").read_bytes()
        self.assertIn(
            b'f.small ? "Ready \xc2\xb7 lossless" : f.kind === "error"',
            original)
        css=self.get("/urano/v1/entry/picker.css").data
        self.assertNotIn(b'content:"Transfer failed"',css)

    def test_engine_indicator_is_private_owner_only(self):
        picker = self.get("/urano/v1/entry/picker.js")
        self.assertEqual(picker.status_code, 200)
        js = picker.data
        self.assertIn(b"montaraOwnerEngineControl", js)
        self.assertIn(b"state==='on'", js)
        self.assertIn(b"active_project", js)
        self.assertNotIn(b"montaraOwnerEngineSwitch", js)
        css = self.get("/urano/v1/entry/picker.css")
        self.assertIn(b"montara-owner-engine-led", css.data)

    def test_scripts_are_original_and_editable_by_chema(self):
        stage = self.get(f"/urano/v1/editor/projects/{self.project.id}/?start=stage")
        original = (self.web / "index.html").read_bytes()
        self.assertIn(b'Project name <input id="videoName"', original)
        self.assertIn(b'data-go="home"', original)
        self.assertIn(b'montara.js', stage.data)
        self.assertIn(b'owner-bridge.js', stage.data)


if __name__ == "__main__":
    unittest.main()
