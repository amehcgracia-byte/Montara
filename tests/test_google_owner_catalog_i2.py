"""Google Owner I2 end-to-end contract with *signed synthetic* Google tokens.

No external requests, credentials, deployment or changes to Chema's editor.
"""
from __future__ import annotations

import base64
import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from urano.google_catalog_app import create_google_owner_catalog
from urano.google_flow import OIDCSettings
from urano.session_auth import SESSION_COOKIE, SessionStore

ORIGIN = "https://owner.test"
CLIENT_ID = "test-owner-client"


def b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


class SignedFakeGoogle:
    def __init__(self):
        self.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.logins = {}

    def jwks(self):
        k = self.private.public_key().public_numbers()
        return {"keys": [{"kty": "RSA", "kid": "i2-test-key", "alg": "RS256",
                          "n": b64(k.n.to_bytes((k.n.bit_length() + 7) // 8, "big")),
                          "e": b64(k.e.to_bytes((k.e.bit_length() + 7) // 8, "big"))}]}

    def exchange(self, code, verifier, settings):
        sub, email, nonce, verified = self.logins[code]
        now = int(time.time())
        hdr = b64(json.dumps({"alg": "RS256", "kid": "i2-test-key"}).encode())
        payload = b64(json.dumps({
            "iss": "https://accounts.google.com", "aud": CLIENT_ID,
            "iat": now, "exp": now + 3600, "nonce": nonce,
            "sub": sub, "email": email, "email_verified": verified,
        }).encode())
        signed = (hdr + "." + payload).encode("ascii")
        signature = self.private.sign(signed, padding.PKCS1v15(), hashes.SHA256())
        return signed.decode("ascii") + "." + b64(signature)


class GoogleOwnerCatalogI2Tests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="i2-google-owner-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.root.chmod(0o700)
        self.google = SignedFakeGoogle()
        self.app = create_google_owner_catalog(
            self.root, provider=self.google,
            settings=OIDCSettings(
                client_id=CLIENT_ID, client_secret="test-only",
                redirect_uri=ORIGIN + "/urano/v1/google/callback",
                allowed_emails=frozenset({"a@example.test", "b@example.test"}),
            ))
        self.sessions = SessionStore(self.root / "sessions.sqlite3")

    def login(self, client, sub, email, code="a1", verified=True):
        start = client.get("/urano/v1/google/start", base_url=ORIGIN)
        self.assertEqual(start.status_code, 302)
        from urllib.parse import urlsplit, parse_qs
        auth = parse_qs(urlsplit(start.location).query)
        self.assertEqual(auth["code_challenge_method"], ["S256"])
        self.assertEqual(auth["prompt"], ["select_account"])
        with sqlite3.connect(self.root / "pending.sqlite3") as db:
            nonce = db.execute("SELECT nonce FROM urano_oidc_pending").fetchall()[-1][0]
        self.google.logins[code] = sub, email, nonce, verified
        callback = client.get("/urano/v1/google/callback", base_url=ORIGIN,
                              query_string={"state": auth["state"][0], "code": code})
        return callback, auth["state"][0]

    @staticmethod
    def post(client, url, data=None, csrf=None):
        return client.post(url, base_url=ORIGIN, json=data or {},
                           headers={"Origin": ORIGIN, **({"X-Urano-CSRF": csrf} if csrf else {})})

    def test_two_google_accounts_private_projects_and_three_day_sessions(self):
        a = self.app.test_client()
        b = self.app.test_client()
        result_a, _ = self.login(a, "google-sub-a", "a@example.test", "code-a")
        result_b, _ = self.login(b, "google-sub-b", "b@example.test", "code-b")
        self.assertEqual((result_a.status_code, result_b.status_code), (303, 303))
        self.assertEqual(result_a.location, "/urano/v1/projects")
        self.assertIn("Max-Age=259200", result_a.headers["Set-Cookie"])
        ca = self.post(a, "/urano/v1/session/refresh").json["csrf"]
        cb = self.post(b, "/urano/v1/session/refresh").json["csrf"]
        self.assertEqual(self.post(a, "/urano/v1/projects", {"title": "Alice"}, ca).status_code, 201)
        self.assertEqual(self.post(b, "/urano/v1/projects", {"title": "Bob"}, cb).status_code, 201)
        ap = a.get("/urano/v1/projects", base_url=ORIGIN).json["projects"][0]
        bp = b.get("/urano/v1/projects", base_url=ORIGIN).json["projects"][0]
        self.assertNotEqual(ap["id"], bp["id"])
        self.assertEqual(a.get("/urano/v1/projects/" + bp["id"], base_url=ORIGIN).status_code, 404)
        self.assertEqual(b.get("/urano/v1/projects/" + ap["id"], base_url=ORIGIN).status_code, 404)
        self.assertEqual(self.post(a, "/urano/v1/projects", {"title": "CSRF missing"}).status_code, 403)
        self.assertEqual(self.post(a, "/urano/v1/projects", {"title": "CSRF old"}, ca).status_code, 201)
        self.assertEqual(self.post(a, "/urano/v1/logout", csrf=ca).status_code, 200)
        self.assertEqual(a.get("/urano/v1/projects", base_url=ORIGIN).status_code, 401)
        self.assertEqual(len(self.sessions._connect().execute(
            "SELECT token_hash FROM urano_auth_sessions").fetchall()), 1)

    def test_unverified_or_unlisted_google_identity_never_gets_session(self):
        for idx, (email, verified) in enumerate([
            ("unknown@example.test", True), ("a@example.test", False),
        ]):
            with self.subTest(email=email, verified=verified):
                client = self.app.test_client()
                callback, state = self.login(client, "unknown-" + str(idx), email,
                                             "denied-" + str(idx), verified)
                self.assertEqual(callback.status_code, 401)
                self.assertEqual(client.get("/urano/v1/projects",
                                           base_url=ORIGIN).status_code, 401)
                self.assertEqual(client.get("/urano/v1/google/callback",
                                           base_url=ORIGIN,
                                           query_string={"state": state, "code": "denied-" + str(idx)}).status_code, 401)

    def test_wrong_origin_and_anonymous_catalog_are_rejected(self):
        client = self.app.test_client()
        self.assertEqual(client.get("/urano/v1/projects", base_url=ORIGIN).status_code, 401)
        self.assertEqual(client.get("/urano/v1/projects",
                                    base_url="https://attacker.test").status_code, 403)
        self.assertEqual(self.post(client, "/urano/v1/session/refresh").status_code, 401)
        self.assertEqual(client.get("/", base_url=ORIGIN).location,
                         "/urano/v1/google/start")
        self.assertEqual(client.get("/urano/v1/google/start",
                                    base_url="https://attacker.test").status_code, 403)


if __name__ == "__main__":
    unittest.main()
