#!/usr/bin/env python3
"""JUPITER EX-14H-10: native 360 HEVC pipeline A/B/B/A, no Stage product mutation."""
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path("/home/fer/zucker-videos-ex14h09")
ORIGINALS = Path("/home/fer/lab-clips/originales")
EXPECTED_HEAD = "25f66a9"
FPS, FRAMES, WIDTH, HEIGHT = 30, 60, 1920, 1080


def command_output(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE).strip()


def probe(path):
    try:
        raw = command_output([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height,nb_read_frames",
            "-of", "json", str(path)
        ])
        stream = json.loads(raw)["streams"][0]
        return stream
    except (subprocess.CalledProcessError, ValueError, KeyError, IndexError):
        return None


def choose_source():
    if not ORIGINALS.is_dir():
        raise RuntimeError("Source directory not available; no render started")
    candidates = []
    for p in sorted(ORIGINALS.iterdir()):
        if not p.is_file() or p.suffix.lower() not in (".mp4", ".mov", ".mkv"):
            continue
        meta = probe(p)
        if (meta and meta.get("codec_name") == "hevc"
                and (meta.get("width"), meta.get("height")) == (3840, 1920)):
            candidates.append(p)
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one HEVC 3840x1920 source, found {len(candidates)}; no render started")
    return candidates[0]


def verify_output(path):
    meta = json.loads(command_output([
        "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,nb_read_frames", "-of", "json", str(path)
    ]))["streams"][0]
    if tuple(int(meta[k]) for k in ("width", "height", "nb_read_frames")) != (WIDTH, HEIGHT, FRAMES):
        raise RuntimeError(f"Unexpected output video: {meta}")
    decoder = subprocess.Popen([
        "ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-map", "0:v:0",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    digest = hashlib.sha256()
    byte_count = 0
    assert decoder.stdout
    while True:
        buf = decoder.stdout.read(1024 * 1024)
        if not buf:
            break
        digest.update(buf)
        byte_count += len(buf)
    error = decoder.stderr.read().decode(errors="replace") if decoder.stderr else ""
    if decoder.wait() != 0 or byte_count != WIDTH * HEIGHT * 3 * FRAMES:
        raise RuntimeError(f"Bad decoded video, size={byte_count}, stderr={error[-500:]}")
    return digest.hexdigest()


def main():
    if command_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"]) != EXPECTED_HEAD:
        raise RuntimeError("Unexpected engine commit; no render started")
    if command_output(["git", "-C", str(ROOT), "status", "--porcelain"]):
        raise RuntimeError("Dirty engine worktree; no render started")
    source = choose_source()
    sys.path.insert(0, str(ROOT))
    from core.spherical_motion import run_reprojected_command

    shot = {
        "type": "stage", "yaw": 180.0, "pitch": -30.0,
        "fov": 100.0, "projection_preset": "linear",
        "runtime_motion_enabled": True,
    }

    def pose(seconds):
        return 180.0 + 0.3 * round(seconds * FPS), -30.0, 100.0

    results = []
    print("EX14H_10_SOURCE_VERIFIED HEVC_3840x1920", flush=True)
    with tempfile.TemporaryDirectory(prefix="jupiter_ex14h10_") as temp:
        for i, mode in enumerate(("A", "B", "B", "A"), 1):
            enabled = (mode == "B")
            output = Path(temp) / f"run_{i}_{mode}.mp4"
            encoder = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "rawvideo", "-pix_fmt", "bgr24", "-s:v", f"{WIDTH}x{HEIGHT}",
                "-r", str(FPS), "-i", "pipe:0", "-an", "-c:v", "libx264",
                "-preset", "veryfast", "-crf", "23", "-threads", "2",
                "-pix_fmt", "yuv420p", str(output)
            ]
            print(f"RUN_{i}_{mode}_START", flush=True)
            start = time.perf_counter()
            run_reprojected_command(
                encoder, str(source), (3840, 1920), 840.0, FRAMES,
                shot, pose_sampler=pose, hardware_decode=False,
                remap_backend="cpu", output_size=(WIDTH, HEIGHT), fps=FPS,
                fast_wrap=enabled, smart_unwrap=enabled
            )
            wall = time.perf_counter() - start
            result = {
                "run": i, "mode": mode, "wall_s": round(wall, 3),
                "bytes": output.stat().st_size,
                "decoded_sha256": verify_output(output)
            }
            results.append(result)
            print("RUN_DONE " + json.dumps(result), flush=True)
    a = [x["wall_s"] for x in results if x["mode"] == "A"]
    b = [x["wall_s"] for x in results if x["mode"] == "B"]
    avg_a, avg_b = sum(a)/len(a), sum(b)/len(b)
    exact = len({x["decoded_sha256"] for x in results}) == 1
    report = {
        "engine": EXPECTED_HEAD, "base": "affe97a", "frames": FRAMES,
        "output": [WIDTH, HEIGHT], "order": "ABBA",
        "A_mean_s": round(avg_a, 3), "B_mean_s": round(avg_b, 3),
        "gain_pct": round(100 * (avg_a - avg_b) / avg_a, 2),
        "identical_decoded_frames": exact, "runs": results,
        "scope": "isolated native 360 pipeline, not Stage E2E"
    }
    print("EX14H_10_RESULT " + json.dumps(report, indent=2), flush=True)
    if not exact:
        raise RuntimeError("EX14H_10_FAIL_FRAME_DIFFERENCE")
    print("EX14H_10_PASS_EXACT_DECODED_FRAMES", flush=True)


if __name__ == "__main__":
    main()
