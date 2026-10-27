"""B03: measure cold/warm proxy preparation using Montara's actual local proxy code.

No cloud/GPU needed. Builds a disposable synthetic 1280x720 H.264 clip and calls
local_media.proxies.prepare twice. The warm call should reuse existing proxy.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

from local_media.proxies import prepare


def build_sample(path: Path, duration: int = 12):
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-f", "lavfi", "-i", f"testsrc2=size=1280x720:rate=30:duration={duration}",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24",
        "-pix_fmt", "yuv420p", str(path),
    ], check=True)


def run(work: Path) -> dict:
    original = work / "source.mp4"
    cache = work / "proxy-cache"
    build_sample(original)
    start = time.perf_counter()
    cold = prepare(original, cache)
    cold_seconds = time.perf_counter() - start
    proxy = Path(cold["proxy"])
    proxy_mtime = proxy.stat().st_mtime_ns
    start = time.perf_counter()
    warm = prepare(original, cache)
    warm_seconds = time.perf_counter() - start
    assert cold["source_id"] == warm["source_id"]
    assert proxy.stat().st_mtime_ns == proxy_mtime, "Warm call unexpectedly regenerated proxy"
    assert cold["original_stamp"] == warm["original_stamp"]
    return {
        "benchmark": "B03-existing-proxy-cache-v1",
        "source": "synthetic 12s, 1280x720, H264, 30fps",
        "source_bytes": original.stat().st_size,
        "proxy_bytes": proxy.stat().st_size,
        "proxy_to_original_ratio": round(proxy.stat().st_size / original.stat().st_size, 5),
        "cold_seconds": round(cold_seconds, 4),
        "warm_seconds": round(warm_seconds, 4),
        "speed_ratio_cold_over_warm": round(cold_seconds / max(warm_seconds, 1e-9), 2),
        "proxy_source_id": cold["source_id"],
        "limitations": [
            "Synthetic short sample, not 4K concert footage.",
            "Warm call reuses the cache; it does not read/decode proxy frames.",
            "No human comparison of picture quality or timecode/frame accuracy.",
            "Includes ffprobe/ffmpeg process startup overhead.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="montara-b03-") as tmp:
        result = run(Path(tmp))
    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    print(payload, end="")
