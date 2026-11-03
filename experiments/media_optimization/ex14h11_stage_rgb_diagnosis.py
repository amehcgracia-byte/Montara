#!/usr/bin/env python3
"""EX14H11G: characterize 360 Stage output variability, baseline A/A vs B/B vs A/B.

Loads the previously proven ExportStage harness. No product or engine edits.
Each project and global cache lives in a transient folder that is cleaned.
"""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import numpy as np

HARNESSED = Path(__file__).with_name("ex14h11_stage_real_hevc_export_abba.py")
if not HARNESSED.is_file():
    raise SystemExit("STOP: sibling Stage harness script missing")
spec = importlib.util.spec_from_file_location("ex14h11_harness", HARNESSED)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


def compare_rgb(left, right):
    def start(p):
        return subprocess.Popen(
            ["ffmpeg", "-v", "error", "-nostdin", "-threads", "2",
             "-i", str(p), "-map", "0:v:0", "-pix_fmt", "rgb24",
             "-f", "rawvideo", "pipe:1"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

    processes = [start(left), start(right)]
    frame_bytes = 1920 * 1080 * 3
    changed, substantial, total_abs, largest = 0, 0, 0, 0

    def read_exact(pipe, n):
        blocks = []
        remaining = n
        while remaining:
            b = pipe.read(remaining)
            if not b:
                break
            blocks.append(b)
            remaining -= len(b)
        return b"".join(blocks)

    try:
        for frame in range(60):
            left_bytes = read_exact(processes[0].stdout, frame_bytes)
            right_bytes = read_exact(processes[1].stdout, frame_bytes)
            if len(left_bytes) != frame_bytes or len(right_bytes) != frame_bytes:
                raise RuntimeError("missing frame during pixel comparison: " + str(frame))
            a = np.frombuffer(left_bytes, dtype=np.uint8).astype(np.int16)
            b = np.frombuffer(right_bytes, dtype=np.uint8).astype(np.int16)
            difference = np.abs(a - b)
            changed += int(np.count_nonzero(difference))
            substantial += int(np.count_nonzero(difference > 8))
            total_abs += int(difference.sum(dtype=np.int64))
            largest = max(largest, int(difference.max()))
        for p in processes:
            if read_exact(p.stdout, 1):
                raise RuntimeError("unexpected extra frames in pixel comparison")
            err = p.stderr.read().decode(errors="replace")
            if p.wait() != 0:
                raise RuntimeError("video comparison failed: " + err[-400:])
        total = frame_bytes * 60
        return {
            "rgb_mae": round(total_abs / total, 6),
            "changed_channels_pct": round(100 * changed / total, 5),
            "channels_delta_gt8_pct": round(100 * substantial / total, 5),
            "max_delta": largest
        }
    finally:
        for p in processes:
            if p.poll() is None:
                p.kill()
            p.wait()


def find_output(project):
    exports = list((project / "exports").rglob("*.mp4"))
    if len(exports) != 1:
        raise RuntimeError(f"Expected exactly one Stage MP4, found {len(exports)}")
    return exports[0]


def main():
    if h.capture(["git", "-C", str(h.ROOT), "rev-parse", "--short", "HEAD"]) != "0f9ec03":
        raise RuntimeError("STOP: worktree commit not expected")
    if h.capture(["git", "-C", str(h.ROOT), "status", "--porcelain"]):
        raise RuntimeError("STOP: dirty worktree")
    if shutil.disk_usage("/home/fer").free < 10 * 1024 ** 3:
        raise RuntimeError("STOP: less than 10 GiB available")
    selected = h.source()
    media_before = (selected.stat().st_size, selected.stat().st_mtime_ns)
    sys.path.insert(0, str(h.ROOT))
    print("EX14H_11G_DIAG_START", flush=True)
    with tempfile.TemporaryDirectory(prefix="jupiter_ex14h11g_", dir="/home/fer") as tmp:
        base = Path(tmp)
        runs = []
        outputs = []
        segments = []
        for i, mode in enumerate(("A", "B", "B", "A"), 1):
            result = h.run_one(base, selected, mode, i)
            output = find_output(base / f"project_{i}_{mode}")
            outputs.append(output)
            cache_files = list((base / f"data_{i}_{mode}" / "Cache" / "segments").glob("*.mp4"))
            if len(cache_files) == 1:
                sh, num = h.sha_stream(cache_files[0], "video")
                result["segment_rgb_sha256"] = sh
                result["segment_rgb_bytes"] = num
            else:
                result["segment_hash_note"] = f"cache segment files found: {len(cache_files)}"
            runs.append(result)
            if (selected.stat().st_size, selected.stat().st_mtime_ns) != media_before:
                raise RuntimeError("STOP: original media changed")
            if shutil.disk_usage("/home/fer").free < 10 * 1024 ** 3:
                raise RuntimeError("STOP: less than 10 GiB available")
        for a, b, title in ((0, 3, "A1_A2"), (1, 2, "B1_B2"),
                            (0, 1, "A1_B1"), (3, 2, "A2_B2")):
            stats = compare_rgb(outputs[a], outputs[b])
            print("EX14H_11G_PAIR " + json.dumps({"pair": title, **stats}), flush=True)
        print("EX14H_11G_SEGMENT_HASHES " + json.dumps(
            [{"run": r["run"], "mode": r["mode"],
              "segment_rgb_sha256": r.get("segment_rgb_sha256"),
              "segment_rgb_bytes": r.get("segment_rgb_bytes"),
              "note": r.get("segment_hash_note")} for r in runs]), flush=True)
        print("EX14H_11G_AUDIO_IDENTICAL " +
              str(len({r["audio_pcm_sha256"] for r in runs}) == 1), flush=True)
    print("EX14H_11G_COMPLETE_OUTPUTS_CLEANED; fidelity not automatically accepted", flush=True)


if __name__ == "__main__":
    main()
