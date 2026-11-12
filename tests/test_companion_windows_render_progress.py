"""Regression for WinError 5 while rendering native Stage progress.

The real MP4/segment writes stay strict; only advisory progress snapshots
may be skipped after bounded retries on Windows.
"""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "companion" / "local_video.py"
spec = importlib.util.spec_from_file_location("montara_companion_local_video", MODULE)
video = importlib.util.module_from_spec(spec)
spec.loader.exec_module(video)


class NativeProgressWindowsTests(unittest.TestCase):
    def test_windows_transient_permission_error_retries_and_succeeds(self):
        events = []

        def writer(path, payload):
            events.append((path, payload))
            if len(events) < 3:
                raise PermissionError(5, "Access denied")

        with patch.object(video.time, "sleep") as sleep:
            self.assertTrue(video.write_render_progress(writer, Path("progress.json"), {"progress": 0.4}, windows=True))
        self.assertEqual(len(events), 3)
        self.assertEqual(sleep.call_count, 2)

    def test_windows_persistent_progress_lock_is_nonfatal(self):
        def writer(path, payload):
            raise PermissionError(5, "Access denied")

        with patch.object(video.os, "name", "nt"), patch.object(video.time, "sleep") as sleep:
            self.assertFalse(video.write_render_progress(writer, Path("progress.json"), {"progress": 0.5}, windows=True))
        self.assertEqual(sleep.call_count, 4)

    def test_nonwindows_permission_denied_is_not_swallowed(self):
        def writer(path, payload):
            raise PermissionError(13, "Access denied")

        with self.assertRaises(PermissionError):
            video.write_render_progress(writer, Path("progress.json"), {"progress": 0.7}, windows=False)

    def test_non_permission_failure_is_never_swallowed(self):
        def writer(path, payload):
            raise OSError(28, "Disk full")

        with self.assertRaises(OSError):
            video.write_render_progress(writer, Path("progress.json"), {"progress": 0.7}, windows=True)


if __name__ == "__main__":
    unittest.main()
