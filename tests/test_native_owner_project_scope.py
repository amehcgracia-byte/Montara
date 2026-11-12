"""Native Chema New/Latest path boundary: one worker, multiple saved edits.

This suite uses only temporary directories. It does not create a new Owner
editor, start a worker or require a second Owner catalog.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from urano.native_owner_project_scope import (
    UnsafeNativeProject,
    verified_native_project,
)


class PrivateNativeChemaProjects(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.a = self.root / "owner-a"
        self.b = self.root / "owner-b"
        for root in (self.a, self.b):
            (root / "Projects").mkdir(parents=True)
        self.a_old = self.write(self.a, "first.zuckervid")
        self.a_new = self.write(self.a, "recent.zuckervid")
        self.b_secret = self.write(self.b, "private.zuckervid")

    def write(self, root: Path, name: str):
        folder = root / "Projects" / name
        folder.mkdir()
        (folder / "project.json").write_text(
            json.dumps({"name": name, "inputs": {"videos": []}}),
            encoding="utf-8",
        )
        return folder

    def test_native_new_and_latest_both_stay_in_one_owner_workspace(self):
        self.assertEqual(
            verified_native_project(self.a, str(self.a_old)), self.a_old
        )
        self.assertEqual(
            verified_native_project(self.a, str(self.a_new)), self.a_new
        )
        # Native Chema is free to keep an old edit while opening a new one.
        self.assertTrue((self.a_old / "project.json").exists())

    def test_other_owner_project_never_passes(self):
        with self.assertRaises(UnsafeNativeProject):
            verified_native_project(self.a, str(self.b_secret))
        self.assertEqual(
            verified_native_project(self.b, str(self.b_secret)), self.b_secret
        )

    def test_path_escape_and_relative_paths_rejected(self):
        for candidate in (
            str(self.a_new) + "/../first.zuckervid",
            str(self.a),
            str(self.a / "Projects"),
            "Projects/recent.zuckervid",
            "",
            str(self.root),
            str(self.a_new / "project.json"),
            str(self.a_new) + "\\x00suffix",
        ):
            with self.subTest(candidate=candidate):
                with self.assertRaises(UnsafeNativeProject):
                    verified_native_project(self.a, candidate)

    def test_symlink_project_and_metadata_rejected(self):
        link = self.a / "Projects" / "linked.zuckervid"
        link.symlink_to(self.b_secret, target_is_directory=True)
        with self.assertRaises(UnsafeNativeProject):
            verified_native_project(self.a, str(link))
        folder = self.a / "Projects" / "linked-metadata.zuckervid"
        folder.mkdir()
        (folder / "project.json").symlink_to(
            self.b_secret / "project.json"
        )
        with self.assertRaises(UnsafeNativeProject):
            verified_native_project(self.a, str(folder))

    def test_corrupt_or_missing_metadata_rejected(self):
        broken = self.write(self.a, "broken.zuckervid")
        (broken / "project.json").write_text("not JSON", encoding="utf-8")
        with self.assertRaises(UnsafeNativeProject):
            verified_native_project(self.a, str(broken))
        (broken / "project.json").unlink()
        with self.assertRaises(UnsafeNativeProject):
            verified_native_project(self.a, str(broken))
        (broken / "project.json").write_text("[]", encoding="utf-8")
        with self.assertRaises(UnsafeNativeProject):
            verified_native_project(self.a, str(broken))


if __name__ == "__main__":
    unittest.main()
