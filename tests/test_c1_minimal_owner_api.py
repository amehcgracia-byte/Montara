"""C1 minimal beta: signed fake Google login → EXISTING SQLite catalog.

Uses no external Google requests, no server deploy and no synthetic media.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from urano.google_flow import OIDCSettings
from urano.minimal_owner_api import create_owner_api
from test_google_flow_contract import CLIENT, HOST, CALLBACK, SignedFakeGoogle


class OwnerAPISeam(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="montara-c1-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.provider = SignedFakeGoogle()
        self.app = create_owner_api(
            self.root,
            settings=OIDCSettings(
                CLIENT, "fake-secret-do-not-use", CALLBACK,
                frozenset({"alpha@example.test", "beta@example.test"}),
            ),
            provider=self.provider,
        )
        self.alice = self.app.test_client()
        self.bob = self.app.test_client()

    def login(self, client, *, sub, email):
        self.provider.sub, self.provider.email = sub, email
        start = client.get("/urano/v1/google/start", base_url=HOST)
        self.assertEqual(start.status_code, 302)
        values = {k: v[0] for k,v in parse_qs(
            urlsplit(start.headers["Location"]).query).items()}
        self.provider.nonce = values["nonce"]
        self.provider.expected_challenge = values["code_challenge"]
        self.provider.code = "fake-provider-code"
        callback = client.get("/urano/v1/google/callback", base_url=HOST,
                              query_string={"state":values["state"],
                                            "code":self.provider.code})
        self.assertEqual(callback.status_code, 303)
        self.assertEqual(callback.headers["Location"], "/urano/v1/projects")

    def csrf(self, client):
        result = client.post("/urano/v1/session/refresh", base_url=HOST,
                             headers={"Origin":HOST})
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        return result.json["csrf"]

    def test_two_real_verified_sessions_and_existing_catalog_isolation(self):
        self.assertEqual(self.alice.get("/urano/v1/projects",base_url=HOST).status_code,401)
        self.login(self.alice,sub="google-sub-alice",email="alpha@example.test")
        self.login(self.bob,sub="google-sub-bob",email="beta@example.test")

        csrf_a = self.csrf(self.alice)
        csrf_b = self.csrf(self.bob)
        new = self.alice.post("/urano/v1/projects",base_url=HOST,
                              headers={"X-Urano-CSRF":csrf_a,"Origin":HOST},
                              json={"title":"Demo owner A"})
        self.assertEqual(new.status_code,201,new.get_data(as_text=True))
        project_id=new.json["project"]["id"]
        self.assertEqual(self.alice.get("/urano/v1/projects",base_url=HOST).json["projects"][0]["id"],
                         project_id)
        self.assertEqual(self.bob.get("/urano/v1/projects",base_url=HOST).json["projects"],[])
        foreign=self.bob.get("/urano/v1/projects/"+project_id,base_url=HOST)
        self.assertEqual(foreign.status_code,404)
        forged=self.bob.put("/urano/v1/projects/"+project_id+"/recipe",base_url=HOST,
                            headers={"Origin":HOST,"X-Urano-CSRF":csrf_b,"X-Owner-ID":"google-sub-alice"},
                            json={"expected_revision":0,"recipe":{"cut":"fake"}})
        self.assertEqual(forged.status_code,404)
        self.assertEqual(self.alice.post("/urano/v1/logout",base_url=HOST,
                                        headers={"X-Urano-CSRF":csrf_a}).status_code,200)
        self.assertEqual(self.alice.get("/urano/v1/projects",base_url=HOST).status_code,401)
        self.assertEqual(self.bob.get("/urano/v1/projects",base_url=HOST).status_code,200)

    def test_refresh_requires_same_origin_and_actual_login(self):
        self.assertEqual(self.alice.post("/urano/v1/session/refresh",base_url=HOST,
                                        headers={"Origin":HOST}).status_code,401)
        self.login(self.alice,sub="google-sub-alice",email="alpha@example.test")
        self.assertEqual(self.alice.post("/urano/v1/session/refresh",base_url=HOST,
                                        headers={"Origin":"https://evil.example.test"}).status_code,403)
        self.assertEqual(self.alice.post("/urano/v1/session/refresh",
                                        base_url="http://lab.example.test",
                                        headers={"Origin":"http://lab.example.test"}).status_code,403)
        self.assertEqual(self.alice.post("/urano/v1/projects",base_url=HOST,
                                        json={"title":"No CSRF"}).status_code,403)
        self.assertEqual(self.csrf(self.alice).__class__,str)

    def test_opt_in_only_no_public_engine_or_user_chosen_identity(self):
        urls={r.rule for r in self.app.url_map.iter_rules()}
        self.assertNotIn("/api/v1/stages/ingest/run",urls)
        self.assertNotIn("/montara/uploads",urls)
        self.assertNotIn("/video-renders",urls)
        self.assertNotIn("/urano/v1/runtime/projects/<project_id>/activate",urls)
        self.assertNotIn("/urano-google-lab/",urls)
        self.assertNotIn("/signup",urls)
        self.assertEqual(self.alice.post("/urano/v1/projects",base_url=HOST,
                                        headers={"X-Owner-ID":"someone-else"},
                                        json={"title":"No session"}).status_code,401)

    def test_unauthorized_email_does_not_get_catalog_session(self):
        start=self.alice.get("/urano/v1/google/start",base_url=HOST)
        values={k:v[0] for k,v in parse_qs(urlsplit(start.headers["Location"]).query).items()}
        self.provider.nonce=values["nonce"]
        self.provider.expected_challenge=values["code_challenge"]
        self.provider.code="fake-provider-code"
        self.provider.email="not-allowed@example.test"
        self.assertEqual(self.alice.get("/urano/v1/google/callback",base_url=HOST,
                        query_string={"state":values["state"],"code":self.provider.code}).status_code,401)
        self.assertEqual(self.alice.get("/urano/v1/projects",base_url=HOST).status_code,401)


if __name__ == "__main__":
    unittest.main()
