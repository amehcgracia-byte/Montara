"""Read-only real-footage preflight acceptance without shipping actual footage."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from urano.real_media_preflight import PreflightError, evaluate, inspect_file


def ffprobe_result(path):
    source = Path(path[-1]).name
    if source == "master.wav":
        streams = [{"codec_type": "audio", "codec_name": "pcm_s16le", "channels": 2,
                    "sample_rate": "48000"}]
    else:
        streams = [
            {"codec_type": "video", "codec_name": "hevc" if source.endswith(".mov") else "h264",
             "width": 3840, "height": 2160, "avg_frame_rate": "30000/1001",
             "r_frame_rate": "30/1", "pix_fmt": "yuv420p", "side_data_list": []},
            {"codec_type": "audio", "codec_name": "aac", "channels": 2,
             "sample_rate": "48000"}]
    return type("Result", (), {"stdout": json.dumps(
        {"format": {"duration": "19.83"}, "streams": streams})})()


class RealSamplePreflightTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "originals"
        self.work = self.root / "isolated-work"
        self.source.mkdir()
        self.work.mkdir()
        for f in ("iphone.mov", "sony.mp4", "master.wav"):
            (self.source / f).write_bytes(b"FAKE_MEDIA_HEADER_ONLY")

    @patch("urano.real_media_preflight.subprocess.run", side_effect=lambda argv, **_: ffprobe_result(argv))
    def test_reports_actual_probe_metadata_and_never_modifies_originals(self, run):
        before = {p.name: p.read_bytes() for p in self.source.iterdir()}
        report = evaluate(self.source, self.work, ["iphone.mov", "sony.mp4"],
                          "master.wav", minimum_free_gb=0)
        self.assertTrue(report["pass"])
        self.assertEqual(report["source_count"], 3)
        self.assertEqual(report["cameras"][0]["videos"][0]["codec"], "hevc")
        self.assertEqual(report["cameras"][0]["videos"][0]["fps_avg"], 29.97)
        self.assertEqual(report["master"]["audios"][0]["sample_rate"], "48000")
        self.assertFalse(report["writes"])
        self.assertFalse(report["export_tested"])
        self.assertFalse(report["companion_tested"])
        self.assertEqual({p.name: p.read_bytes() for p in self.source.iterdir()}, before)
        self.assertEqual(list(self.work.iterdir()), [])
        self.assertEqual(run.call_count, 3)

    def test_source_and_work_must_not_overlap(self):
        with self.assertRaises(PreflightError):
            evaluate(self.source, self.source, ["iphone.mov"], None, 0)
        with self.assertRaises(PreflightError):
            evaluate(self.root, self.work, ["iphone.mov"], None, 0)

    @patch("urano.real_media_preflight.subprocess.run", side_effect=lambda argv, **_: ffprobe_result(argv))
    def test_rejects_traversal_absent_file_and_symlink_escape(self, run):
        (self.source / "alias.mov").symlink_to(self.source / "iphone.mov")
        for sample in ("../isolated-work/camera.mp4", "/etc/passwd",
                       "alias.mov", "missing.mp4", ".env"):
            with self.subTest(sample=sample), self.assertRaises(PreflightError):
                inspect_file(self.source.resolve(), sample)
        self.assertEqual(run.call_count, 0)

    @patch("urano.real_media_preflight.subprocess.run", side_effect=lambda argv, **_: ffprobe_result(argv))
    def test_rejects_insufficient_disk_without_render(self, run):
        report = evaluate(self.source, self.work, ["iphone.mov"],
                          None, minimum_free_gb=1_000_000)
        self.assertFalse(report["pass"])
        self.assertIn("Insufficient", report["warning"])
        self.assertEqual(list(self.work.iterdir()), [])

    @patch("urano.real_media_preflight.subprocess.run", side_effect=lambda argv, **_: ffprobe_result(argv))
    def test_master_must_have_audio(self, run):
        with self.assertRaises(PreflightError):
            evaluate(self.source, self.work, ["iphone.mov"],
                     "sony.mp4", minimum_free_gb=0) if False else self._no_audio()

    def _no_audio(self):
        with patch("urano.real_media_preflight.subprocess.run", return_value=type(
                "Result", (), {"stdout": json.dumps({"format": {"duration": "20"},
                                                     "streams": [{"codec_type": "video", "width": 640}]})})()):
            evaluate(self.source, self.work, ["iphone.mov"], "sony.mp4", 0)


if __name__ == "__main__":
    unittest.main()
