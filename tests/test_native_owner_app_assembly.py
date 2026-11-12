"""H3 composition: existing Google PKCE redirect lands on Chema, not dashboard."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from urano.google_flow import OIDCSettings
from urano.native_owner_app import create_native_owner_api
from urano.session_auth import SESSION_COOKIE, SessionStore

ORIGIN="https://montara.test"
WEB=Path(__file__).resolve().parents[1]/"web"


class NativeOwnerAppAssemblyTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="montara-owner-app-")
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.calls=[]
        def ensure(op,session,csrf,workspace):
            self.calls.append((op,workspace))
            return {"ok":True,"project_id":workspace,
                    "state":"ready","generation":1}
        self.app=create_native_owner_api(
            self.root,settings=OIDCSettings(
                client_id="test-client",
                client_secret="test-secret-never-exported",
                redirect_uri=ORIGIN+"/urano/v1/google/callback",
                allowed_emails=frozenset({"one@example.test"})
            ),
            chema_web_root=WEB,ensure_worker=ensure,
            connect_worker=lambda *a,**k:None,
        )
        self.client=self.app.test_client()
        self.sessions=SessionStore(self.root/"sessions.sqlite3")

    def test_only_google_and_original_chema_page_without_dashboard(self):
        anonymous=self.client.get("/",base_url=ORIGIN)
        self.assertEqual(anonymous.status_code,302)
        self.assertEqual(anonymous.location,"/urano/v1/google/start")
        start=self.client.get("/urano/v1/google/start",base_url=ORIGIN)
        self.assertEqual(start.status_code,302)
        self.assertTrue(start.location.startswith(
            "https://accounts.google.com/o/oauth2/v2/auth?"))
        self.assertIn("code_challenge=",start.location)
        self.assertNotIn("test-secret",start.location)
        issued=self.sessions.issue("owner-a")
        self.client.set_cookie(SESSION_COOKIE,issued.token,domain="montara.test")
        home=self.client.get("/",base_url=ORIGIN)
        self.assertEqual(home.status_code,302)
        self.assertEqual(home.location,"/urano/v1/native/")
        chema=self.client.get(home.location,base_url=ORIGIN)
        self.assertEqual(chema.status_code,200)
        self.assertIn('id="newVideo" data-go="mode"',chema.get_data(as_text=True))
        self.assertNotIn("owner_project_picker",chema.get_data(as_text=True))
        self.assertEqual(self.client.get("/urano/v1/dashboard",
                         base_url=ORIGIN).status_code,404)
        self.assertEqual(self.client.get("/urano/v1/entry",
                         base_url=ORIGIN).status_code,404)

    def test_rotating_csrf_drives_anonymous_workspace_ensure(self):
        issued=self.sessions.issue("owner-a")
        self.client.set_cookie(SESSION_COOKIE,issued.token,domain="montara.test")
        refresh=self.client.post("/urano/v1/session/refresh",base_url=ORIGIN,
                                 headers={"Origin":ORIGIN})
        self.assertEqual(refresh.status_code,200)
        newcsrf=refresh.json["csrf"]
        self.assertNotEqual(newcsrf,issued.csrf)
        before=self.client.post("/urano/v1/native/ensure",base_url=ORIGIN,
                     headers={"Origin":ORIGIN,"X-Urano-CSRF":issued.csrf})
        self.assertEqual(before.status_code,403)
        after=self.client.post("/urano/v1/native/ensure",base_url=ORIGIN,
                     headers={"Origin":ORIGIN,"X-Urano-CSRF":newcsrf})
        self.assertEqual(after.status_code,200)
        self.assertEqual(after.json,{"state":"ready","generation":1})
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.calls[0][0],"ensure_owner")
        self.assertNotIn(self.calls[0][1],after.get_data(as_text=True))

    def test_unknown_host_and_unverified_login_fail_closed(self):
        bad=self.client.get("/",base_url="https://untrusted.test")
        self.assertEqual(bad.status_code,403)
        csrf=self.client.post("/urano/v1/session/refresh",base_url=ORIGIN,
                              headers={"Origin":ORIGIN})
        self.assertEqual(csrf.status_code,401)
        self.assertFalse(self.calls)


if __name__=="__main__":
    unittest.main()
