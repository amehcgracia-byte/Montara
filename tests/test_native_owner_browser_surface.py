"""H3: original Chema HTML is served, not recreated or reassembled.

Runs using the repository's pinned web/index.html and real Owner SessionStore.
All data stays in temporary SQLite; no OAuth mock is exposed by the product.
"""
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from urano.native_owner_browser_surface import native_owner_browser_blueprint
from urano.session_auth import SESSION_COOKIE, SessionStore

ORIGIN = "https://montara.test"
WEB = Path(__file__).resolve().parents[1] / "web"


class NativeOwnerChemaSurfaceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.sessions = SessionStore(Path(tmp.name) / "sessions.sqlite3")
        self.issued = self.sessions.issue("owner-a")
        self.app = Flask(__name__)
        self.app.register_blueprint(native_owner_browser_blueprint(
            self.sessions,https_origin=ORIGIN,web_root=WEB))
        self.client = self.app.test_client()

    def auth(self):
        self.client.set_cookie(SESSION_COOKIE,self.issued.token,
                               domain="montara.test")

    def test_authenticates_original_complete_chema_document(self):
        self.auth()
        result = self.client.get("/urano/v1/native/",base_url=ORIGIN)
        self.assertEqual(result.status_code,200)
        expected = (WEB/"index.html").read_text()
        actual = result.get_data(as_text=True)
        self.assertEqual(actual.replace(
            '<script src="owner-bridge.js"></script>\n',""),expected)
        self.assertIn('id="newVideo" data-go="mode"',actual)
        self.assertIn('id="sessionResume"',actual)
        self.assertIn('data-platform="youtube"',actual)
        self.assertIn('data-platform="reel"',actual)
        self.assertIn('data-platform="show"',actual)
        self.assertNotIn('owner_project_picker',actual)
        self.assertNotIn('id="ownerMessage"',actual)
        self.assertNotIn("montara-owner-stage-entry",actual)
        self.assertEqual(result.headers["Cache-Control"],"private, no-store")

    def test_all_native_javascript_and_css_are_private_and_unchanged(self):
        self.auth()
        for filename in ("montara.js","full-session.js","companion.js",
                         "native-export.js","montara.css","mark.svg"):
            with self.subTest(asset=filename):
                result=self.client.get("/urano/v1/native/"+filename,base_url=ORIGIN)
                self.assertEqual(result.status_code,200)
                self.assertEqual(result.data,(WEB/filename).read_bytes())
        bridge=self.client.get("/urano/v1/native/owner-bridge.js",base_url=ORIGIN)
        self.assertEqual(bridge.status_code,200)
        self.assertIn(b"native/rpc/",bridge.data)
        self.assertNotIn(b"owner_project_picker",bridge.data)

    def test_no_login_or_wrong_host_rejected_before_index_or_assets(self):
        for path in ("/urano/v1/native/","/urano/v1/native/montara.js",
                     "/urano/v1/native/owner-bridge.js"):
            self.assertEqual(self.client.get(path,base_url=ORIGIN).status_code,401)
        self.auth()
        for path in ("/urano/v1/native/","/urano/v1/native/montara.js"):
            self.assertEqual(self.client.get(
                path,base_url="https://evil.test").status_code,403)

    def test_unknown_assets_dotfiles_and_traversal_not_served(self):
        self.auth()
        for filename in ("private.json",".env","../../../etc/passwd","plans.html",
                         "missing.js","montara.js.map"):
            with self.subTest(filename=filename):
                result=self.client.get("/urano/v1/native/"+filename,base_url=ORIGIN)
                self.assertEqual(result.status_code,404)


if __name__=="__main__":
    unittest.main()
