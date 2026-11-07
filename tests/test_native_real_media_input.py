"""Narrow validation of existing real inputs, no footage transferred to CI."""
import tempfile
import unittest
from pathlib import Path

from native_real_media_input import hash_streamed, validate_real_sources


class RealNativeInputs(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.real = self.root / "real"
        self.real.mkdir()
        self.out = self.root / "scratch"
        self.camera_a = self.real / "iphone.MOV"
        self.camera_b = self.real / "sony.MP4"
        self.master = self.real / "master.wav"
        for file, content in ((self.camera_a, b"a"*10000),
                              (self.camera_b, b"b"*8000),
                              (self.master, b"m"*6000)):
            file.write_bytes(content)

    def test_selects_existing_originals_without_writes(self):
        before = {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in self.real.iterdir()}
        cameras, master = validate_real_sources(
            [str(self.camera_a), str(self.camera_b)], str(self.master), self.out)
        self.assertEqual(cameras, [self.camera_a, self.camera_b])
        self.assertEqual(master, self.master)
        self.assertFalse(self.out.exists())
        self.assertEqual(
            {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in self.real.iterdir()}, before)

    def test_rejects_symlink_output(self):
        shortcut = self.root / 'link-to-real'
        shortcut.symlink_to(self.real, target_is_directory=True)
        with self.assertRaises(ValueError):
            validate_real_sources([str(self.camera_a),str(self.camera_b)],str(self.master),shortcut)

    def test_streamed_original_digest(self):
        self.assertEqual(hash_streamed(self.camera_a, block_size=13),
                         hash_streamed(self.camera_a, block_size=8192))
        self.assertNotEqual(hash_streamed(self.camera_a), hash_streamed(self.camera_b))

    def test_rejects_sources_placed_inside_output(self):
        with self.assertRaises(ValueError):
            validate_real_sources(
                [str(self.camera_a), str(self.camera_b)],
                str(self.master), self.real / "scratch")

    def test_rejects_symlink_duplicate_or_missing_inputs(self):
        alias = self.real / "alias.MOV"
        alias.symlink_to(self.camera_a)
        cases = [
            ([str(alias), str(self.camera_b)], str(self.master)),
            ([str(self.camera_a), str(self.camera_a)], str(self.master)),
            ([str(self.camera_a), str(self.camera_b)], str(self.real / "missing.wav")),
            ([str(self.camera_a)], str(self.master)),
        ]
        for cameras, master in cases:
            with self.subTest(cameras=cameras, master=master):
                with self.assertRaises(ValueError):
                    validate_real_sources(cameras, master, self.out)


if __name__ == "__main__":
    unittest.main()
