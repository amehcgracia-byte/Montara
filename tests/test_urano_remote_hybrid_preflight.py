"""U18: no remote deployment, no real user media, no guessed origins."""
import json
import unittest
from urllib.error import HTTPError
from io import BytesIO
from types import SimpleNamespace

from urano_remote_hybrid_preflight import check_server_url, run_preflight


def dns_global(host, port, type=None):
    return [(2, 1, 6, "", ("93.184.216.34", 443))]


def dns_internal(host, port, type=None):
    return [(2, 1, 6, "", ("127.0.0.1", 443))]


class MockOpener:
    def __init__(self, *, server_status=401, companion=True):
        self.server_status = server_status
        self.companion = companion
        self.urls = []

    def open(self, request, timeout=3):
        url = request.full_url
        self.urls.append(url)
        if url == "http://127.0.0.1:47820/health":
            return MockResponse(200, b'{"app":"montara-companion","ffmpeg":true}' if self.companion else b'{}')
        if url == "https://montara.example/api/v1/wizard/status":
            if self.server_status in (401, 403, 302):
                return MockResponse(self.server_status, b'{"error":"requires credentials"}')
            return MockResponse(self.server_status, b'{"status":"ready"}')
        raise AssertionError("Unknown URL was contacted")


class MockResponse:
    def __init__(self, status, content):
        self.status = status
        self.content = content
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def read(self, count): return self.content[:count]


class RemotePilotContracts(unittest.TestCase):
    def test_reject_insecure_urls_and_private_or_loopback_server(self):
        forbidden = [
            "http://montara.example", "https://127.0.0.1",
            "https://localhost", "https://user:pass@montara.example",
            "https://montara.example:8443", "https://montara.example/path",
            "https://montara.example?token=secret", "https://montara.example/#fragment",
        ]
        for url in forbidden:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    check_server_url(url, resolve=dns_global)
        with self.assertRaises(ValueError):
            check_server_url("https://montara.example", resolve=dns_internal)
        self.assertEqual(check_server_url("https://montara.example", resolve=dns_global),
                         "https://montara.example")

    def test_protected_https_server_plus_real_loopback_companion_can_pass_preflight(self):
        opener = MockOpener(server_status=401)
        report = run_preflight("https://montara.example", resolve=dns_global, opener=opener)
        self.assertTrue(report["ready_for_manual_auth_trial"])
        self.assertTrue(report["server_auth_required_or_forbidden"])
        self.assertTrue(report["companion_healthy"])
        self.assertFalse(report["authenticated_job_verified"])
        self.assertFalse(report["distributed_performance_verified"])
        self.assertFalse(report["media_uploaded"])
        self.assertEqual(opener.urls, [
            "https://montara.example/api/v1/wizard/status",
            "http://127.0.0.1:47820/health",
        ])
        output=json.dumps(report)
        for disallowed in ("montara.example", "access_token", "cookies", "path", "93.184.216.34"):
            self.assertNotIn(disallowed,output)

    def test_unhealthy_companion_not_ready(self):
        result=run_preflight("https://montara.example", resolve=dns_global,
                             opener=MockOpener(companion=False))
        self.assertFalse(result["ready_for_manual_auth_trial"])

    def test_redirect_not_equal_auth_success_or_endpoint_reachable(self):
        result=run_preflight("https://montara.example", resolve=dns_global,
                             opener=MockOpener(server_status=302))
        self.assertFalse(result["server_endpoint_reachable"])
        self.assertFalse(result["ready_for_manual_auth_trial"])

    def test_never_connect_remote_companion(self):
        with self.assertRaises(ValueError):
            run_preflight("https://montara.example",
                          local_health="https://montara.example:47820/health",
                          resolve=dns_global, opener=MockOpener())


if __name__ == "__main__":
    unittest.main()
