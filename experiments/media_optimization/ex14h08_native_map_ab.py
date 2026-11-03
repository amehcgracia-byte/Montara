#!/usr/bin/env python3
"""EX-14H-08: 1080p geometry-only A/B of EX-07/13 (NO video decoding).

Read-only: imports the pinned baseline and lab code, generates deterministic
poses, verifies exact arrays, and times map generation. Does not touch media.
Run ONLY after confirming the shared VM is idle.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

import numpy as np


BASE_SHA = "ff9baf45aef07f0e9f16c489cf5cbd15acbd1b2f"
EXPECTED_CHANGES = {
    "core/spherical_motion.py",
    "tests/test_ex06_cpu_interpolation.py",
    "tests/test_ex07_fast_wrap.py",
    "tests/test_ex13_smart_unwrap.py",
}
ROOT = Path("/home/fer/montara-jupiter/engine")
LAB = Path("/home/fer/zucker-videos-ex06")
SOURCE_SIZE = (3840, 1920)
OUTPUT_SIZE = (1920, 1080)
FRAMES = 60
ROUNDS = 3
SHOT = {
    "yaw": 180.0, "pitch": -30.0, "fov": 100.0, "roll": 0,
    "type": "full_stage", "projection_preset": "linear",
    "runtime_motion_enabled": True,
}


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], text=True, timeout=15
    ).strip()


def preflight() -> dict:
    if not ROOT.is_dir() or not LAB.is_dir():
        raise RuntimeError("Missing baseline engine or experimental worktree")
    baseline_sha = git(ROOT, "rev-parse", "HEAD")
    lab_sha = git(LAB, "rev-parse", "HEAD")
    lab_branch = git(LAB, "branch", "--show-current")
    common = git(LAB, "merge-base", BASE_SHA, "HEAD")
    diff = set(filter(None, git(LAB, "diff", "--name-only", BASE_SHA, "HEAD").splitlines()))
    if baseline_sha != BASE_SHA or common != BASE_SHA:
        raise RuntimeError("Pinned baseline/ancestry changed: stop")
    if lab_branch != "fernando/ex06-engine-lab" or diff != EXPECTED_CHANGES:
        raise RuntimeError("Lab branch or changed-file set diverges: stop")
    for repo in (ROOT, LAB):
        subprocess.run(["git", "-C", str(repo), "diff", "--quiet"], check=True)
        subprocess.run(["git", "-C", str(repo), "diff", "--cached", "--quiet"], check=True)

    processes = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            name = (proc / "comm").read_text().strip()
            if name in ("ffmpeg", "ffprobe"):
                processes.append(name)
        except OSError:
            pass
    load1 = os.getloadavg()[0]
    if processes or load1 > 5:
        raise RuntimeError("Shared VM appears busy: stop without running benchmark")
    return {"base_sha": baseline_sha[:12], "lab_sha": lab_sha[:12],
            "lab_branch": lab_branch, "load1": round(load1, 2),
            "external_ffmpeg_processes": len(processes)}


def load_modules():
    sys.path.insert(0, str(ROOT))
    from core import spherical_motion as base
    path = LAB / "core" / "spherical_motion.py"
    spec = importlib.util.spec_from_file_location("ex14h08_lab_motion", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load experimental reprojector")
    lab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lab)
    return base, lab


def pose(index: int) -> tuple[float, float, float]:
    # EXACTLY the synthetic pose series from EX-14H-06.
    return 180.0 + 0.3 * index, -30.0, 100.0


def quantiles_ms(values: list[float]) -> dict:
    sorted_values = sorted(values)
    return {
        "median": round(statistics.median(values), 3),
        "mean": round(statistics.fmean(values), 3),
        "p95_nearest_rank": round(sorted_values[int(.95 * (len(values)-1))], 3),
        "sum_ms": round(sum(values), 3),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true",
                        help="Explicit opt-in: compute 1080p projection maps")
    args = parser.parse_args()
    print("=== EX-14H-08 · GEOMETRY A/B / NO VIDEO ===", flush=True)
    guard = preflight()
    print("PREFLIGHT", json.dumps(guard, sort_keys=True), flush=True)
    if not args.execute:
        print("PREFLIGHT_ONLY; pass --execute when VM is reserved/idle")
        return

    base, lab = load_modules()
    cases = {
        "A_base": (base.reproject_maps, {}),
        "B_fast_wrap": (lab.reproject_maps, {"fast_wrap": True}),
        "C_smart_unwrap": (lab.reproject_maps, {"smart_unwrap": True}),
        "D_both": (lab.reproject_maps, {"fast_wrap": True, "smart_unwrap": True}),
    }
    timings = {name: [] for name in cases}
    mismatches = []
    wall_start = time.perf_counter()

    # Warm-up once per implementation, excluded from benchmark and fidelity check.
    for fn, flags in cases.values():
        fn(SOURCE_SIZE, OUTPUT_SIZE, SHOT, pose(0), **flags)

    # Rotate execution order, reducing systematic order/warm-cache bias.
    variants = list(cases)
    for run in range(ROUNDS):
        order = variants[run:] + variants[:run]
        for i in range(FRAMES):
            reference = None
            outputs = {}
            # Compute all four for the identical pose.
            for name in order:
                fn, flags = cases[name]
                start = time.perf_counter_ns()
                outputs[name] = fn(SOURCE_SIZE, OUTPUT_SIZE, SHOT, pose(i), **flags)
                timings[name].append((time.perf_counter_ns() - start) / 1e6)
            reference = outputs["A_base"]
            for name in variants[1:]:
                if not all(np.array_equal(a, b) for a, b in zip(reference, outputs[name])):
                    mismatches.append({"round": run + 1, "frame": i, "variant": name})
                    if len(mismatches) >= 10:
                        raise RuntimeError("Too many exact-map mismatches; aborting")
        print(f"ROUND_{run+1}_DONE", flush=True)

    baseline = statistics.median(timings["A_base"])
    result = {
        "base_sha": guard["base_sha"], "lab_sha": guard["lab_sha"],
        "source_dimensions": SOURCE_SIZE, "output_dimensions": OUTPUT_SIZE,
        "poses": FRAMES, "rounds": ROUNDS,
        "wall_s": round(time.perf_counter() - wall_start, 3),
        "time_stats_ms": {k: quantiles_ms(v) for k, v in timings.items()},
        "vs_baseline_median_pct": {
            k: round((1 - statistics.median(v)/baseline)*100, 2)
            for k, v in timings.items() if k != "A_base"
        },
        "exact_mismatches": mismatches,
        "scope": "map generation ONLY; no HEVC decoding, OpenCV remap or encoding",
    }
    print("RESULT", json.dumps(result, indent=2), flush=True)
    if mismatches:
        raise SystemExit("EX14H_08_FAIL_EXACT_MAPS")
    print("EX14H_08_PASS_EXACT_MAPS")


if __name__ == "__main__":
    main()
