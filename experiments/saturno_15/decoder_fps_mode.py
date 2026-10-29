"""SATURNO-15: isolate -fps_mode passthrough in native 360 decode.
No engine edits, reprojection, rendering, or full exports.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.saturno_14.decoder_window import sha, run, decode, compare, EXPECTED_ENGINE

OUT = Path(tempfile.gettempdir()) / "saturno15-decoder"

def main():
    OUT.mkdir(exist_ok=True)
    report = {"experiment": "SATURNO-15", "status": "NOT_RUN",
              "question": "Does adding only -fps_mode passthrough eliminate the A/B 360 decoder mismatch?",
              "tokens_measured": None}
    try:
        engine = run(["git", "-C", str(ROOT / "engine"), "rev-parse", "HEAD"]).strip()
        assert engine == EXPECTED_ENGINE, "Engine pin changed"
        report["engine_commit"] = engine
        report["ffmpeg_version"] = run(["ffmpeg", "-version"]).splitlines()[0]
        previous = json.loads((ROOT / "experiments/saturno_14/results_40902865517.json").read_text())["report"]
        baseline = json.loads((ROOT / "experiments/saturno_10/packet_results_40886014059.json").read_text())["report"]
        row = next(s for s in baseline["sources"] if s["source"].endswith("cam-360.mp4"))
        source = ROOT / "tests/fixtures/much-to-me/cam-360.mp4"
        target = OUT / "cam-360.mp4"
        assert sha(source) == row["source_sha256"] == previous["source_sha256"]
        package_command = [str(target) if a == row["target"] else str(source) if a == row["source"] else a for a in row["command"]]
        run(package_command)
        assert sha(target) == row["target_sha256"] == previous["package_sha256"]
        plan_path = ROOT / "experiments/saturno_10/stage_edit_plan.json"
        assert sha(plan_path) == previous["plan_sha256"]
        seg = json.loads(plan_path.read_text())["segments"][2]
        start = str(float(seg["clip_start_sec"]))
        frames = round(float(seg["duration_sec"]) * 30)
        assert frames == previous["requested_frames"] == 278 and start == str(previous["clip_start_sec"])
        width, height = previous["source_size"]
        def cmd(path, passthrough=False):
            argv = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-threads", "2",
                    "-ss", start, "-i", str(path), "-vf", "fps=30,format=bgr24",
                    "-an", "-frames:v", str(frames)]
            if passthrough:
                argv += ["-fps_mode", "passthrough"]
            return argv + ["-f", "rawvideo", "pipe:1"]
        results = {}
        for label, path, flag in [
            ("A_exact", source, False), ("B_exact", target, False),
            ("A_passthrough", source, True), ("A_repeat_passthrough", source, True),
            ("B_passthrough", target, True)]:
            results[label] = decode(cmd(path, flag), width, height)
        report["decodes"] = results
        report["comparisons"] = {
            "AB_exact": compare(results["A_exact"], results["B_exact"]),
            "AA_passthrough": compare(results["A_passthrough"], results["A_repeat_passthrough"]),
            "AB_passthrough": compare(results["A_passthrough"], results["B_passthrough"]),
            "A_exact_vs_passthrough": compare(results["A_exact"], results["A_passthrough"]),
            "B_exact_vs_passthrough": compare(results["B_exact"], results["B_passthrough"]),
        }
        report["previous_exact_reproduced"] = all(
            results[k]["frame_hashes"] == previous["decodes"][k]["frame_hashes"]
            for k in ("A_exact", "B_exact"))
        report["all_requested_counts"] = all(x["frame_count"] == 278 for x in results.values())
        if not report["all_requested_counts"]:
            report["status"] = "INCOMPLETE_FRAMES"
        elif not report["previous_exact_reproduced"]:
            report["status"] = "BASELINE_NOT_REPRODUCED"
        elif not report["comparisons"]["AA_passthrough"]["exact"]:
            report["status"] = "UNSTABLE_PASSTHROUGH_AA"
        elif report["comparisons"]["AB_passthrough"]["exact"]:
            report["status"] = "PASSTHROUGH_AB_EXACT"
        else:
            report["status"] = "PASSTHROUGH_AB_DIFFERS"
        report["interpretation_limit"] = "One window only. Equality under this control does not certify the full render or selective GOP savings."
    except Exception as e:
        report.update(status="OPERATIONAL_ERROR", error=repr(e))
    finally:
        (OUT / "REPORT.json").write_text(json.dumps(report, indent=2))
        print("SATURNO15_REPORT_BEGIN", flush=True)
        print(json.dumps(report, separators=(",", ":")), flush=True)
        print("SATURNO15_REPORT_END", flush=True)
        print("SATURNO15_SUMMARY=" + json.dumps({
            "status": report["status"],
            "previous_exact_reproduced": report.get("previous_exact_reproduced"),
            "all_requested_counts": report.get("all_requested_counts"),
            "comparisons": {k: {j: v[j] for j in ("exact", "same_index_exact", "first_different_index")}
                            for k, v in report.get("comparisons", {}).items()},
            "error": report.get("error")}, separators=(",", ":")), flush=True)
    return 1 if report["status"] in ("OPERATIONAL_ERROR", "INCOMPLETE_FRAMES") else 0

if __name__ == "__main__":
    raise SystemExit(main())
