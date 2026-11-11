"""I56 original Chema three-part release matrix and source-hash contract."""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from urano.jm_bundle_manifest import (
    build_pinned_chema_manifest, verify_pinned_chema_manifest,
    verify_jm_bundle_files,
)
from urano.jm_private_proxy_overlay import patched_original_resumable_upload

EDITOR="14cce126137a0ef30a987351ff35b750f54473bd"
ENGINE="b867b3c72af8fe4685b487bcf1e09ffcc2a7c82b"
MIXER="f15ff91c1b80fc5f157099dcd9451d958d553ae6"
OLD_ENGINE="b5e48317ef85225f901adc69af8cc17aa8146880"


class PinnedChemaProductMatrixTests(unittest.TestCase):
    def test_real_chema_gitlinks_and_source_pin_when_repo_present(self):
        repo=os.environ.get("MONTARA_REVIEWED_JM_GIT_REPO")
        if not repo:
            self.skipTest("Reviewed Chema git objects not present in this runner")
        matrix=build_pinned_chema_manifest(Path(repo),EDITOR,
                                           private_preview_limit_mib=2048)
        self.assertEqual(matrix["engine_commit"],ENGINE)
        self.assertEqual(matrix["mixer_commit"],MIXER)
        self.assertEqual(matrix["private_proxy_limit_mib"],2048)
        verify_pinned_chema_manifest(
            matrix,expected_editor_commit=EDITOR,
            expected_engine_commit=ENGINE,
            expected_private_preview_limit_mib=2048)
        with self.assertRaises(ValueError):
            verify_pinned_chema_manifest(
                matrix,expected_editor_commit=EDITOR,
                expected_engine_commit=OLD_ENGINE,
                expected_private_preview_limit_mib=2048)
        with tempfile.TemporaryDirectory() as t:
            from subprocess import run,PIPE
            original=run(["git","-C",repo,"show",EDITOR+":resumable_upload.py"],
                         check=True,stdout=PIPE).stdout.decode()
            root=Path(t)
            (root/"app.py").write_text("# original app placeholder")
            (root/"web").mkdir()
            (root/"web/montara.js").write_text("// editor placeholder")
            (root/"resumable_upload.py").write_text(
                patched_original_resumable_upload(original))
            verify_jm_bundle_files(root,matrix)
            (root/"resumable_upload.py").write_text(original)
            with self.assertRaises(ValueError):
                verify_jm_bundle_files(root,matrix)

    def test_fail_closed_on_changed_sha_malformed_keys_and_policy(self):
        base={
            "schema":1,"editor_commit":EDITOR,"engine_commit":ENGINE,
            "mixer_commit":MIXER,"private_proxy_limit_mib":2048,
            "patched_resumable_sha256":"a"*64,
        }
        for modified in (
            {**base,"engine_commit":OLD_ENGINE},
            {**base,"editor_commit":EDITOR[:-1]+"f"},
            {**base,"schema":True},
            {**base,"private_proxy_limit_mib":True},
            {**base,"private_proxy_limit_mib":8192},
            {**base,"patched_resumable_sha256":"wrong"},
            {**base,"unexpected":"injected"},
        ):
            with self.subTest(modified=modified),self.assertRaises(ValueError):
                verify_pinned_chema_manifest(
                    modified,expected_editor_commit=EDITOR,
                    expected_engine_commit=ENGINE,
                    expected_private_preview_limit_mib=2048)


if __name__=="__main__":
    unittest.main()
