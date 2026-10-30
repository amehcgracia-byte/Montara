#!/usr/bin/env python3
"""OPT-08: CPU-only encoder-routing proposal tests (no FFmpeg, no engine edits).

Models the proposed routing contract; NOT a test of the existing engine.
"""
import unittest

def proposed_encoder_order(platform, videotoolbox_available, force_cpu=False):
    if force_cpu or platform != "darwin" or not videotoolbox_available:
        return ("libx264",)
    return ("h264_videotoolbox", "libx264")

def simulate_attempts(order, fails):
    attempted=[]
    for encoder in order:
        attempted.append(encoder)
        if encoder not in fails:
            return attempted
    raise RuntimeError("all encoders failed")

class EncoderSelectionContract(unittest.TestCase):
    def test_linux_without_videotoolbox(self):
        order=proposed_encoder_order("linux", False)
        self.assertEqual(simulate_attempts(order, set()), ["libx264"])
    def test_macos_hardware_success(self):
        self.assertEqual(simulate_attempts(proposed_encoder_order("darwin", True),set()),["h264_videotoolbox"])
    def test_macos_hardware_fallback(self):
        self.assertEqual(simulate_attempts(proposed_encoder_order("darwin", True),{"h264_videotoolbox"}),["h264_videotoolbox","libx264"])
    def test_force_cpu(self):
        for platform in ("linux","darwin","win32"):
            self.assertEqual(proposed_encoder_order(platform,True,True),("libx264",))
    def test_macos_missing_hw(self):
        self.assertEqual(proposed_encoder_order("darwin",False),("libx264",))
    def test_windows(self):
        self.assertEqual(proposed_encoder_order("win32",False),("libx264",))

if __name__=="__main__":
    unittest.main(verbosity=2)
