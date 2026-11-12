"""The browser can use Companion only from the explicitly approved Montara origins.

Offline: no network, no local Companion start, no user data.
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "companion"))
import companion


class CompanionCloudflareOriginContracts(unittest.TestCase):
    def origin_allowed(self, origin):
        # Exercise the real request-handler policy without starting the listener.
        instance = object.__new__(companion.Handler)
        instance.headers = {"Origin": origin}
        return companion.Handler.origin_ok(instance)

    def test_approved_beta_frontends_and_existing_local_origins(self):
        for origin in (
            "https://montara-beta-preview.pages.dev",
            "https://montara-owner.memoriainvalida001.workers.dev",
            "http://127.0.0.1:8101",
            "http://localhost:8102",
            "https://example.vercel.app",
            "https://example.trycloudflare.com",
        ):
            with self.subTest(origin=origin):
                self.assertEqual(self.origin_allowed(origin), origin)

    def test_other_pages_workers_and_lookalikes_are_not_trusted(self):
        for origin in (
            "https://attacker.pages.dev",
            "https://attacker.workers.dev",
            "https://montara-beta-preview.pages.dev.attacker.test",
            "https://montara-owner.memoriainvalida001.workers.dev.attacker.test",
            "https://montara-beta-preview.pages.dev:443",
            "http://montara-beta-preview.pages.dev",
            "https://sub.montara-beta-preview.pages.dev",
            "null",
            "",
        ):
            with self.subTest(origin=origin):
                self.assertIsNone(self.origin_allowed(origin))

    def test_preflight_denied_without_origin(self):
        self.assertIsNone(self.origin_allowed(""))


if __name__ == "__main__":
    unittest.main()
