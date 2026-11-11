"""Targeted Windows runner check of Chema's original video_jobs compatibility."""
from __future__ import annotations
import ast
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from companion.windows_video_jobs_compat import patched_windows_video_jobs


class CompanionWindowsVideoJobs(unittest.TestCase):
    def test_windows_python_path_and_safe_termination(self):
        source=Path(os.environ["MONTARA_CHEMA_VIDEO_JOBS_FILE"]).read_text()
        patched=patched_windows_video_jobs(source)
        self.assertIn("taskkill",patched)
        ast.parse(patched)
        ns={"__name__":"video_jobs", "__file__":"video_jobs.py"}
        exec(compile(patched,"video_jobs.py","exec"),ns)
        video=ns["VideoJobs"].__new__(ns["VideoJobs"])
        video.home=Path("C:/MontaraCompanion/video")
        with patch.object(ns["os"],"name","nt"):
            self.assertEqual(video.renderer_python(),
                             video.home/"venv"/"Scripts"/"python.exe")
        with patch.object(ns["os"],"name","posix"):
            self.assertEqual(video.renderer_python(),
                             video.home/"venv"/"bin"/"python")


if __name__=="__main__":
    unittest.main()
