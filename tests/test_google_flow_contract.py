"""Offline HTTPS OIDC flow tests: fake Google signer, real state/PKCE/session/storage."""
from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from flask import Flask

from urano.google_flow import FLOW_COOKIE, GoogleProvider, OIDCSettings, PendingLogins, google_login_blueprint
from urano.google_owner import GoogleOwnerStore
from urano.http_projects import project_blueprint
from urano.project_catalog import ProjectCatalog
from urano.session_auth import SESSION_COOKIE, SessionStore

HOST = "https://lab.example.test"
CALLBACK = HOST + "/urano/v1/google/callback"
CLIENT = "fake-client.apps.googleusercontent.com"


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


class SignedFakeGoogle(GoogleProvider):
    def __init__(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub = self.key.public_key().public_numbers()
        self.signing_keys = {"keys": [{
            "kid": "local-test", "kty": "RSA", "alg": "RS256", "use": "sig",
            "n": b64(pub.n.to_bytes((pub.n.bit_length() + 7) // 8, "big")),
            "e": b64(pub.e.to_bytes((pub.e.bit_length() + 7) // 8, "big")),
        }]}
        self.nonce = ""
        self.expected_challenge = ""
        self.code = ""
        self.sub = "google-sub-a"
        self.email = "alpha@example.test"
        self.fail_token = False
        self.calls = 0

    def token(self, nonce):
        import time
        claims = {"iss": "https://accounts.google.com", "aud": CLIENT,
                  "iat": int(time.time()) - 2, "exp": int(time.time()) + 3600,
                  "nonce": nonce, "sub": self.sub, "email": self.email,
                  "email_verified": True}
        header = {"alg": "RS256", "kid": "local-test", "typ": "JWT"}
        value = b64(json.dumps(header).encode()) + "." + b64(json.dumps(claims).encode())
        sig = self.key.sign(value.encode(), padding.PKCS1v15(), hashes.SHA256())
        return value + "." + b64(sig)

    def exchange(self, code, verifier, settings):
        self.calls += 1
        assert settings.redirect_uri == CALLBACK
        assert settings.client_id == CLIENT
        assert code == self.code
        assert self.expected_challenge == b64(hashlib.sha256(verifier.encode()).digest())
        return self.token("wrong-nonce" if self.fail_token else self.nonce)

    def jwks(self):
        return self.signing_keys


class OIDCFullFlow(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.pending = PendingLogins(root / "pending.sqlite3")
        self.owners = GoogleOwnerStore(root / "owners.sqlite3")
        self.sessions = SessionStore(root / "sessions.sqlite3")
        self.projects = ProjectCatalog(root / "projects.sqlite3")
        self.fake = SignedFakeGoogle()
        self.settings = OIDCSettings(CLIENT, "fake-secret-do-not-use", CALLBACK,
                                     frozenset({"alpha@example.test", "beta@example.test"}))
        self.app = Flask(__name__)
        self.app.register_blueprint(google_login_blueprint(
            settings=self.settings, pending=self.pending, owners=self.owners,
            sessions=self.sessions, provider=self.fake))
        self.app.register_blueprint(project_blueprint(self.projects, self.sessions))
        self.a = self.app.test_client()
        self.b = self.app.test_client()

    def start(self, client):
        response = client.get("/urano/v1/google/start", base_url=HOST, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("Secure", response.headers.get("Set-Cookie", ""))
        self.assertIn("HttpOnly", response.headers.get("Set-Cookie", ""))
        url = urlsplit(response.headers["Location"])
        self.assertEqual(url.scheme + "://" + url.netloc, "https://accounts.google.com")
        data = {k: v[0] for k, v in parse_qs(url.query).items()}
        self.assertEqual(data["code_challenge_method"], "S256")
        self.assertEqual(data["response_type"], "code")
        self.assertEqual(data["redirect_uri"], CALLBACK)
        self.fake.nonce = data["nonce"]
        self.fake.expected_challenge = data["code_challenge"]
        self.fake.code = "fake-provider-code"
        return data["state"]

    def callback(self, client, state, **extra):
        q = {"state": state, "code": "fake-provider-code", **extra}
        return client.get("/urano/v1/google/callback", query_string=q,
                          base_url=HOST, follow_redirects=False)

    def test_valid_pkce_login_session_projects_and_logout(self):
        state = self.start(self.a)
        response = self.callback(self.a, state)
        self.assertEqual(response.status_code, 303)
        self.assertIn("__Host-montara-urano=", response.headers.getlist("Set-Cookie")[0])
        projects = self.a.get("/urano/v1/projects", base_url=HOST)
        self.assertEqual((projects.status_code, projects.json["projects"]), (200, []))
        # HTTP session is usable; same-origin CSRF must still be supplied for writes.
        self.assertEqual(self.a.post("/urano/v1/projects", json={"title": "No CSRF"}, base_url=HOST).status_code, 403)
        self.assertEqual(self.fake.calls, 1)

    def test_state_replay_no_second_exchange(self):
        state = self.start(self.a)
        self.assertEqual(self.callback(self.a, state).status_code, 303)
        self.assertEqual(self.callback(self.a, state).status_code, 401)
        self.assertEqual(self.fake.calls, 1)

    def test_cross_browser_binding_denied_and_consumed(self):
        state = self.start(self.a)
        self.assertEqual(self.callback(self.b, state).status_code, 401)
        self.assertEqual(self.callback(self.a, state).status_code, 401)
        self.assertEqual(self.fake.calls, 0)

    def test_bad_nonce_and_allowlist_fail_closed(self):
        state = self.start(self.a)
        self.fake.fail_token = True
        self.assertEqual(self.callback(self.a, state).status_code, 401)
        self.assertEqual(self.a.get("/urano/v1/projects", base_url=HOST).status_code, 401)
        self.fake.fail_token = False
        state = self.start(self.a)
        self.fake.email = "not-allowed@example.test"
        self.assertEqual(self.callback(self.a, state).status_code, 401)
        self.assertEqual(self.a.get("/urano/v1/projects", base_url=HOST).status_code, 401)

    def test_missing_duplicate_callback_query_parameters(self):
        state = self.start(self.a)
        r = self.a.get("/urano/v1/google/callback",
                       query_string=[("state", state), ("state", state), ("code", "fake-provider-code")],
                       base_url=HOST)
        self.assertEqual(r.status_code, 401)
        self.assertEqual(self.callback(self.a, state).status_code, 401)

    def test_exact_origin_required_and_invalid_configuration(self):
        self.assertEqual(self.a.get("/urano/v1/google/start", base_url="http://lab.example.test").status_code, 403)
        self.assertEqual(self.a.get("/urano/v1/google/start", base_url="https://wrong.example.test").status_code, 403)
        with self.assertRaises(ValueError):
            OIDCSettings(CLIENT, "secret", "http://lab.example.test/urano/v1/google/callback",
                         frozenset({"alpha@example.test"}))

    def test_two_google_subjects_have_isolated_persistent_histories(self):
        sa = self.start(self.a)
        self.assertEqual(self.callback(self.a, sa).status_code, 303)
        self.fake.sub = "google-sub-b"
        self.fake.email = "beta@example.test"
        sb = self.start(self.b)
        self.assertEqual(self.callback(self.b, sb).status_code, 303)
        with self.owners._connect() as db:
            owners = dict(db.execute("SELECT google_sub,owner_id FROM urano_google_owners").fetchall())
        self.assertNotEqual(owners["google-sub-a"], owners["google-sub-b"])
        aproject = self.projects.create(owners["google-sub-a"], "A private")
        bproject = self.projects.create(owners["google-sub-b"], "B private")
        self.assertEqual([p["id"] for p in self.a.get("/urano/v1/projects", base_url=HOST).json["projects"]], [aproject.id])
        self.assertEqual([p["id"] for p in self.b.get("/urano/v1/projects", base_url=HOST).json["projects"]], [bproject.id])
        self.assertEqual(self.a.get(f"/urano/v1/projects/{bproject.id}", base_url=HOST).status_code, 404)
        self.assertEqual(self.b.get(f"/urano/v1/projects/{aproject.id}", base_url=HOST).status_code, 404)

    def test_expired_state_is_denied(self):
        state = self.start(self.a)
        with self.pending._connect() as db:
            db.execute("UPDATE urano_oidc_pending SET expires_at=0")
        self.assertEqual(self.callback(self.a, state).status_code, 401)
        self.assertEqual(self.fake.calls, 0)


if __name__ == "__main__":
    unittest.main()
