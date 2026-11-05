"""Unit regression for FFmpeg SDR color metadata on Windows.

A Windows 10 FFmpeg build wrote colorspace=bt709 but omitted color_transfer
and color_primaries when these were supplied only as encoder output flags.
"""
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


COMPANION_DIR = Path(__file__).resolve().parents[1] / "companion"


class CompanionProxyColorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(COMPANION_DIR))
        spec = importlib.util.spec_from_file_location("companion_color_under_test", COMPANION_DIR / "companion.py")
        cls.comp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.comp)

    def plan(self, hdr=False):
        return {"rotation": 0, "fps": 30, "hdr": hdr, "duration": 2,
                "codec": "h264", "pix_fmt": "yuv420p", "size": [640, 360]}

    def test_sdr_software_tags_frames_not_just_encoder(self):
        with patch.object(self.comp, "HW_H264", False):
            args = self.comp.proxy_command(Path("source.mp4"), Path("output.mp4"), self.plan())
        filters = args[args.index("-vf") + 1]
        self.assertIn("setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709", filters)
        self.assertIn("-color_trc", args)
        self.assertIn("-color_primaries", args)
        self.assertIn("-colorspace", args)

    def test_hdr_without_tonemapping_not_labeled_by_setparams(self):
        with patch.object(self.comp, "HW_H264", False), patch.object(self.comp, "TONEMAP", False):
            args = self.comp.proxy_command(Path("source.mp4"), Path("output.mp4"), self.plan(hdr=True))
        filters = args[args.index("-vf") + 1]
        self.assertNotIn("setparams=", filters)

    def test_hdr_tonemapped_to_sdr_tags_frames(self):
        with patch.object(self.comp, "HW_H264", False), patch.object(self.comp, "TONEMAP", True):
            args = self.comp.proxy_command(Path("source.mp4"), Path("output.mp4"), self.plan(hdr=True))
        filters = args[args.index("-vf") + 1]
        self.assertIn("tonemap=", filters)
        self.assertIn("setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709", filters)


if __name__ == "__main__":
    unittest.main()
