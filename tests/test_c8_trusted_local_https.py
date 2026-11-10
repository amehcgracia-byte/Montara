"""HTTPS origin protection: only loopback TLS proxy, never browser-supplied headers."""
import json
import tempfile
import unittest
from pathlib import Path

from werkzeug.test import Client
from werkzeug.wrappers import Response

from urano.trusted_local_https import (
    TrustedLocalHTTPSBoundary, create_loopback_owner_application,
)

HOST = "beta-owner.example.test"


class LocalProxyBoundary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="montara-c8-proxy-")
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        root = base / "owner"
        root.mkdir(mode=0o700)
        secret = base / "client-secret"
        secret.write_text("example-secret-no-production")
        secret.chmod(0o600)
        self.env = {
            "MONTARA_BETA_ORIGIN": "https://" + HOST,
            "MONTARA_COMPANION_BETA_ORIGIN": "https://" + HOST,
            "MONTARA_GOOGLE_CLIENT_ID": "123456-test.apps.googleusercontent.com",
            "MONTARA_BETA_ALLOWED_EMAILS": "beta@example.test",
            "MONTARA_GOOGLE_SECRET_FILE": str(secret),
            "MONTARA_OWNER_PRIVATE_DIR": str(root),
        }
        self.app = create_loopback_owner_application(config=self.env)
        self.client = Client(self.app, Response)

    def ask(self, path="/", *, remote="127.0.0.1", host=HOST, headers=None,
            method="GET"):
        return self.client.open(
            path, method=method, base_url="http://" + host,
            environ_overrides={"REMOTE_ADDR": remote},
            headers=headers or {},
        )

    def test_proxy_creates_https_wsgienv_and_google_session_flow(self):
        home = self.ask()
        self.assertEqual(home.status_code, 303)
        self.assertEqual(home.headers["Location"], "/urano/v1/google/start")
        google = self.ask("/urano/v1/google/start")
        self.assertEqual(google.status_code, 302)
        self.assertTrue(google.headers["Location"].startswith(
            "https://accounts.google.com/o/oauth2/v2/auth?"))
        self.assertIn("redirect_uri=https%3A%2F%2F" + HOST, google.headers["Location"])
        self.assertIn("Secure", google.headers.get("Set-Cookie", ""))
        self.assertIn("HttpOnly", google.headers.get("Set-Cookie", ""))
        self.assertEqual(self.ask("/urano/v1/projects").status_code, 401)
        self.assertEqual(self.ask("/api/v1/project").status_code, 404)

    def test_internet_origin_and_bad_host_denied_before_app(self):
        for remote in ("198.51.100.13", "203.0.113.5", "::ffff:192.0.2.1",
                       "", "not-an-ip"):
            with self.subTest(remote=remote):
                result = self.ask(remote=remote)
                self.assertEqual(result.status_code, 403)
                self.assertNotIn("accounts.google", result.get_data(as_text=True))
        for host in ("evil.example.test", HOST + ":443", "localhost"):
            with self.subTest(host=host):
                self.assertEqual(self.ask(host=host).status_code, 403)

    def test_reject_any_forwarded_or_client_ip_header(self):
        for name in ("X-Forwarded-For", "X-Forwarded-Proto", "X-Forwarded-Host",
                     "X-Forwarded-Port", "Forwarded", "X-Real-Ip"):
            with self.subTest(name=name):
                response = self.ask(headers={name: "https"})
                self.assertEqual(response.status_code, 403)

    def test_unmounted_engine_and_unpaired_companion_remain_unavailable(self):
        self.assertEqual(self.ask("/montara/samples").status_code, 404)
        self.assertEqual(self.ask("/urano/v1/proxy-inbox/projects/abc/slots/0",
                                  method="PUT").status_code, 404)
        status = self.ask("/healthz")
        self.assertEqual(status.status_code, 200)
        data = json.loads(status.get_data(as_text=True))
        self.assertFalse(data["engine_provisioned"])
        self.assertFalse(data["public_multiuser_ready"])

    def test_invalid_origin_is_never_assumed_to_be_https(self):
        with self.assertRaises(ValueError):
            TrustedLocalHTTPSBoundary(lambda env, start: [], origin="http://example.test")
        with self.assertRaises(ValueError):
            create_loopback_owner_application(config={
                **self.env, "MONTARA_BETA_ORIGIN": "http://" + HOST
            })


if __name__ == "__main__":
    unittest.main()
