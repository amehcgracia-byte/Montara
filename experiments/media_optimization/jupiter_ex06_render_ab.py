#!/usr/bin/env python3
"""JUPITER EX-06 real native 360 A/B, isolated process, no engine edits.

Source is an existing video fixture; outputs are disposable local /tmp MP4s.
This is a render-path smoke/performance comparison, NOT a full product E2E.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "engine")]

import cv2
import numpy as np
from core.spherical_motion import run_reprojected_command
from experiments.media_optimization.jupiter_cpu_linear_optin import cpu_bilinear_optin

SOURCE = ROOT / "tests/fixtures/much-to-me/cam-360.mp4"
OUTPUT = Path(tempfile.gettempdir()) / "montara-jupiter-ex06-ab"
NFRAMES = 30
WIDTH, HEIGHT = 960, 540
SHOT = {
    "yaw": 180., "pitch": -20., "fov": 100.,
    "type": "full_stage", "projection_preset": "linear",
    "runtime_motion_enabled": True, "movement": "pan_right",
}
def cmd(*args):
    return subprocess.run(list(args), check=True, capture_output=True, text=True, timeout=90).stdout

def frames_digest(path: Path):
    out = cmd("ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-map", "0:v:0",
              "-an", "-f", "framehash", "-hash", "sha256", "-")
    return [line.rsplit(",", 1)[-1].strip() for line in out.splitlines()
            if line.strip() and not line.startswith("#")]

def render(label: str, use_linear: bool):
    dest = OUTPUT / (label + ".mp4")
    ffmpeg_args = ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                   "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{WIDTH}x{HEIGHT}",
                   "-r", "30", "-i", "pipe:0", "-an", "-c:v", "libx264",
                   "-preset", "ultrafast", "-crf", "18", "-threads:v", "1",
                   "-pix_fmt", "yuv420p", str(dest)]
    pose = lambda sec: (180. + 0.8 * sec * 30, -20., 100.)
    t = time.perf_counter()
    if use_linear:
        with cpu_bilinear_optin() as metrics:
            run_reprojected_command(ffmpeg_args, str(SOURCE), (640, 320), 0., NFRAMES,
                                    SHOT, hardware_decode=False, remap_backend="cpu",
                                    output_size=(WIDTH, HEIGHT), fps=30, pose_sampler=pose)
        swaps = metrics.cubic_to_linear_calls
        if swaps != NFRAMES:
            raise AssertionError(f"expected {NFRAMES} bilinear remaps, got {swaps}")
    else:
        run_reprojected_command(ffmpeg_args, str(SOURCE), (640, 320), 0., NFRAMES,
                                SHOT, hardware_decode=False, remap_backend="cpu",
                                output_size=(WIDTH, HEIGHT), fps=30, pose_sampler=pose)
        swaps = 0
    return {"seconds": round(time.perf_counter()-t, 3), "bytes": dest.stat().st_size,
            "frames": frames_digest(dest), "swaps": swaps}

def main():
    if not SOURCE.is_file():
        raise SystemExit("Missing video fixture, refusing to run")
    if OUTPUT.exists():
        raise SystemExit(f"Output directory already exists, refusing overwrite: {OUTPUT}")
    OUTPUT.mkdir()
    result = {}
    for label, linear in (("bicubic", False), ("bilinear", True)):
        print("RUN", label, flush=True)
        result[label] = render(label, linear)
    a, b = result["bicubic"], result["bilinear"]
    if not (len(a["frames"]) == len(b["frames"]) == NFRAMES):
        raise AssertionError(f"Frame count differs: {len(a['frames'])}/{len(b['frames'])}")
    report = {"engine": cmd("git", "-C", str(ROOT/"engine"), "rev-parse", "--short", "HEAD").strip(),
              "fixture": SOURCE.name, "frames": NFRAMES, "resolution": [WIDTH, HEIGHT],
              "bicubic_sec": a["seconds"], "bilinear_sec": b["seconds"],
              "bilinear_override_calls": b["swaps"],
              "identical_encoded_frames": sum(x==y for x,y in zip(a["frames"],b["frames"])),
              "outputs": {key: str(OUTPUT / (key+".mp4")) for key in result},
              "notes": "Full reprojection+decode+encode of small real video fixture; not E2E or 4K source."}
    (OUTPUT / "REPORT.json").write_text(json.dumps(report, indent=2) + "\n")
    print("EX06_RENDER_AB=" + json.dumps(report, sort_keys=True), flush=True)

if __name__ == "__main__":
    main()
