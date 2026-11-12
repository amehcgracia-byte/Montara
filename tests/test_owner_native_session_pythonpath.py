"""The native JM child inherits only a pinned vendor site, not Python's sys.path."""
from __future__ import annotations
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from urano.full_jm_worker import pinned_native_session_site


class NativeMixerPythonPathTests(unittest.TestCase):
    def test_child_receives_reviewed_vendor_site_and_no_user_paths(self):
        with tempfile.TemporaryDirectory(prefix="montara-mixer-path-") as temp:
            root=Path(temp)/"engine"
            site=root/"site"
            site.mkdir(parents=True)
            for module in ("numpy","scipy","numba","librosa","soundfile",
                           "pyloudnorm","matchering"):
                if module=="soundfile":
                    (site/"soundfile.py").write_text("version='pinned'\n")
                else:
                    (site/module).mkdir()
            (site/"montara_vendor_path_marker.py").write_text(
                "value='only-the-bundled-packages'\n",encoding="utf-8")
            expected=str(site.resolve())
            with patch.dict(os.environ,{"PYTHONPATH":"/tmp/untrusted-module-path"}):
                os.environ["PYTHONPATH"]=pinned_native_session_site(root)
                self.assertEqual(os.environ["PYTHONPATH"],expected)
                call=subprocess.run(
                    [sys.executable,"-c",
                     "import montara_vendor_path_marker as m;print(m.value)"],
                    cwd=Path(temp),capture_output=True,text=True,timeout=5,
                    check=True,env=os.environ.copy())
            self.assertEqual(call.stdout.strip(),"only-the-bundled-packages")

    def test_missing_mixer_wheel_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="montara-mixer-missing-") as temp:
            root=Path(temp)
            (root/"site").mkdir()
            with self.assertRaisesRegex(RuntimeError,"Pinned JM mixer libraries unavailable"):
                pinned_native_session_site(root)
        with self.assertRaises(FileNotFoundError):
            pinned_native_session_site(Path(temp)/"deleted-bundle")

    def test_owner_worker_sets_child_environment_before_creating_original_app(self):
        src=(Path(__file__).resolve().parents[1]/"urano"/"full_jm_worker.py").read_text()
        setting='os.environ["PYTHONPATH"] = pinned_native_session_site(engine_root)'
        self.assertIn(setting,src)
        self.assertLess(src.index(setting),src.index("from app import create_montara_app"))


if __name__=="__main__":
    unittest.main()
