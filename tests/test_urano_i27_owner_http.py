"""I27 beta Owner endpoint: zero browser-controlled host targets."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from flask import Flask

from urano.project_catalog import ProjectCatalog
from urano.session_auth import SessionStore,SESSION_COOKIE
from urano.owner_broker_preview import owner_engine_preview_blueprint
from urano.owner_dashboard import owner_dashboard_blueprint

ORIGIN="https://montara-example.invalid"

class OwnerHTTPContracts(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p=Path(tmp.name)
        self.projects=ProjectCatalog(p/"projects.sqlite")
        self.sessions=SessionStore(p/"sessions.sqlite")
        self.owner="owner-a";self.foreign="owner-b"
        self.mine=self.projects.create(self.owner,"Personal")
        self.other=self.projects.create(self.foreign,"Foreign")
        self.auth=self.sessions.issue(self.owner)
        app=Flask("i27-owner-contract")
        app.register_blueprint(owner_engine_preview_blueprint(
            self.projects,self.sessions,https_origin=ORIGIN))
        app.register_blueprint(owner_dashboard_blueprint(
            self.sessions,https_origin=ORIGIN,enable_engine_preview=True))
        self.client=app.test_client()
        self.client.set_cookie(SESSION_COOKIE,self.auth.token,domain="montara-example.invalid")
        self.base=ORIGIN
        self.target=f"/urano/v1/projects/{self.mine.id}/open"
        self.headers={"Origin":ORIGIN,"X-Urano-CSRF":self.auth.csrf}

    def test_good_owner_opens_without_unit_or_paths(self):
        with patch("urano.owner_broker_preview.broker_request",return_value={
            "ok":True,"project_id":self.mine.id,"state":"ready","generation":3}) as broker:
            r=self.client.post(self.target,headers=self.headers,base_url=self.base)
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json["state"],"ready")
        broker.assert_called_once_with("open_owner",self.auth.token,self.auth.csrf,self.mine.id)

    def test_foreign_project_is_not_forwarded(self):
        with patch("urano.owner_broker_preview.broker_request") as broker:
            r=self.client.post(f"/urano/v1/projects/{self.other.id}/open",
                headers=self.headers,base_url=self.base)
        self.assertEqual(r.status_code,404)
        broker.assert_not_called()

    def test_csrf_denied_before_broker(self):
        with patch("urano.owner_broker_preview.broker_request") as broker:
            r=self.client.post(self.target,headers={"Origin":ORIGIN},
                base_url=self.base)
        self.assertEqual(r.status_code,403)
        broker.assert_not_called()

    def test_untrusted_origin_denied(self):
        with patch("urano.owner_broker_preview.broker_request") as broker:
            r=self.client.post(self.target,headers={"Origin":"https://evil.invalid",
                    "X-Urano-CSRF":self.auth.csrf},base_url=self.base)
        self.assertEqual(r.status_code,403)
        broker.assert_not_called()

    def test_body_rejected(self):
        with patch("urano.owner_broker_preview.broker_request") as broker:
            r=self.client.post(self.target,headers=self.headers,
                base_url=self.base,data=b'{"unit":"owner"}')
        self.assertEqual(r.status_code,400)
        broker.assert_not_called()

    def test_closed_session_denied(self):
        self.sessions.revoke(self.auth.token)
        with patch("urano.owner_broker_preview.broker_request") as broker:
            r=self.client.post(self.target,headers=self.headers,base_url=self.base)
        self.assertEqual(r.status_code,401)
        broker.assert_not_called()

    def test_close_is_same_authorized_project(self):
        with patch("urano.owner_broker_preview.broker_request",return_value={
            "ok":True,"project_id":self.mine.id,"state":"stopped"}) as broker:
            r=self.client.post(self.target.replace("/open","/close"),
                headers=self.headers,base_url=self.base)
        self.assertEqual(r.status_code,200)
        broker.assert_called_once_with("close_owner",self.auth.token,self.auth.csrf,self.mine.id)

    def test_dashboard_buttons_only_when_preview_flag_enabled(self):
        r=self.client.get("/urano/v1/dashboard",base_url=self.base)
        self.assertEqual(r.status_code,200)
        self.assertIn(b'data-engine-beta="1"',r.data)

if __name__=="__main__":
    unittest.main()

