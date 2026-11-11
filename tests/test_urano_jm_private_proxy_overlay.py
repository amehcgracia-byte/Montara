"""Opt-in private proxy quota overlay on ORIGINAL Chema upload routes."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from urano.jm_private_proxy_overlay import (
    DEFAULT_PRIVATE_PROXY_MIB, _MARKERS, patched_original_resumable_upload,
    private_proxy_limit_mib, stage_private_jm_resumable,
)

def verified_jm_upload_fixture() -> str:
    # Minimal executable structure of Chema's reviewed source anchors.
    # The full original branch source is tested in a separate real JM lab.
    return (
        "def register_resumable_upload(app, data_root, classify):\\n"
        + _MARKERS["limit"] + "\\n"
        + "    def chunk_size(data):\\n"
        + _MARKERS["chunk"] + "\\n"
        + "    def upload_limits():\\n"
        + _MARKERS["limits"] + "\\n"
        + "    def upload_create():\\n"
        + "        name = 'camera.small.mp4'\\n"
        + "        size = 1\\n"
        + "        body = {}\\n"
        + _MARKERS["size"] + "\\n"
        + _MARKERS["error"] + "\\n"
    )



class ChemaProxyOverlayTests(unittest.TestCase):
    def test_original_source_unchanged_and_patch_compiles(self):
        source=verified_jm_upload_fixture()
        original=Path(__file__).resolve()
        candidate=patched_original_resumable_upload(source)
        self.assertNotEqual(source,candidate)
        self.assertIn("max_original_file_bytes=limit",candidate)
        self.assertIn("admitted_limit = proxy_limit if preview_file else limit",
                      candidate)
        compile(candidate,str(original), "exec")
        self.assertEqual(verified_jm_upload_fixture(),source)

    def test_source_drift_fails_closed(self):
        src=verified_jm_upload_fixture()
        for change in ("limit", "chunk", "size", "limits", "error"):
            from urano.jm_private_proxy_overlay import _MARKERS
            bad=src.replace(_MARKERS[change],"bad_alternative",1)
            with self.subTest(change=change),self.assertRaises(ValueError):
                patched_original_resumable_upload(bad)

    def test_opt_in_immutable_destination_not_source(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/"reviewed-original.py"
            source.write_text(verified_jm_upload_fixture())
            target=Path(temp)/"immutable-jm"/"resumable_upload.py"
            before=source.read_bytes()
            stage_private_jm_resumable(source,target)
            self.assertTrue(target.is_file())
            self.assertEqual(source.read_bytes(),before)
            with self.assertRaises(FileExistsError):
                stage_private_jm_resumable(source,target)
            with self.assertRaises(ValueError):
                stage_private_jm_resumable(source,source)

    def test_private_quota_bounds(self):
        for bad in (0,255,4097,"2048",True,None):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                private_proxy_limit_mib(bad)
        self.assertEqual(private_proxy_limit_mib(),2048)


if __name__=="__main__":
    unittest.main()
