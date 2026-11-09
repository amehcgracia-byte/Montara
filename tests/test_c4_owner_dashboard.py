"""C4 opt-in web dashboard: signed Google login, owner-only catalog, no legacy editor."""
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from urano.google_flow import OIDCSettings
from urano.minimal_owner_api import create_owner_api
from test_google_flow_contract import CLIENT, HOST, CALLBACK, SignedFakeGoogle


class TestC4OwnerDashboard(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="montara-c4-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.google = SignedFakeGoogle()
        self.app = create_owner_api(self.root,
            settings=OIDCSettings(CLIENT,"fake-secret-do-not-use",CALLBACK,
                 frozenset({"alpha@example.test","beta@example.test"})),
            provider=self.google, enable_dashboard=True)
        self.a = self.app.test_client()
        self.b = self.app.test_client()

    def login(self, client, sub, email):
        self.google.sub, self.google.email = sub, email
        start = client.get("/urano/v1/google/start",base_url=HOST)
        self.assertEqual(start.status_code,302)
        query = {k:v[0] for k,v in parse_qs(urlsplit(start.headers["Location"]).query).items()}
        self.google.nonce=query["nonce"]
        self.google.expected_challenge=query["code_challenge"]
        self.google.code="fake-provider-code"
        result=client.get("/urano/v1/google/callback",base_url=HOST,
                          query_string={"state":query["state"],"code":self.google.code})
        self.assertEqual(result.status_code,303)
        self.assertEqual(result.headers["Location"],"/urano/v1/dashboard")

    def csrf(self, client):
        result=client.post("/urano/v1/session/refresh",base_url=HOST,
                           headers={"Origin":HOST})
        self.assertEqual(result.status_code,200)
        return result.json["csrf"]

    def test_authentication_and_cross_user_projects(self):
        self.assertEqual(self.a.get("/urano/v1/dashboard",base_url=HOST).status_code,401)
        self.assertEqual(self.a.get("/urano/v1/dashboard.js",base_url=HOST).status_code,401)
        self.login(self.a,"google-sub-a","alpha@example.test")
        self.login(self.b,"google-sub-b","beta@example.test")
        result=self.a.get("/urano/v1/dashboard",base_url=HOST)
        self.assertEqual(result.status_code,200)
        self.assertIn("Mis proyectos",result.get_data(as_text=True))
        self.assertIn("default-src 'none'",result.headers["Content-Security-Policy"])
        self.assertEqual(result.headers["Cache-Control"],"no-store")
        self.assertEqual(self.a.get("/urano/v1/dashboard",base_url="http://lab.example.test").status_code,403)
        self.assertEqual(self.a.get("/urano/v1/dashboard.js",base_url=HOST).status_code,200)
        new=self.a.post("/urano/v1/projects",base_url=HOST,
            headers={"Origin":HOST,"X-Urano-CSRF":self.csrf(self.a)},
            json={"title":"Solo Alice"})
        self.assertEqual(new.status_code,201)
        self.assertEqual(len(self.a.get("/urano/v1/projects",base_url=HOST).json["projects"]),1)
        self.assertEqual(self.b.get("/urano/v1/projects",base_url=HOST).json["projects"],[])
        self.assertEqual(self.b.get("/urano/v1/projects/"+new.json["project"]["id"],base_url=HOST).status_code,404)
        self.assertEqual(self.a.post("/urano/v1/logout",base_url=HOST,
            headers={"X-Urano-CSRF":self.csrf(self.a)}).status_code,200)
        self.assertEqual(self.a.get("/urano/v1/dashboard",base_url=HOST).status_code,401)

    def test_dashboard_not_exposed_by_default(self):
        plain=create_owner_api(self.root,
            settings=OIDCSettings(CLIENT,"fake-secret-do-not-use",CALLBACK,
                                  frozenset({"alpha@example.test"})),provider=self.google)
        self.assertEqual(plain.test_client().get("/urano/v1/dashboard",base_url=HOST).status_code,404)
        self.assertFalse(any(r.rule.startswith("/api/v1/") for r in self.app.url_map.iter_rules()))
        self.assertFalse(any(r.rule.startswith("/montara/uploads") for r in self.app.url_map.iter_rules()))


if __name__=="__main__":
    unittest.main()
