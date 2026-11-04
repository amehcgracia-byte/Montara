"""Regression: Companion must drain noisy FFmpeg diagnostics without deadlocking.

Runs a tiny fake FFmpeg child that fills stderr before emitting progress. The
original separate stdout/stderr pipe reader hangs; merged-pipe reader completes.
No media files, GPU, or external network are required.
"""
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


COMPANION = Path(__file__).resolve().parents[1] / "companion"


class ProxyPipeRegressionTests(unittest.TestCase):
    def test_ffmpeg_stderr_over_pipe_capacity(self):
        with tempfile.TemporaryDirectory(prefix="montara-proxy-pipe-") as temp:
            script = textwrap.dedent(r'''
                import os
                import subprocess
                import sys
                from pathlib import Path

                root = Path(sys.argv[2])
                os.environ["MONTARA_COMPANION_HOME"] = str(root / "state")
                sys.path.insert(0, sys.argv[1])
                import companion

                source = root / "synthetic.mp4"
                source.write_bytes(b"simulated media")
                key = "a" * 24
                companion.CACHE.mkdir(parents=True, exist_ok=True)
                companion.sources[key] = source
                companion.jobs[key] = {"status": "working", "progress": 0}
                companion.probe = lambda unused: {}
                companion.plan = lambda unused: {
                    "duration": 2, "fps": 30, "hdr": False, "codec": "h264",
                    "size": [640, 360], "pix_fmt": "yuv420p", "rotation": 0
                }
                child = (
                    "from pathlib import Path; import sys; "
                    "sys.stderr.write(('FFmpeg diagnostics ' + 'x'*160 + '\\n')*1000); "
                    "sys.stderr.flush(); "
                    "print('out_time_us=1000000', flush=True); "
                    "Path(sys.argv[1]).write_bytes(b'valid-proxy')"
                )
                companion.proxy_commands = lambda src, target, plan: [
                    [sys.executable, "-c", child, str(target)]
                ]
                companion.make_proxy(key)
                status = companion.jobs[key]
                assert status["status"] == "ready", status
                assert status["progress"] > 0, status
                assert companion.output_path(key).read_bytes() == b"valid-proxy"
                print("PROXY_PIPE_PASS")
            ''')
            result = subprocess.run(
                [sys.executable, "-c", script, str(COMPANION), temp],
                capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PROXY_PIPE_PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
