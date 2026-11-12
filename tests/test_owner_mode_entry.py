"""Focused owner mode entry tests: original JM markup, privacy and no Engine side effects."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from flask import Flask

from urano.owner_mode_entry import owner_mode_entry_blueprint
from urano.session_auth import SESSION_COOKIE, SessionStore

ORIGIN = "https://montara-owner.example.test"
HOST = "montara-owner.example.test"
HEADER = ('<header class="top"><a class="brand" href="#"><img src="mark.svg"></a>'
          '<nav class="steps" hidden></nav>'
          '<button class="btn primary" id="newVideo" data-go="mode">New project</button></header>')
MODE = ('<section class="screen" id="mode" hidden>'
        '<div id="intentChoices"><button data-intent="music">Music</button>'
        '<button data-intent="video">Video</button></div>'
        '<div id="musicChoices" hidden><button data-audio-task="song">Mix</button></div>'
        '<div id="videoChoices" hidden>'
        '<button data-platform="youtube">Stage</button>'
        '<button data-platform="reel">Push</button>'
        '<button data-platform="show">Show</button></div>'
        '<button id="modeQuestionBack" hidden>Back</button>'
        '<h2 id="modeQuestion">Mode</h2></section>')


class OwnerModeEntryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        web = self.root / "web"
        web.mkdir()
        (web / "index.html").write_text(
            HEADER + '<section class="screen" id="home"><h1 class="intro-name">Montara</h1></section>' + MODE,
            encoding="utf-8")
        for asset in ("montara.css", "push-pack.css", "mark.svg"):
            (web / asset).write_text("/* pinned JM test asset */", encoding="utf-8")
        self.sessions = SessionStore(self.root / "sessions.sqlite3")
        self.app = Flask(__name__)
        self.app.register_blueprint(owner_mode_entry_blueprint(
            sessions=self.sessions, https_origin=ORIGIN, web_root=web))
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def get(self, path):
        return self.client.get(path, base_url=ORIGIN)

    def login(self):
        session = self.sessions.issue("a" * 32)
        self.client.set_cookie(SESSION_COOKIE, session.token, domain=HOST, secure=True)

    def test_auth_and_markup(self):
        self.assertEqual(self.get("/urano/v1/entry").status_code, 401)
        self.login()
        result = self.get("/urano/v1/entry")
        self.assertEqual(result.status_code, 200)
        for marker in (b"data-platform=\"youtube\"", b"data-platform=\"reel\"",
                       b"data-platform=\"show\"", b"ownerLogout"):
            self.assertIn(marker, result.data)
        self.assertNotIn(b"Engine (beta)", result.data)
        self.assertNotIn(b"id=\"ownerProjects\"", result.data)
        self.assertEqual(self.client.get("/urano/v1/entry",
            base_url="https://attacker.test").status_code, 403)

    def test_assets_and_denied_paths(self):
        self.login()
        self.assertEqual(self.get("/urano/v1/entry.js").status_code, 200)
        for name in ("montara.css", "push-pack.css", "mark.svg"):
            self.assertEqual(self.get("/urano/v1/entry/assets/" + name).status_code, 200)
        self.assertEqual(self.get("/urano/v1/entry/assets/other.env").status_code, 404)

    def test_contextual_picker_is_authenticated_and_no_extra_screen_navigation(self):
        self.login()
        html = self.get("/urano/v1/entry").data
        self.assertIn(b"/urano/v1/entry/picker.js", html)
        self.assertIn(b"/urano/v1/entry/picker.css", html)
        script = self.get("/urano/v1/entry.js")
        self.assertEqual(script.status_code, 200)
        self.assertIn(b"MontaraProjectPicker.open('stage')", script.data)
        for asset in ("picker.js", "picker.css"):
            self.assertEqual(self.get("/urano/v1/entry/" + asset).status_code, 200)

    def test_back_restores_all_projects_and_stage_skips_forced_popup(self):
        self.login()
        script = self.get("/urano/v1/entry.js").data.decode("utf-8")
        self.assertIn("setScope(kind === 'root' ? 'all' : kind)", script)
        self.assertIn("api('editor/projects?mode=stage')", script)
        self.assertIn("openEditor(current.id, true)", script)
        self.assertIn("result.projects.find(p=>p.id===selected)", script)
        self.assertIn("engine-state", script)
        self.assertIn("current=active", script)
        self.assertLess(script.index("current=active"),
                        script.index("openEditor(current.id, true)"))
        self.assertIn("window.MontaraProjectPicker.open('stage')", script)
        self.assertLess(script.index("openEditor(current.id, true)"),
                        script.index("window.MontaraProjectPicker.open('stage')"))

    def test_picker_assets_reject_anonymous_session(self):
        self.assertEqual(self.get("/urano/v1/entry/picker.js").status_code, 401)
        self.assertEqual(self.get("/urano/v1/entry/picker.css").status_code, 401)

    def test_fail_closed_if_chema_changes(self):
        web = self.root / "web"
        (web / "index.html").write_text("<div>Unreviewed editor</div>", encoding="utf-8")
        with self.assertRaises(ValueError):
            owner_mode_entry_blueprint(sessions=self.sessions, https_origin=ORIGIN, web_root=web)


if __name__ == "__main__":
    unittest.main()
