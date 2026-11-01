#!/usr/bin/env python3
"""Bounded, read-only 4-second FFmpeg proxy vs source decode/quality-sample probe.
Does not run EditStage, write video, mutate engine, or touch shared caches.
"""
import json
import shutil
import subprocess
import time
from pathlib import Path

BASE = Path("/home/fer")
PAIRS = (
    ("iPhone", BASE/"lab-clips/originales/IMG_0044.MOV", BASE/"montara-focus-ac-real-01/1-iphone-proxy.mp4"),
    ("Sony", BASE/"lab-clips/originales/C0188.MP4", BASE/"montara-focus-ac-real-01/2-sony-proxy.mp4"),
)
RESULT = BASE/"montara-jupiter-focus-quality-4s-report.json"

def ffmpeg_sample(path: Path, begin: int) -> dict:
    # Original t=10 corresponds to proxy t=0. Seek before input to avoid
    # processing first ten seconds; -t bounds sampling to four seconds.
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
               "-threads", "2", "-ss", str(begin), "-i", str(path),
               "-t", "4", "-an", "-vf", "fps=2,scale=320:-1",
               "-c:v", "mjpeg", "-q:v", "5", "-f", "image2pipe", "pipe:1"]
    started = time.perf_counter()
    res = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, check=False)
    elapsed = time.perf_counter() - started
    if res.returncode:
        raise RuntimeError(f"FFmpeg failed for {path.name}: {res.stderr.decode(errors='replace')[-800:]}")
    return {"path": str(path), "start_sec": begin, "bounded_sec": 4,
            "elapsed_sec": round(elapsed, 3), "jpeg_frames": res.stdout.count(b"\xff\xd8"),
            "jpeg_bytes": len(res.stdout)}

def main():
    if RESULT.exists():
        raise SystemExit("Report already exists; no overwrite: " + str(RESULT))
    if shutil.disk_usage(BASE).free < 5*1024**3:
        raise SystemExit("Less than 5 GiB free; abort")
    for _, original, proxy in PAIRS:
        if not original.is_file() or not proxy.is_file():
            raise SystemExit(f"Missing original/proxy: {original}, {proxy}")
    result = {
        "experiment": "FOCUS quality 4s bounded original-vs-proxy",
        "limitations": ["FFmpeg pipe JPEG extraction only; not the full detector or EditStage",
                        "Original source offset 10 seconds; proxy offset 0 seconds",
                        "Cannot attribute prior 218.846 seconds or validate visual scoring equivalence",
                        "No unbounded full-original FFmpeg run"],
        "samples": []}
    for name, original, proxy in PAIRS:
        pair = {"camera": name, "original": ffmpeg_sample(original, 10),
                "proxy": ffmpeg_sample(proxy, 0)}
        pair["decode_speedup_original_over_proxy"] = round(pair["original"]["elapsed_sec"]/max(.001, pair["proxy"]["elapsed_sec"]), 2)
        result["samples"].append(pair)
        print(json.dumps(pair, indent=2, ensure_ascii=False), flush=True)
    RESULT.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n")
    print("REPORT", RESULT)

if __name__ == "__main__":
    main()
