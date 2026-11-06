"""Real panorama proxy: projection, complete sphere, audio and failure safety."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))
import companion
from spherical_proxy import preserve_panorama


class PanoramaProxyTests(unittest.TestCase):
    def test_panorama_plan_and_ordinary_camera(self):
        def info(w, h, side=()):
            return {"streams": [{"codec_type": "video", "width": w, "height": h,
                                 "side_data_list": list(side)}]}
        self.assertTrue(companion.plan(info(4096, 2048))["panorama"])
        self.assertTrue(companion.plan(info(640, 320, [{"side_data_type": "Spherical Mapping"}]))["panorama"])
        self.assertFalse(companion.plan(info(3840, 2160))["panorama"])
        self.assertIn("skip", companion.plan(info(1920, 1920, [{"side_data_type": "Spherical Mapping"}])))

    def test_real_proxy_retains_projection_audio_and_original(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder / "sphere.mp4"
            subprocess.run([companion.FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i",
                            "testsrc2=size=4096x2048:rate=24:duration=1", "-f", "lavfi", "-i",
                            "sine=frequency=440:duration=1", "-c:v", "libx264", "-preset", "ultrafast",
                            "-crf", "10", "-c:a", "aac", "-shortest", str(source)], check=True)
            original = hashlib.sha256(source.read_bytes()).digest()
            key = "d" * 24
            with patch.object(companion, "CACHE", folder), patch.object(companion, "HW_H264", False), patch.object(companion, "HW_SCALE", False):
                companion.sources[key] = source
                companion.jobs[key] = {"status": "working", "progress": 0}
                try:
                    companion.make_proxy(key)
                    self.assertEqual(companion.jobs[key]["status"], "ready", companion.jobs[key])
                    proxy = companion.output_path(key)
                    data = companion.probe(proxy)
                    video = next(s for s in data["streams"] if s["codec_type"] == "video")
                    self.assertEqual((video["width"], video["height"]), (2048, 1024))
                    self.assertTrue(any("spherical" in str(d).lower() for d in video["side_data_list"]))
                    self.assertTrue(any(s["codec_type"] == "audio" for s in data["streams"]))
                    self.assertLess(abs(float(data["format"]["duration"]) - 1), .15)
                    self.assertLess(proxy.stat().st_size, source.stat().st_size)
                    # The engine recognizes it, and different viewpoints remain available.
                    previous_path = sys.path[:]
                    try:
                        sys.path.insert(0, str(ROOT / "engine"))
                        from core.media_validation import projection
                    finally:
                        sys.path[:] = previous_path
                    self.assertEqual(projection(data, video["width"], video["height"]), "equirect")
                    views = []
                    for yaw in (0, 90):
                        views.append(subprocess.check_output([companion.FFMPEG, "-v", "error", "-i", str(proxy),
                                     "-vf", f"v360=input=equirect:output=flat:yaw={yaw}:w=160:h=90",
                                     "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]))
                    self.assertNotEqual(views[0], views[1])
                    self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), original)
                finally:
                    companion.sources.pop(key, None)
                    companion.jobs.pop(key, None)

    def test_missing_metadata_never_publishes_a_flat_proxy(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pending.mp4"
            path.write_bytes(b"unmodified")
            def fake_inject(src, dst, metadata, console):
                Path(dst).write_bytes(b"flat")
            with patch("spatialmedia.metadata_utils.inject_metadata", fake_inject):
                with self.assertRaises(RuntimeError):
                    preserve_panorama(path, lambda _: {"streams": [{"codec_type": "video", "width": 2048, "height": 1024}]})
            self.assertEqual(path.read_bytes(), b"unmodified")
            self.assertFalse(path.with_name("pending.spherical.mp4").exists())


if __name__ == "__main__":
    unittest.main()
