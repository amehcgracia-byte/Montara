"""Regression: a working local renderer must be shipped to every Mac user.

The U21 endpoint imports urano_local_handoff.py at Companion startup. Tests
running from a repository checkout can hide missing installer/ZIP assets.
"""
import ast
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MODULE="urano_local_handoff.py"


class CompanionPackageCompatibility(unittest.TestCase):
    def test_python_import_and_all_delivery_paths_include_module(self):
        server=(ROOT/"app.py").read_text()
        installer=(ROOT/"companion"/"install.sh").read_text()
        command=(ROOT/"companion"/"Install Montara Companion.command").read_text()
        companion=(ROOT/"companion"/"companion.py").read_text()
        self.assertTrue((ROOT/"companion"/MODULE).is_file())
        self.assertIn("from urano_local_handoff import local_render_payload",companion)
        self.assertIn(f'("{MODULE}", 0o644)',server)
        self.assertRegex(installer,r"for f in [^\n]*\burano_local_handoff\.py\b[^\n]*; do")
        self.assertRegex(command,r"for f in [^\n]*\burano_local_handoff\.py\b[^\n]*; do")
        ast.parse(server)
        ast.parse(companion)

    def test_old_video_route_and_new_route_both_present(self):
        src=(ROOT/"companion"/"companion.py").read_text()
        self.assertIn("if self.path == '/video-renders/handoff':",src)
        self.assertIn("if self.path == '/video-renders':",src)
        self.assertIn("video_jobs.start(local, projects, find_original)",src)
        self.assertIn("video_jobs.start(body,projects,find_original)",src)


if __name__=="__main__":
    unittest.main()
