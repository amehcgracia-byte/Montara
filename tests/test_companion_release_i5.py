"""I5 distribution contract; QA artifacts never impersonate signed releases."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from flask import Flask
from companion.release_catalog import companion_releases_blueprint

ENGINE = "a" * 40


class CompanionReleaseI5Tests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="montara-i5-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.engine = ENGINE
        app = Flask(__name__)
        app.register_blueprint(companion_releases_blueprint(self.root, lambda: self.engine))
        self.client = app.test_client()

    def entry(self, os_name, arch, *, signed=True, notarized=False):
        extension = ".pkg" if os_name == "macos" else ".msix"
        filename = "Montara-Companion-1.2.3-" + os_name + "-" + arch + extension
        content = (os_name + arch).encode() * 400
        (self.root / filename).write_bytes(content)
        return {"os": os_name, "arch": arch, "filename": filename,
                "version": "1.2.3", "sha256": hashlib.sha256(content).hexdigest(),
                "signed": signed, "notarized": notarized,
                "signing_identity": "test-fixture-only"}

    def publish(self, entries, engine=ENGINE):
        (self.root / "companion-releases.json").write_text(
            json.dumps({"schema": 1, "engine": engine, "releases": entries}), encoding="utf-8")

    def test_no_installer_is_published_without_verified_manifest(self):
        response = self.client.get("/montara/companion/releases")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["releases"], [])
        self.assertEqual(self.client.get("/montara/companion/releases/download?os=windows&arch=x64").status_code, 503)

    def test_both_signed_platforms_and_exact_engine_are_needed(self):
        win = self.entry("windows", "x64")
        mac = self.entry("macos", "arm64", notarized=True)
        self.publish([win, mac])
        response = self.client.get("/montara/companion/releases")
        self.assertEqual(response.status_code, 200)
        self.assertEqual({(x["os"], x["arch"]) for x in response.json["releases"]},
                         {("windows", "x64"), ("macos", "arm64")})
        self.assertNotIn("filename", response.json["releases"][0])
        with self.client.get("/montara/companion/releases/download?os=macos&arch=arm64") as response:\n            self.assertEqual(response.status_code, 200)
        with self.client.get("/montara/companion/releases/download?os=windows&arch=x64") as response:\n            self.assertEqual(response.status_code, 200)
        self.engine = "b" * 40
        self.assertEqual(self.client.get("/montara/companion/releases").json["releases"], [])

    def test_unsigned_qa_and_non_notarized_mac_are_never_downloadable(self):
        win = self.entry("windows", "x64", signed=False)
        mac = self.entry("macos", "arm64", notarized=False)
        self.publish([win, mac])
        self.assertEqual(self.client.get("/montara/companion/releases").json["releases"], [])
        self.assertEqual(self.client.get("/montara/companion/releases/download?os=macos&arch=arm64").status_code, 503)

    def test_corrupt_package_fails_sha256_check(self):
        win = self.entry("windows", "x64")
        self.publish([win])
        (self.root / win["filename"]).write_bytes(b"corrupt" * 300)
        response = self.client.get("/montara/companion/releases/download?os=windows&arch=x64")
        self.assertEqual(response.status_code, 503)
        self.assertIn("integrity", response.json["error"].lower())

    def test_symlink_traversal_and_invalid_os_rejected(self):
        win = self.entry("windows", "x64")
        (self.root / win["filename"]).unlink()
        (self.root / win["filename"]).symlink_to(self.root / "outside")
        self.publish([win])
        self.assertEqual(self.client.get("/montara/companion/releases").json["releases"], [])
        for key in ("os=linux&arch=x64", "os=windows&arch=../x64", "os=macos&arch=x86"):
            self.assertEqual(self.client.get("/montara/companion/releases/download?" + key).status_code, 400)

    def test_manifest_is_bound_to_file_not_attacker_url(self):
        win = self.entry("windows", "x64")
        win["filename"] = "../../attack.exe"
        self.publish([win])
        self.assertEqual(self.client.get("/montara/companion/releases").json["releases"], [])
        (self.root / "companion-releases.json").write_text("{broken")
        self.assertEqual(self.client.get("/montara/companion/releases").json["releases"], [])


if __name__ == "__main__":
    unittest.main()
