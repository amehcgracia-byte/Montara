"""Montara: reproducible CPU-only proxy and scene-change benchmark.

Generates synthetic footage; no customer media, cloud or GPU.
Requires ffmpeg/ffprobe. Outputs JSON. Results are not performance guarantees.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

SCENE_SECONDS = 2
SCENE_COLORS = ("red", "blue", "green", "yellow")
PTS = re.compile(r"pts_time:([0-9.]+)")


def run(args: list[str]) -> tuple[float, subprocess.CompletedProcess[str]]:
    start = time.perf_counter()
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    elapsed = time.perf_counter() - start
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed: {result.stderr[-1500:]}")
    return elapsed, result


def create_input(target: Path, fps: int = 24, size: str = "640x360") -> None:
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for color in SCENE_COLORS:
        command += ["-f", "lavfi", "-i", f"color=c={color}:s={size}:r={fps}:d={SCENE_SECONDS}"]
    filt = "".join(f"[{i}:v]" for i in range(len(SCENE_COLORS))) + f"concat=n={len(SCENE_COLORS)}:v=1:a=0[v]"
    command += ["-filter_complex", filt, "-map", "[v]", "-c:v", "libx264",
                "-preset", "ultrafast", "-crf", "18", "-pix_fmt", "yuv420p", str(target)]
    run(command)


def detect(path: Path, vf: str) -> tuple[float, list[float]]:
    elapsed, result = run(["ffmpeg", "-hide_banner", "-i", str(path), "-vf",
                           vf + ",showinfo", "-an", "-f", "null", "-"])
    return elapsed, [float(m.group(1)) for line in result.stderr.splitlines()
                     if "showinfo" in line and (m := PTS.search(line))]


def matches(events: list[float], expected: list[float], tolerance: float = .15) -> dict:
    used = set()
    correct = 0
    for target in expected:
        possible = [i for i, t in enumerate(events)
                    if i not in used and abs(t-target) <= tolerance]
        if possible:
            used.add(possible[0])
            correct += 1
    return {"hits": correct, "expected": len(expected), "detected": len(events),
            "precision": round(correct / len(events), 3) if events else 0,
            "recall": round(correct / len(expected), 3) if expected else 1}


def benchmark(workdir: Path) -> dict:
    src = workdir / "synthetic_original.mp4"
    proxy = workdir / "proxy_360p.mp4"
    create_input(src)
    generation_s, _ = run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                           "-vf", "scale=480:270", "-c:v", "libx264", "-preset", "veryfast",
                           "-crf", "28", "-an", str(proxy)])
    full_s, full_events = detect(src, r"select=gt(scene\,0.12)")
    sampled_s, sampled_events = detect(src, r"fps=2,select=gt(scene\,0.12)")
    expected = [float(i * SCENE_SECONDS) for i in range(1, len(SCENE_COLORS))]
    return {"benchmark": "B01-scene-sampling-v1", "source_type": "synthetic",
            "duration_seconds": len(SCENE_COLORS) * SCENE_SECONDS,
            "original_bytes": src.stat().st_size, "proxy_bytes": proxy.stat().st_size,
            "proxy_ratio": round(proxy.stat().st_size / src.stat().st_size, 4),
            "proxy_generation_seconds": round(generation_s, 4),
            "full": {"seconds": round(full_s, 4), "events": full_events,
                     **matches(full_events, expected)},
            "sampled_2fps": {"seconds": round(sampled_s, 4), "events": sampled_events,
                            **matches(sampled_events, expected)},
            "note": "Obvious synthetic cuts; not representative of music videos. Timings vary by environment."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="Optional JSON report")
    args = parser.parse_args()
    for binary in ("ffmpeg", "ffprobe"):
        if not shutil.which(binary):
            parser.error(f"{binary} must be installed")
    with tempfile.TemporaryDirectory(prefix="montara-b01-") as folder:
        report = benchmark(Path(folder))
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
