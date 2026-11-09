"""C8 physical-beta handoff: Google owner portal is real, never classic app.

All tests use fake OAuth configuration and an isolated temp filesystem; no
Google network calls, production keys, VM changes, or engine provision.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

from urano.owner_beta_wsgi import create_private_owner_beta


class C8GoogleOwnerBridge(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="montara-google-owner-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        private = root / "owner"
        private.mkdir(mode=0o700)
        key = root / "fake-client-secret"
        key.write_text("fake-oauth-client-secret")
        key.chmod(0o600)
        self.private = private
        self.env = {
            "MONTARA_BETA_ORIGIN": "https://beta.example.test",
            "MONTARA_COMPANION_BETA_ORIGIN": "https://beta.example.test",
            "MONTARA_GOOGLE_CLIENT_ID":
                "123456-synthetic.apps.googleusercontent.com",
            "MONTARA_BETA_ALLOWED_EMAILS": "user@example.test",
            "MONTARA_GOOGLE_SECRET_FILE": str(key),
            "MONTARA_OWNER_PRIVATE_DIR": str(private),
        }
        self.app = create_private_owner_beta(self.env)
        self.client = self.app.test_client()

    def test_owner_portal_requires_real_https_host_and_not_basic_auth(self):
        bad = self.client.get("/", base_url="http://localhost")
        self.assertEqual(bad.status_code, 403)
        blocked = self.client.get("/", base_url="https://wrong.example.test")
        self.assertEqual(blocked.status_code, 403)
        good = self.client.get("/", base_url="https://beta.example.test")
        self.assertEqual(good.status_code, 303)
        self.assertEqual(good.headers["Location"], "/urano/v1/google/start")
        self.assertNotIn("Basic", good.headers.get("WWW-Authenticate", ""))

    def test_google_login_redirects_real_provider_url_with_pkce(self):
        response = self.client.get("/urano/v1/google/start",
                                   base_url="https://beta.example.test")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].startswith(
            "https://accounts.google.com/o/oauth2/v2/auth?"))
        self.assertIn("code_challenge_method=S256", response.headers["Location"])
        self.assertIn("state=", response.headers["Location"])
        self.assertIn("nonce=", response.headers["Location"])
        self.assertIn("__Host-montara-oidc-flow=", response.headers["Set-Cookie"])
        self.assertIn("Secure", response.headers["Set-Cookie"])
        self.assertIn("HttpOnly", response.headers["Set-Cookie"])

    def test_anonymous_catalog_and_dashboard_denied(self):
        for path in ("/urano/v1/dashboard", "/urano/v1/projects"):
            with self.subTest(path=path):
                response = self.client.get(path, base_url="https://beta.example.test")
                self.assertEqual(response.status_code, 401)
        # The global editor/Engine is not mounted: cannot bypass per-owner.
        for path in ("/api/v1/project", "/montara/samples",
                     "/urano/v1/workspace/test"):
            response = self.client.get(path,base_url="https://beta.example.test")
            self.assertEqual(response.status_code, 404)

    def test_forwarded_headers_rejected_not_trusted(self):
        for headers in ({"X-Forwarded-Proto":"https"},
                        {"X-Forwarded-Host":"evil.example.test"}):
            with self.subTest(headers=headers):
                response = self.client.get("/", base_url="https://beta.example.test",
                                           headers=headers)
                self.assertEqual(response.status_code, 403)

    def test_health_is_not_silent_claim_of_multitenant_readiness(self):
        health = self.client.get("/healthz", base_url="https://beta.example.test")
        self.assertEqual(health.status_code, 200)
        body = health.get_json()
        self.assertFalse(body["engine_provisioned"])
        self.assertFalse(body["public_multiuser_ready"])
        self.assertNotIn("oauth", json.dumps(body).lower())
        self.assertEqual(health.headers["Cache-Control"], "no-store")

    def test_cannot_mount_proxy_inbox_without_isolated_worker(self):
        with self.assertRaises(ValueError):
            create_private_owner_beta(self.env,proxy_staging_root=self.private)

    def test_invalid_private_dir_denied(self):
        self.private.chmod(0o755)
        with self.assertRaises(ValueError):
            create_private_owner_beta(self.env)
        self.private.chmod(0o700)
        with self.assertRaises(ValueError):
            create_private_owner_beta({**self.env,"MONTARA_OWNER_PRIVATE_DIR":"/"})

    def test_unconfigured_oauth_never_has_mock_login_fallback(self):
        with self.assertRaises(ValueError):
            create_private_owner_beta({**self.env,"MONTARA_GOOGLE_CLIENT_ID":""})
        self.assertNotIn("app", self.app.extensions)


if __name__ == "__main__":
    unittest.main()
