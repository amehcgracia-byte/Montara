#!/usr/bin/env python3
"""EX-14H-12B: time real Stage 360 map generation vs OpenCV remap.

Deliberately DOES NOT attribute residual wall time to decoder/encoder. Benchmarks
a real ExportStage shot, isolated per-run caches, no engine file edits, safe cleanup.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import resource
import shutil
import sys
import tempfile
import time

HARNESSED = Path(__file__).with_name("ex14h11_stage_real_hevc_export_abba.py")
if not HARNESSED.exists():
    raise SystemExit("STOP: sibling EX14H11 harness required")

spec = importlib.util.spec_from_file_location("ex14h11_verified_harness", HARNESSED)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


@contextmanager
def observe_mapping():
    import core.spherical_motion as sm

    original_map = sm.reproject_maps
    original_remap = sm.cv2.remap
    stats = defaultdict(lambda: {"calls": 0, "seconds": 0.0})
    # Timing wrapper preserves args/kwargs, return value, exceptions and
    # original outputs. The process is dedicated to this one lab run.
    def measured_map(*args, **kwargs):
        begin = time.perf_counter()
        try:
            return original_map(*args, **kwargs)
        finally:
            x = stats["map_generation"]
            x["calls"] += 1
            x["seconds"] += time.perf_counter() - begin

    def measured_remap(*args, **kwargs):
        begin = time.perf_counter()
        try:
            return original_remap(*args, **kwargs)
        finally:
            x = stats["opencv_remap"]
            x["calls"] += 1
            x["seconds"] += time.perf_counter() - begin

    sm.reproject_maps = measured_map
    sm.cv2.remap = measured_remap
    try:
        yield stats
    finally:
        sm.reproject_maps = original_map
        sm.cv2.remap = original_remap


def resource_snapshot():
    self_usage = resource.getrusage(resource.RUSAGE_SELF)
    child_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {
        "cpu_user_sec": self_usage.ru_utime + child_usage.ru_utime,
        "cpu_system_sec": self_usage.ru_stime + child_usage.ru_stime,
        "max_rss_python_kib": self_usage.ru_maxrss,
        "max_rss_child_kib": child_usage.ru_maxrss,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("ab", "abba"), default="ab")
    options = parser.parse_args()

    if h.capture(["git", "-C", str(h.ROOT), "rev-parse", "--short", "HEAD"]) != "0f9ec03":
        raise RuntimeError("STOP: worktree commit must be 0f9ec03")
    if h.capture(["git", "-C", str(h.ROOT), "status", "--porcelain"]):
        raise RuntimeError("STOP: worktree has uncommitted changes")
    if shutil.disk_usage("/home/fer").free < 10 * 1024**3:
        raise RuntimeError("STOP: less than 10 GiB free")
    selected = h.source()
    original_stat = (selected.stat().st_size, selected.stat().st_mtime_ns)
    sys.path.insert(0, str(h.ROOT))
    modes = ("A", "B") if options.mode == "ab" else ("A", "B", "B", "A")
    results = []
    print("EX14H_12B_START " + json.dumps({"modes": modes,
          "note": "map/remap timings exclusive only; residual includes decode/encode waits and all Stage overhead"}), flush=True)

    with tempfile.TemporaryDirectory(prefix="jupiter_ex14h12b_", dir="/home/fer") as temp:
        for index, mode in enumerate(modes, 1):
            before = resource_snapshot()
            with observe_mapping() as prof:
                output = h.run_one(Path(temp), selected, mode, index)
            after = resource_snapshot()

            if (selected.stat().st_size, selected.stat().st_mtime_ns) != original_stat:
                raise RuntimeError("STOP: original video metadata changed")
            if shutil.disk_usage("/home/fer").free < 10 * 1024**3:
                raise RuntimeError("STOP: less than 10 GiB free")

            maps = prof.get("map_generation") or {"calls": 0, "seconds": 0.0}
            remap = prof.get("opencv_remap") or {"calls": 0, "seconds": 0.0}
            if maps["calls"] == 0 or remap["calls"] != 60:
                raise RuntimeError(f"STOP: expected real CPU remap 60 frames; maps={maps} remap={remap}")
            map_sec = maps["seconds"]
            remap_sec = remap["seconds"]
            measured = map_sec + remap_sec
            segment = float(output["segment_ffmpeg_sec"])
            if measured > segment + 0.1:
                raise RuntimeError("STOP: measured mapping exceeds observed segment wall")
            report = {
                "mode": mode, "run": index,
                "stage_wall_sec": output["wall_sec"],
                "segment_ffmpeg_sec": segment,
                "map_calls": maps["calls"],
                "map_sec": round(map_sec, 4),
                "map_ms_per_call": round(1000 * map_sec/maps["calls"], 3),
                "remap_calls": remap["calls"],
                "remap_sec": round(remap_sec, 4),
                "remap_ms_per_frame": round(1000 * remap_sec/remap["calls"], 3),
                "map_plus_remap_pct_segment": round(100 * measured/segment, 2),
                "segment_residual_sec_unattributed": round(segment - measured, 4),
                "cpu_user_plus_children_sec": round(after["cpu_user_sec"] - before["cpu_user_sec"], 3),
                "cpu_system_plus_children_sec": round(after["cpu_system_sec"] - before["cpu_system_sec"], 3),
                "rss_python_peak_kib": after["max_rss_python_kib"],
                "rss_child_max_kib": after["max_rss_child_kib"],
                "rgb_sha256": output["rgb_sha256"],
                "audio_pcm_sha256": output["audio_pcm_sha256"],
            }
            print("EX14H_12B_RUN " + json.dumps(report, ensure_ascii=False), flush=True)
            results.append(report)

    if len({x["audio_pcm_sha256"] for x in results}) != 1:
        raise RuntimeError("STOP: audio PCM mismatch")

    summary = {}
    for mode in ("A", "B"):
        group = [x for x in results if x["mode"] == mode]
        summary[mode] = {
            key: round(sum(x[key] for x in group) / len(group), 4)
            for key in ("stage_wall_sec", "segment_ffmpeg_sec", "map_sec",
                        "remap_sec", "map_plus_remap_pct_segment",
                        "segment_residual_sec_unattributed")
        }
    if len(modes) == 4:
        summary["stage_gain_pct"] = round(
            100 * (summary["A"]["stage_wall_sec"]-summary["B"]["stage_wall_sec"])/
            summary["A"]["stage_wall_sec"], 2)
    print("EX14H_12B_SUMMARY " + json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    print("EX14H_12B_COMPLETED_TEMP_FILES_CLEANED", flush=True)


if __name__ == "__main__":
    main()
