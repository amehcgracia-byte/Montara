#!/usr/bin/env python3
"""EX-14H-12F: real Stage encoder thread budget vs auto (safe isolated process).

Fixed true Stage recipe/cached media independently for each run.
Changes only encoder invocation arguments inside this lab process, without
modifying the engine source or system FFmpeg. One job at a time, 4 variants.
"""
from __future__ import annotations

from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

BASE = Path(__file__).with_name("ex14h11_stage_real_hevc_export_abba.py")
if not BASE.exists():
    raise SystemExit("STOP: missing sibling Stage harness")
spec = importlib.util.spec_from_file_location("ex14h11_stage_original", BASE)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


@contextmanager
def encoder_threads(number: int):
    from core.stages import export
    old = export.run_reprojected_command
    observed = []

    def invocation(command, *args, **kwargs):
        args_copy = list(command)
        positions = [i for i, token in enumerate(args_copy[:-1]) if token == "-threads"]
        if positions:
            raise RuntimeError("STOP: real Stage encoder unexpectedly has -threads already")
        if "libx264" not in args_copy:
            raise RuntimeError("STOP: not an x264 Stage invocation")
        if "pipe:0" not in args_copy or "-filter_complex" not in args_copy:
            raise RuntimeError("STOP: Stage native encoder recipe unexpected")
        # Output filename is the final command token. Setting -threads just
        # before it applies to output libx264, not to the HEVC decoder.
        new_command = args_copy[:-1] + ["-threads", str(number)] + args_copy[-1:]
        observed.append({
            "threads": number,
            "same_recipe_except_threads": new_command[:-(3)] == args_copy[:-1],
            "codec": "libx264",
            "has_filter_complex": True,
        })
        return old(new_command, *args, **kwargs)

    export.run_reprojected_command = invocation
    try:
        yield observed
    finally:
        export.run_reprojected_command = old


def main():
    if h.capture(["git", "-C", str(h.ROOT), "rev-parse", "--short", "HEAD"]) != "0f9ec03":
        raise RuntimeError("STOP: expected 0f9ec03 engine commit")
    if h.capture(["git", "-C", str(h.ROOT), "status", "--porcelain"]):
        raise RuntimeError("STOP: engine worktree not clean")
    free = shutil.disk_usage("/home/fer").free
    if free < 10 * (1024 ** 3):
        raise RuntimeError("STOP: less than 10 GiB free")
    selected = h.source()
    original_stat = (selected.stat().st_size, selected.stat().st_mtime_ns)
    sys.path.insert(0, str(h.ROOT))

    logical = os.cpu_count()
    affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else []
    # First-phase smoke: four real Stage exports with identical settings,
    # aside from the number of libx264 encoder threads. This is NOT ABBA.
    modes = (2, 0, 1, 4)
    print("EX14H_12F_START " + json.dumps({
        "host_logical_cpu": logical, "available_cpus_affinity": affinity,
        "thread_order": modes,
        "note": "single repetition per variant; screening only, not a winner selection",
    }), flush=True)

    results = []
    with tempfile.TemporaryDirectory(prefix="jupiter_ex14h12f_", dir="/home/fer") as temporary:
        root = Path(temporary)
        for index, threads in enumerate(modes, 1):
            if shutil.disk_usage("/home/fer").free < 10 * (1024 ** 3):
                raise RuntimeError("STOP: less than 10 GiB free during benchmark")
            with encoder_threads(threads) as calls:
                result = h.run_one(root, selected, "A", index)
            if len(calls) != 1 or not calls[0]["same_recipe_except_threads"]:
                raise RuntimeError("STOP: encoder option injection not verifiable")
            if (selected.stat().st_size, selected.stat().st_mtime_ns) != original_stat:
                raise RuntimeError("STOP: original source changed")
            row = {
                "threads": threads,
                "stage_wall_sec": result["wall_sec"],
                "segment_ffmpeg_sec": result["segment_ffmpeg_sec"],
                "rgb_sha256": result["rgb_sha256"],
                "audio_sha256": result["audio_pcm_sha256"],
                "bytes": result["output_bytes"],
                "native_calls": len(result["native_calls"]),
            }
            results.append(row)
            print("EX14H_12F_RUN " + json.dumps(row), flush=True)

    if len({r["audio_sha256"] for r in results}) != 1:
        raise RuntimeError("STOP: output audio changed")
    print("EX14H_12F_SCREENING " + json.dumps({
        "runs": results,
        "audio_pcm_exact": True,
        "quality_note": "H264 may change pixels with thread count; no fidelity approval implied",
        "repetition_note": "Do not choose optimal threads from n=1 each. Later ABBA and concurrent job tests.",
    }, indent=2), flush=True)
    print("EX14H_12F_COMPLETED_TEMP_MEDIA_CLEANED", flush=True)


if __name__ == "__main__":
    main()
