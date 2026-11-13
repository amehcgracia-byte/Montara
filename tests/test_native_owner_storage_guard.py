"""Native Chema desktop storage paths cannot escape a private Owner root."""
import json
import tempfile
import unittest
from pathlib import Path

from urano.native_owner_storage_guard import (
    UnsafeOwnerStorage, verify_owner_storage_config,
)


class NativeOwnerStorageGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="montara-native-storage-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "owner"
        self.root.mkdir(mode=0o700)
        (self.root / "Projects").mkdir()
        (self.root / "Inbox").mkdir()
        self.config = self.root / "config.json"

    def write(self, **settings):
        self.config.write_text(json.dumps(settings))

    def test_fresh_worker_without_config_is_valid(self):
        verify_owner_storage_config(self.root)

    def test_existing_beta_layout_can_be_reused_without_moving_files(self):
        last = self.root / "Projects" / "existing.zuckervid"
        last.mkdir()
        self.write(
            project_roots=[str(self.root / "Projects")],
            inbox_path=str(self.root / "Inbox"),
            source_folders=[str(self.root / "Inbox")],
            last_project_path=str(last),
            ffmpeg_path="/usr/bin/ffmpeg",
        )
        verify_owner_storage_config(self.root)

    def test_rejects_foreign_or_alternative_project_root(self):
        for value in ("/tmp/outsider", str(self.root / "Foreign"),
                      str(self.root / "Projects" / "subfolder")):
            with self.subTest(root=value):
                self.write(project_roots=[value])
                with self.assertRaises(UnsafeOwnerStorage):
                    verify_owner_storage_config(self.root)

    def test_rejects_external_inbox_source_and_resume_locations(self):
        for key in ("source_folders", "inbox_path", "last_project_path"):
            with self.subTest(field=key):
                self.write(**{key: ["/tmp/outsider"] if key == "source_folders"
                              else "/tmp/outsider"})
                with self.assertRaises(UnsafeOwnerStorage):
                    verify_owner_storage_config(self.root)

    def test_rejects_linked_config_and_media_folder(self):
        foreign = Path(self.temp.name) / "foreign"
        foreign.mkdir()
        self.config.symlink_to(foreign / "config.json")
        with self.assertRaises(UnsafeOwnerStorage):
            verify_owner_storage_config(self.root)
        self.config.unlink()
        alias = self.root / "Alias"
        alias.symlink_to(foreign,target_is_directory=True)
        self.write(source_folders=[str(alias)])
        with self.assertRaises(UnsafeOwnerStorage):
            verify_owner_storage_config(self.root)

    def test_rejects_malformed_config(self):
        self.config.write_text("invalid JSON")
        with self.assertRaises(UnsafeOwnerStorage):
            verify_owner_storage_config(self.root)
        self.config.write_text("[]")
        with self.assertRaises(UnsafeOwnerStorage):
            verify_owner_storage_config(self.root)

    def test_rejects_public_data_root_before_accessing_config(self):
        self.root.chmod(0o755)
        with self.assertRaises(UnsafeOwnerStorage):
            verify_owner_storage_config(self.root)


if __name__=="__main__":
    unittest.main()
