"""Pure local storage policy; existing Companion /projects behavior unchanged."""
import json
import tempfile
import unittest
from pathlib import Path

from companion.project_storage_policy import (
    InvalidProjectRoot, load_preferred_root, project_folder, suggested_root,
)


class ProjectLocationPolicyTests(unittest.TestCase):
    def test_fallback_in_documents_is_a_suggestion_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            proposed = suggested_root(home=home, environ={})
            self.assertEqual(proposed, home / "Documents" / "Montara")
            self.assertFalse(proposed.exists())

    def test_user_choice_overrides_config_and_document_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            custom = str(Path(tmp) / "ProjectsOnExternalSSD")
            fallback = str(Path(tmp) / "Default")
            self.assertEqual(
                suggested_root(home=Path(tmp), environ={
                    "MONTARA_PROJECTS_ROOT": fallback},
                    preference=custom), Path(custom))
            self.assertEqual(
                suggested_root(home=Path(tmp), environ={
                    "MONTARA_DOCUMENTS_ROOT": fallback}),
                Path(fallback) / "Montara")
            self.assertFalse(Path(custom).exists())

    def test_project_proposal_is_pure_and_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Media" / "Montara"
            folder = project_folder(root, "Concierto ../ Verano")
            self.assertEqual(folder.parent, root)
            self.assertFalse(folder.exists())
            with self.assertRaises(InvalidProjectRoot):
                project_folder(root, "../")
            with self.assertRaises(InvalidProjectRoot):
                suggested_root(home=Path(tmp), environ={},
                               preference="relative/montara")

    def test_preference_is_read_only_and_old_project_mapping_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            legacy = home / "projects.json"
            legacy.write_text('{"abc123":"/old/video/Concierto"}')
            settings = home / "settings.json"
            new_root = str(home / "other-drive")
            settings.write_text(json.dumps({
                "projects_root": new_root, "other_setting": "keep"}))
            before = legacy.read_bytes()
            self.assertEqual(load_preferred_root(settings), new_root)
            self.assertEqual(legacy.read_bytes(), before)
            self.assertEqual(
                load_preferred_root(home / "missing-settings.json"), None)
            settings.unlink()
            settings.symlink_to(legacy)
            with self.assertRaises(InvalidProjectRoot):
                load_preferred_root(settings)


if __name__ == "__main__":
    unittest.main()
