"""SATURNO-14: exact native decoder versus the previous preflight control.

Only decodes one 278-frame window; never imports or changes the engine.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(tempfile.gettempdir()) / "saturno14-decoder"
EXPECTED_ENGINE = "60a7b7e9a39077b36f45057811abd6a833a168ef"

def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def run(args, timeout=120):
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError(f"Command failed {p.returncode}: {p.stderr[-2000:]}")
    return p.stdout

def decode(command, width, height):
    hashes = []
    frame_bytes = width * height * 3
    started = time.perf_counter()
    with tempfile.TemporaryFile() as err:
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=err) as p:
            expired = threading.Event()
            def stop():
                expired.set()
                p.kill()
            timer = threading.Timer(120, stop)
            timer.start()
            try:
                while True:
                    frame = bytearray()
                    while len(frame) < frame_bytes:
                        block = p.stdout.read(frame_bytes - len(frame))
                        if not block:
                            break
                        frame.extend(block)
                    if not frame:
                        break
                    if len(frame) != frame_bytes:
                        raise RuntimeError(f"Partial BGR frame: {len(frame)}/{frame_bytes}")
                    hashes.append(hashlib.sha256(frame).hexdigest())
                code = p.wait(timeout=10)
                err.seek(0)
                stderr = err.read().decode(errors="replace")
                if code or expired.is_set():
                    raise RuntimeError(f"Decoder exit={code}, timeout={expired.is_set()}: {stderr[-2000:]}")
            finally:
                timer.cancel()
                if p.poll() is None:
                    p.kill()
                p.wait()
    return {"command": command, "frame_count": len(hashes),
            "frame_hashes": hashes, "elapsed_sec": time.perf_counter() - started,
            "stderr": stderr[-2000:]}

def compare(a, b):
    bad = [i for i, (x, y) in enumerate(zip(a["frame_hashes"], b["frame_hashes"])) if x != y]
    return {"frames_A": a["frame_count"], "frames_B": b["frame_count"],
            "exact": a["frame_hashes"] == b["frame_hashes"],
            "same_index_exact": sum(x == y for x, y in zip(a["frame_hashes"], b["frame_hashes"])),
            "first_different_index": bad[0] if bad else (min(a["frame_count"], b["frame_count"]) if a["frame_count"] != b["frame_count"] else None),
            "different_indices": bad}

def main():
    OUT.mkdir(exist_ok=True)
    report = {"experiment": "SATURNO-14", "status": "NOT_RUN",
              "scope": "one real 360 window; decoder only; no reprojection/encoding",
              "tokens_measured": None, "tokens_reason": "No chat token telemetry available"}
    try:
        engine = run(["git", "-C", str(ROOT / "engine"), "rev-parse", "HEAD"]).strip()
        assert engine == EXPECTED_ENGINE, "Engine pin changed"
        report["engine_commit"] = engine
        report["ffmpeg_version"] = run(["ffmpeg", "-version"]).splitlines()[0]
        baseline = json.loads((ROOT / "experiments/saturno_10/packet_results_40886014059.json").read_text())["report"]
        row = next(s for s in baseline["sources"] if s["source"].endswith("cam-360.mp4"))
        source = ROOT / "tests/fixtures/much-to-me/cam-360.mp4"
        assert sha(source) == row["source_sha256"], "Original source changed"
        target = OUT / "cam-360.mp4"
        package_command = [str(target) if a == row["target"] else str(source) if a == row["source"] else a for a in row["command"]]
        run(package_command)
        assert sha(target) == row["target_sha256"], "Package recipe output changed"
        plan = json.loads((ROOT / "experiments/saturno_10/stage_edit_plan.json").read_text())
        segment = plan["segments"][2]
        start = float(segment["clip_start_sec"])
        frames = max(1, round(float(segment["duration_sec"]) * 30))
        assert frames == 278
        probe = json.loads(run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams", "-of", "json", str(source)]))["streams"][0]
        width, height = int(probe["width"]), int(probe["height"])
        report.update(source_sha256=sha(source), package_sha256=sha(target),
            package_command=package_command, segment_index_one_based=3,
            clip_start_sec=start, requested_frames=frames, source_size=[width, height],
            plan_sha256=sha(ROOT / "experiments/saturno_10/stage_edit_plan.json"),
            all_video_gops_retained=True)
        def command(path, control=False):
            if control:
                # Exact recipe from packet_preflight.window_hash(native_360=True).
                return ["ffmpeg", "-nostdin", "-v", "error", "-threads", "2", "-ss", str(start),
                        "-i", str(path), "-vf", "fps=30,format=bgr24", "-frames:v", str(frames),
                        "-pix_fmt", "bgr24", "-map", "0:v:0", "-an",
                        "-fps_mode", "passthrough", "-f", "rawvideo", "-"]
            # Exact CPU command from spherical_motion.py:187-188, except binary spelling.
            return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-threads", "2",
                    "-ss", str(start), "-i", str(path), "-vf", "fps=30,format=bgr24",
                    "-an", "-frames:v", str(frames), "-f", "rawvideo", "pipe:1"]
        results = {}
        for label, path, control in (
                ("A_exact", source, False), ("A_repeat_exact", source, False),
                ("B_exact", target, False), ("A_previous", source, True), ("B_previous", target, True)):
            results[label] = decode(command(path, control), width, height)
        report["decodes"] = results
        report["comparisons"] = {
            "AA_exact": compare(results["A_exact"], results["A_repeat_exact"]),
            "AB_exact": compare(results["A_exact"], results["B_exact"]),
            "AB_previous": compare(results["A_previous"], results["B_previous"]),
            "A_exact_vs_previous": compare(results["A_exact"], results["A_previous"]),
            "B_exact_vs_previous": compare(results["B_exact"], results["B_previous"]),
        }
        assert all(r["frame_count"] > 0 for r in results.values()), "Empty decode"
        report["all_requested_counts"] = all(r["frame_count"] == frames for r in results.values())
        if not report["comparisons"]["AA_exact"]["exact"]:
            report["status"] = "UNSTABLE_EXACT_AA"
        elif not report["comparisons"]["AB_exact"]["exact"]:
            report["status"] = "EXACT_DECODER_AB_DIFFERS"
        else:
            report["status"] = "EXACT_DECODER_AB_IDENTICAL"
        # Previous-control command differs in several flags, not only fps_mode.
        # A discrepancy localizes a command-path difference; it does not establish
        # which individual flag causes it.
        report["interpretation_limit"] = "Command-level comparison only; no single-flag causal attribution; no pose/reprojection tested."
    except Exception as exc:
        report.update(status="OPERATIONAL_ERROR", error=repr(exc))
    finally:
        (OUT / "REPORT.json").write_text(json.dumps(report, indent=2))
        print("SATURNO14_REPORT_BEGIN", flush=True)
        print(json.dumps(report, separators=(",", ":")), flush=True)
        print("SATURNO14_REPORT_END", flush=True)
        brief = {k: v for k, v in report.items() if k not in {"decodes", "package_command"}}
        print("SATURNO14_SUMMARY=" + json.dumps(brief, separators=(",", ":")), flush=True)
    # This is a diagnostic, not the full-plan equivalence gate.
    return 1 if report["status"] == "OPERATIONAL_ERROR" else 0

if __name__ == "__main__":
    raise SystemExit(main())
