"""Baseline of the actual Chema UI—not a second Owner test editor.

These assertions intentionally inspect the original web/ files. Changes in
Chema's main should cause us to re-audit the contracts before reworking the
Owner adapter; nothing here changes the UI or starts an Engine.
"""
from pathlib import Path
import unittest

WEB = Path(__file__).resolve().parents[1] / "web"


class NativeChemaUXBaseline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (WEB / "index.html").read_text(encoding="utf-8")
        cls.editor = (WEB / "montara.js").read_text(encoding="utf-8")
        cls.session = (WEB / "full-session.js").read_text(encoding="utf-8")
        cls.memory = (WEB / "footage-memory.js").read_text(encoding="utf-8")

    def test_native_intro_and_music_video_choices_exist_in_one_document(self):
        for marker in (
            'id="home"', 'class="intro-name"', 'id="mode"',
            'data-intent="music"', 'data-intent="video"',
            'data-platform="youtube"', 'data-platform="reel"',
            'data-platform="show"', 'data-audio-task="song"',
            'data-audio-task="session"', 'data-audio-task="master"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.page)

    def test_new_and_restore_are_in_the_editor_where_chema_put_them(self):
        for marker in (
            'id="newVideo" data-go="mode"',
            'id="sessionResume"', 'id="restoreNote"', 'id="restoreFiles"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.page)
        self.assertIn('function resetFlow()', self.editor)
        self.assertIn('montara-open-edit', self.editor)
        self.assertIn('indexedDB.open', self.memory)
        self.assertIn("api('/montara/recovery/latest')", self.session)

    def test_stage_full_session_keeps_original_new_draft_order(self):
        self.assertIn("async function openFullSession(forVideo = false)", self.session)
        self.assertIn("async function mixSessionForVideo(data)", self.session)
        new = "await api('/wizard/projects/new', {})"
        draft = "await api('/wizard/draft',"
        self.assertIn(new, self.session)
        self.assertIn(draft, self.session)
        self.assertLess(self.session.index(new), self.session.index(draft))

    def test_no_owner_auth_or_project_picker_inserted_in_original_web(self):
        # The Owner adapter is a separate, removable integration layer.
        self.assertNotIn("montaraOwnerProjectsButton", self.page)
        self.assertNotIn("owner-bridge.js", self.page)
        self.assertNotIn("/urano/v1/", self.page)


if __name__ == "__main__":
    unittest.main()
