#!/usr/bin/env python3
"""EX-14H-12D: isolate x264 reproducibility/speed from real 360 projected frames.

1 genuine isolated Stage A render (HEVC 360 original, 60 frames, master audio)
capturing every remapped BGR frame losslessly to a temporary raw stream.
2 x264 encodes with threads=2 and 2 with threads=0, alternating A-B-B-A.
Stream / hash / inspect outputs; no engine edits, changes to global FFmpeg,
project originals, or persisted assets. CPU performance includes raw disk read.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

HARNESSED = Path(__file__).with_name("ex14h11_stage_real_hevc_export_abba.py")
if not HARNESSED.exists():
    raise SystemExit("STOP: sibling EX14H11 harness missing")
spec = importlib.util.spec_from_file_location("verified_stage_harness", HARNESSED)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)

WIDTH, HEIGHT, COUNT = 1920, 1080, 60
FRAME_BYTES = WIDTH * HEIGHT * 3
RAW_BYTES = FRAME_BYTES * COUNT


def render_capture(root, source, raw_path):
    import core.spherical_motion as sm
    original = sm.cv2.remap
    captured = [0]
    sha = hashlib.sha256()
    # Do not open outside isolated temp. Write only 373,248,000 bytes.
    with raw_path.open("xb", buffering=1024 * 1024) as dst:
        def wrapped(*args, **kwargs):
            pixels = original(*args, **kwargs)
            if pixels is None:
                pixels = kwargs.get("dst")
                if pixels is None and len(args) > 6:
                    pixels = args[6]
            if pixels is None or pixels.shape != (HEIGHT, WIDTH, 3):
                raise RuntimeError("STOP: invalid output BGR shape")
            view = memoryview(pixels)
            if not view.c_contiguous:
                raise RuntimeError("STOP: output not contiguous")
            block = view.cast("B")
            dst.write(block)
            sha.update(block)
            captured[0] += 1
            return pixels
        sm.cv2.remap = wrapped
        try:
            result = h.run_one(root, source, "A", 1)
        finally:
            sm.cv2.remap = original
    if captured[0] != COUNT or raw_path.stat().st_size != RAW_BYTES:
        raise RuntimeError(f"STOP: captured {captured[0]} frames, {raw_path.stat().st_size} bytes")
    return result, sha.hexdigest()


def run_encoder(binary, raw_path, output, threads):
    command = [binary, "-hide_banner", "-v", "error", "-nostdin",
               "-y", "-f", "rawvideo", "-pixel_format", "bgr24",
               "-video_size", f"{WIDTH}x{HEIGHT}", "-framerate", "30",
               "-i", str(raw_path), "-frames:v", str(COUNT),
               "-an", "-c:v", "libx264", "-preset", "veryfast",
               "-b:v", "8000000", "-pix_fmt", "yuv420p",
               "-threads", str(threads), "-movflags", "+faststart",
               str(output)]
    begin = time.perf_counter()
    done = subprocess.run(command, capture_output=True, text=True, timeout=240)
    elapsed = time.perf_counter() - begin
    if done.returncode != 0:
        raise RuntimeError("isolated encode failed: " + done.stderr[-1000:])
    meta = h.probe(output, frames=True)
    if int(meta.get("nb_read_frames") or 0) != COUNT:
        raise RuntimeError("STOP: isolated encoded frame count differs")
    rgb, rgb_bytes = h.sha_stream(output, "video")
    if rgb_bytes != RAW_BYTES:
        raise RuntimeError("STOP: decoded RGB has wrong byte count")
    hash_file = hashlib.sha256()
    with output.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            hash_file.update(block)
    return {
        "threads": threads, "wall_sec": round(elapsed, 3),
        "size_bytes": output.stat().st_size,
        "encoded_sha256": hash_file.hexdigest(),
        "decoded_rgb_sha256": rgb,
        "decoded_frames": COUNT,
    }


def main():
    if h.capture(["git", "-C", str(h.ROOT), "rev-parse", "--short", "HEAD"]) != "0f9ec03":
        raise RuntimeError("STOP: expected experimental engine 0f9ec03")
    if h.capture(["git", "-C", str(h.ROOT), "status", "--porcelain"]):
        raise RuntimeError("STOP: experimental engine worktree is dirty")
    if shutil.disk_usage("/home/fer").free < 10 * 1024**3:
        raise RuntimeError("STOP: less than 10 GiB free")

    selected_source = h.source()
    stat_before = (selected_source.stat().st_size, selected_source.stat().st_mtime_ns)
    sys.path.insert(0, str(h.ROOT))
    binary = shutil.which("ffmpeg")
    if not binary:
        raise RuntimeError("STOP: ffmpeg missing")
    ffmpeg_version = subprocess.check_output([binary, "-version"], text=True).splitlines()[0]
    print("EX14H_12D_START " + json.dumps({
        "ffmpeg": binary, "version": ffmpeg_version,
        "clip": "HEVC original 360 Stage 2s, 60 frames",
        "raw_bgr_bytes": RAW_BYTES,
        "encode_variants": ["threads2", "threads0", "threads0", "threads2"],
        "note": "isolated encode from captured BGR, NOT full Stage alternative"}), flush=True)

    with tempfile.TemporaryDirectory(prefix="jupiter_ex14h12d_", dir="/home/fer") as temp:
        base = Path(temp)
        raw = base / "preencoder_1920x1080_bgr24_60f.raw"
        stage_result, input_sha = render_capture(base, selected_source, raw)
        print("EX14H_12D_RAW " + json.dumps({
            "sha256": input_sha, "bytes": raw.stat().st_size,
            "stage_export_wall_sec_instrumented": stage_result["wall_sec"],
            "stage_decoded_rgb_sha256": stage_result["rgb_sha256"],
            "warning": "do not benchmark instrumented Stage time"}), flush=True)

        results = []
        for index, threads in enumerate((2, 0, 0, 2), 1):
            if shutil.disk_usage("/home/fer").free < 10 * 1024**3:
                raise RuntimeError("STOP: disk free below 10 GiB")
            name = "A" if threads == 2 else "B"
            result = run_encoder(binary, raw, base / f"isolated_{index}_{name}.mp4", threads)
            result.update({"run": index, "mode": name})
            print("EX14H_12D_ENCODER " + json.dumps(result), flush=True)
            results.append(result)

        def equals(a, b, name):
            return {"pair": name,
                    "compressed_identical": results[a]["encoded_sha256"] == results[b]["encoded_sha256"],
                    "decoded_identical": results[a]["decoded_rgb_sha256"] == results[b]["decoded_rgb_sha256"]}
        pairs = [equals(0, 3, "A1_A2"), equals(1, 2, "B1_B2"),
                 equals(0, 1, "A1_B1"), equals(3, 2, "A2_B2")]
        a_times = [r["wall_sec"] for r in results if r["mode"] == "A"]
        b_times = [r["wall_sec"] for r in results if r["mode"] == "B"]
        avg_a, avg_b = sum(a_times)/len(a_times), sum(b_times)/len(b_times)
        print("EX14H_12D_RESULT " + json.dumps({
            "pairs": pairs,
            "threads2_mean_sec": round(avg_a, 3),
            "threads_auto_mean_sec": round(avg_b, 3),
            "threads_auto_gain_pct": round(100*(avg_a-avg_b)/avg_a, 2),
            "hypothesis": "If repeated isolated x264 outputs are identical while Stage A/A differs, investigate Stage filters/options/process conditions rather than blaming remap",
            "caveat": "A/B thread variants may differ due to codec threading; changes in encoded image must be judged by quality and requirements",
        }, indent=2), flush=True)

    if (selected_source.stat().st_size, selected_source.stat().st_mtime_ns) != stat_before:
        raise RuntimeError("STOP: original source unexpectedly modified")
    print("EX14H_12D_COMPLETED_TEMP_MEDIA_CLEANED", flush=True)


if __name__ == "__main__":
    main()
