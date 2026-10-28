"""CPU-only FFmpeg experiment B02: frame access versus reusable proxies.

No downloaded/customer media. Creates a small synthetic H.264 test clip.
Run: python experiments/media_optimization/benchmark_b02.py
"""
from __future__ import annotations
import json
import subprocess
import tempfile
import time
from pathlib import Path

FPS = 30
DURATION = 36
TIMES = (2, 7, 12, 17, 22, 27, 32)


def timed(command):
    start = time.perf_counter()
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-1500:]}")
    return round(time.perf_counter() - start, 4)


def benchmark(workdir: Path) -> dict:
    src = workdir / "source.mp4"
    timed(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
           "-i", f"testsrc2=size=640x360:rate={FPS}:duration={DURATION}",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
           "-g", "120", "-keyint_min", "120", "-sc_threshold", "0",
           "-pix_fmt", "yuv420p", str(src)])
    discard = ["-an", "-f", "null", "-"]
    full = timed(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(src),
                  "-vf", "fps=0.2", *discard])
    seeks = [timed(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(t),
                    "-i", str(src), "-frames:v", "1", *discard]) for t in TIMES]
    proxy = workdir / "proxy.mp4"
    build = timed(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                   "-vf", "fps=2,scale=320:180", "-an", "-c:v", "libx264",
                   "-preset", "veryfast", "-crf", "30", str(proxy)])
    proxy_decode = timed(["ffmpeg", "-hide_banner", "-loglevel", "error",
                          "-i", str(proxy), "-vf", "fps=0.2", *discard])
    return {
        "benchmark": "B02-frame-access-proxy-v1",
        "source": "FFmpeg testsrc2, 640x360, H264 30fps, GOP=120, 36 seconds",
        "source_bytes": src.stat().st_size,
        "proxy_bytes": proxy.stat().st_size,
        "source_sparse_pass_s": full,
        "seven_individual_seek_s": round(sum(seeks), 4),
        "individual_seek_times_s": seeks,
        "proxy_creation_s": build,
        "proxy_subsequent_pass_s": proxy_decode,
        "proxy_first_use_total_s": round(build + proxy_decode, 4),
        "warning": ("Process launch overhead is included in each independent seek. "
                    "This synthetic workload does not represent 4K concerts, "
                    "high-motion shots, audio, image accuracy or remote transfers.")
    }


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="montara-b02-") as folder:
        print(json.dumps(benchmark(Path(folder)), indent=2))
