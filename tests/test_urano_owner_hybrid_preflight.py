"""C8 preflight contracts: test isolated local/remote synthetic responses, no networking."""
import json
import unittest
from io import BytesIO
from urllib.error import HTTPError
from urllib.parse import urlsplit

from urano_owner_hybrid_preflight import preflight_owner_portal


class MockResponse:
    def __init__(self, status, body):
        self.status, self.body = status, body
    def read(self, n):
        return self.body[:n]
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class MockOpener:
    def __init__(self, *, health=200, dashboard=401, companion=200):
        self.health, self.dashboard, self.companion = health, dashboard, companion
        self.requested = []
    def open(self, request, timeout):
        url = request.full_url
        self.requested.append(url)
        if url.endswith("/healthz"):
            code, body = self.health, b'{"service":"montara-owner-beta","engine_provisioned":false}'
        elif url.endswith("/urano/v1/dashboard"):
            code, body = self.dashboard, b'{"error":"Authentication required"}'
        elif url == "http://127.0.0.1:47820/health":
            code, body = self.companion, b'{"app":"montara-companion","ffmpeg":true}'
        else:
            raise AssertionError("Unexpected request")
        if code >= 400:
            raise HTTPError(url, code, "denied", {}, BytesIO(body))
        return MockResponse(code, body)


def public_dns(host, port, type=None):
    return [(2, 1, 6, "", ("8.8.8.8", 443))]


class OwnerHybridPreflightContracts(unittest.TestCase):
    origin = "https://owner.example.test"

    def run_probe(self, **kwargs):
        opener = kwargs.pop("opener", MockOpener())
        return preflight_owner_portal(self.origin, opener=opener,
                                      resolve=public_dns, **kwargs)

    def test_healthy_anonymous_portal_is_not_one_user_benchmark(self):
        opener = MockOpener()
        report = self.run_probe(opener=opener)
        self.assertTrue(report["ready_for_manual_auth_trial"])
        self.assertTrue(report["anonymous_dashboard_denied"])
        self.assertIsNone(report["wan_proxy_upload_bytes"])
        for field in ("google_login_verified", "owner_engine_verified",
                      "stage_to_local_mp4_verified", "one_user_benchmark_complete"):
            self.assertFalse(report[field])
        text = json.dumps(report)
        self.assertNotIn("owner.example.test", text)
        self.assertNotIn("127.0.0.1", text)
        self.assertEqual(len(opener.requested), 3)

    def test_stopped_portal_503_not_ready_and_no_dashboard_probe(self):
        opener = MockOpener(health=503)
        report = self.run_probe(opener=opener)
        self.assertEqual(report["server_http_status"], 503)
        self.assertFalse(report["ready_for_manual_auth_trial"])
        self.assertIsNone(report["anonymous_dashboard_status"])
        self.assertEqual(len(opener.requested), 2)

    def test_not_allowing_public_dashboard(self):
        report = self.run_probe(opener=MockOpener(dashboard=200))
        self.assertFalse(report["anonymous_dashboard_denied"])
        self.assertFalse(report["ready_for_manual_auth_trial"])

    def test_unhealthy_companion_does_not_pass(self):
        report = self.run_probe(opener=MockOpener(companion=503))
        self.assertFalse(report["companion_healthy"])
        self.assertFalse(report["ready_for_manual_auth_trial"])

    def test_reject_remote_or_custom_companion_and_unsafe_tls(self):
        with self.assertRaises(ValueError):
            self.run_probe(local_health="http://192.168.1.10:47820/health")
        with self.assertRaises(ValueError):
            preflight_owner_portal("http://owner.example.test", resolve=public_dns)
        with self.assertRaises(ValueError):
            self.run_probe(timeout=0.1)


if __name__ == "__main__":
    unittest.main()
