"""Verify Windows renderer paths without requiring a Windows interpreter."""
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "companion"))
import video_jobs


class RendererPathTests(unittest.TestCase):
    def test_windows_renderer_uses_scripts_python_exe(self):
        with tempfile.TemporaryDirectory() as tmp:
            worker = video_jobs.VideoJobs(Path(tmp))
            self.assertEqual(
                worker.renderer_python(platform="nt"),
                Path(tmp) / "video" / "venv" / "Scripts" / "python.exe",
            )

    def test_linux_and_mac_renderer_stay_unix(self):
        with tempfile.TemporaryDirectory() as tmp:
            worker = video_jobs.VideoJobs(Path(tmp))
            for platform in ("posix", "darwin"):
                self.assertEqual(
                    worker.renderer_python(platform=platform),
                    Path(tmp) / "video" / "venv" / "bin" / "python",
                )


if __name__ == "__main__":
    unittest.main()
