"""I14 lab preflight stays opt-in, local, pinned and secret-independent."""
from pathlib import Path
from unittest import TestCase, mock
import tempfile

from urano_i14_real_engine_lab import checked_engine


class I14LabContract(TestCase):
    def test_missing_engine_api_never_runs_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            with mock.patch('urano_i14_real_engine_lab._git_sha', side_effect=['a'*40,'a'*40]):
                with self.assertRaisesRegex(ValueError,'Engine API'):
                    checked_engine(path,path)

    def test_engine_commit_mismatch_is_rejected_before_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            with mock.patch('urano_i14_real_engine_lab._git_sha',side_effect=['a'*40,'b'*40]):
                with self.assertRaisesRegex(ValueError,'differs'):
                    checked_engine(path,path)

    def test_real_probe_does_not_run_on_import_and_identifies_no_os_isolation(self):
        text=(Path(__file__).resolve().parent/'urano_i14_real_engine_lab.py').read_text()
        self.assertIn('if __name__ == "__main__":',text)
        self.assertIn('"isolation_verified": False',text)
        self.assertIn('TemporaryDirectory(',text)
        self.assertNotIn('sudo ',text)
