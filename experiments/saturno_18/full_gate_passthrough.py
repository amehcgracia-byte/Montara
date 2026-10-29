"""Full saved Stage-plan A/A/B gate. QA controls only; no source edits.

B uses the packet-preflight recipe. In this fixture all video GOPs are needed:
the measured reduction is camera-audio removal, NOT video-frame omission.
"""
from __future__ import annotations
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import zlib
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = Path(os.environ.get("SATURNO_FULL_OUT", "/tmp/saturno-full18"))


def call(args, timeout=2100):
    p = subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError(f"returncode={p.returncode}: {p.stderr[-6000:]}")
    return p.stdout


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def audio_hash(path):
    args = ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-map", "0:a:0",
            "-vn", "-c:a", "pcm_f32le", "-f", "f32le", "-"]
    # Stream PCM rather than buffering the whole full-length movie in memory.
    with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        h = hashlib.sha256(); size = 0
        for chunk in iter(lambda: process.stdout.read(1024 * 1024), b""):
            h.update(chunk); size += len(chunk)
        stderr = process.stderr.read()
        if process.wait(timeout=180) != 0:
            raise RuntimeError(stderr.decode(errors="replace")[-2000:])
    return {"sha256": h.hexdigest(), "bytes": size}


def final_evidence(path):
    raw = call(["ffmpeg", "-nostdin", "-v", "error", "-i", path, "-map", "0:v:0",
                "-an", "-c:v", "rawvideo", "-threads:v", "1", "-pix_fmt", "yuv420p",
                "-fps_mode", "passthrough", "-f", "framehash", "-hash", "sha256", "-"])
    rows = [line for line in raw.splitlines() if line and not line.startswith("#")]
    frame_hashes = [line.split(",")[-1].strip() for line in rows]
    timeline = json.loads(call(["ffprobe", "-v", "error", "-show_streams", "-show_packets",
        "-show_entries", "stream=index,codec_type,time_base,start_time,duration,nb_frames,sample_rate,channels,width,height:packet=stream_index,pts,dts,duration",
        "-of", "json", path]))
    canonical = json.dumps(timeline, sort_keys=True, separators=(",", ":")).encode()
    packets = timeline["packets"]
    return {"sha256": file_hash(path), "bytes": Path(path).stat().st_size,
            "frame_hashes": frame_hashes, "frame_count": len(frame_hashes),
            "framehash_timeline_sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "audio_pcm": audio_hash(path), "streams": timeline["streams"],
            "packet_count": len(packets), "packet_first_last": packets[:4] + packets[-4:],
            "timeline_sha256": hashlib.sha256(canonical).hexdigest(),
            "timeline_zlib_base64": base64.b64encode(zlib.compress(canonical)).decode(),
            "timeline_encoding": "base64(zlib(canonical sorted compact ffprobe JSON)); includes every packet"}


def worker(spec_path):
    spec = json.loads(Path(spec_path).read_text())
    for folder in spec["mask"]:
        call(["mount", "-t", "tmpfs", "-o", "size=1m,mode=0755", "tmpfs", folder])
        assert not list(Path(folder).iterdir())
    absent = {p: not Path(p).exists() for p in spec["originals"]}
    if spec["mask"]:
        assert all(absent.values()), "Original media still visible to B"
    os.environ["ZUCKER_DATA_ROOT"] = spec["runtime"]
    sys.path.insert(0, str(ROOT / "engine"))
    sys.path.insert(0, str(ROOT))
    from experiments.saturno_17.qa_decoder_override import cpu_decoder_passthrough_guard
    from core.project import Project
    from core.normalization import global_cache_root
    import core.stages.export as export
    cache = global_cache_root()
    assert not cache.exists() or not list(cache.rglob("*")), "Runtime cache not empty"
    data = json.loads(Path(spec["project_data"]).read_text())
    plan = json.loads(Path(spec["plan"]).read_text())
    data.setdefault("settings", {}).setdefault("export", {})["force_rerender_segments"] = True
    project = Project(Path(spec["folder"]) / "project", data)
    project.ensure_dirs(); project.save()
    commands = []; lock = threading.Lock()

    def wrap(original, kind):
        def controlled(command, *args, **kwargs):
            actual = list(command)
            if "libx264" in actual:
                actual[-1:-1] = ["-threads:v", "1"]
            entry = {"kind": kind, "engine_command": command, "effective_command": actual}
            started = time.perf_counter()
            try:
                return original(actual, *args, **kwargs)
            except Exception as exc:
                entry["error"] = repr(exc)
                raise
            finally:
                entry["elapsed_sec"] = time.perf_counter() - started
                output = Path(str(actual[-1]))
                if output.is_file():
                    entry["output_sha256"] = file_hash(output)
                    entry["output_bytes"] = output.stat().st_size
                with lock:
                    commands.append(entry)
        return controlled

    export._run_ffmpeg_progress = wrap(export._run_ffmpeg_progress, "ordinary")
    export.run_reprojected_command = wrap(export.run_reprojected_command, "native_360")
    destination = project.folder / "exports/render.mp4"
    warnings = []
    started = time.perf_counter()
    decoder_control = None
    try:
        with cpu_decoder_passthrough_guard() as decoder_control:
            export._render_plan(project, plan["segments"], spec["master"], destination,
                plan["platform"], spec["bitrate"], warnings, lambda *_: None,
                master_window_start=plan["master_window_start_sec"])
    except Exception as exc:
        (Path(spec["folder"]) / "error.json").write_text(json.dumps({"error": repr(exc), "commands": commands}))
        raise
    elapsed = time.perf_counter() - started
    assert decoder_control is not None and len(decoder_control["interventions"]) == 7, "Expected seven QA decoder interventions"
    result = final_evidence(destination)
    expected = round((sum(float(s["duration_sec"]) for s in plan["segments"])
                      + export.INTRO_DURATION + export.OUTRO_DURATION) * export.TARGET_EXPORT_FPS)
    result.update(qa_decoder_interventions=len(decoder_control["interventions"]),
                  qa_decoder_commands=decoder_control["interventions"],
                  label=spec["label"], export_sec=elapsed, expected_frames=expected,
                  expected_frame_count_ok=result["frame_count"] == expected,
                  warnings=warnings, commands=commands,
                  native_360_calls=sum(c["kind"] == "native_360" and "error" not in c for c in commands),
                  original_paths_absent=absent, masked_directories=spec["mask"],
                  cache_initially_empty=True, project_json_sha256=file_hash(spec["project_data"]),
                  plan_json_sha256=file_hash(spec["plan"]),
                  export_plan_sha256=hashlib.sha256(json.dumps(plan["segments"], sort_keys=True).encode()).hexdigest())
    expected_native = sum(bool(s.get("spherical_shot", {}).get("movement")) for s in plan["segments"])
    result["expected_native_360_calls_min"] = expected_native
    assert result["native_360_calls"] >= expected_native, "Native moving-360 path was not observed as expected"
    (Path(spec["folder"]) / "result.json").write_text(json.dumps(result))


def compare(a, b):
    left, right = a["frame_hashes"], b["frame_hashes"]
    bad = [i for i, (x, y) in enumerate(zip(left, right)) if x != y]
    return {"frames_A": len(left), "frames_B": len(right), "expected": a["expected_frames"],
            "video_exact": a["expected_frame_count_ok"] and b["expected_frame_count_ok"] and left == right,
            "different_indices": bad, "same_index_exact": sum(x == y for x, y in zip(left, right)),
            "audio_exact": a["audio_pcm"] == b["audio_pcm"] and a["audio_pcm"]["bytes"] > 0,
            "timeline_exact": a["timeline_sha256"] == b["timeline_sha256"],
            "file_exact": a["sha256"] == b["sha256"]}


def accepted(pair):
    return all(pair.get(k) is True for k in ("video_exact", "audio_exact", "timeline_exact"))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"status": "NOT_RUN", "scope": "exact real Stage plan: forced A/A, then source/cache-isolated B",
              "critical_limitation": "All original video GOPs retained. Savings are camera-audio removal, not partial-video selection.",
              "runtime_controls": "QA encoder threads:v 1 in both ordinary and native_360 FFmpeg entry points",
              "remote_transfer_or_production_cost_measured": False}
    results = {}
    try:
        from packet_preflight import rewrite
        preflight = json.loads((HERE / "packet_results_40886014059.json").read_text())["report"]
        assert preflight["status"] == "PASS_INPUT_PREFLIGHT"
        baseline = json.loads((HERE / "stage_results_40882186838.json").read_text())
        project_data = json.loads((HERE / "stage_project.json").read_text())
        plan = json.loads((HERE / "stage_edit_plan.json").read_text())
        package = OUT / "package"; package.mkdir()
        mapping = {}
        prepare_start = time.perf_counter()
        for row in preflight["sources"]:
            assert file_hash(row["source"]) == row["source_sha256"], "Input source changed"
            target = package / Path(row["source"]).name
            command = list(row["command"]); command[-1] = str(target)
            call(command, timeout=300)
            assert file_hash(target) == row["target_sha256"], "Packet recipe output changed"
            mapping[row["source"]] = str(target)
            record = next(r for r in project_data["inputs"]["videos"] if r["path"] == row["source"])
            mapping[record["normalized"]["path"]] = str(target)
        original_master = project_data["inputs"]["master"]["path"]
        master_data = Path(original_master).read_bytes()
        master_git_sha = hashlib.sha1(b"blob " + str(len(master_data)).encode() + b"\0" + master_data).hexdigest()
        expected_master = next(f for f in baseline["fixture_git_objects"] if f["path"].endswith("/master.mp3"))
        assert master_git_sha == expected_master["blob_sha1"], "Master fixture changed"
        report["original_master_sha256"] = hashlib.sha256(master_data).hexdigest()
        master = package / "master.mp3"; shutil.copy2(original_master, master)
        mapping[original_master] = str(master)
        b_project = package / "project.json"; b_project.write_text(json.dumps(rewrite(copy.deepcopy(project_data), mapping)))
        b_plan = package / "plan.json"; b_plan.write_text(json.dumps(rewrite(copy.deepcopy(plan), mapping)))
        report["package_prepare_sec"] = time.perf_counter() - prepare_start
        report["package_files"] = [{"path": str(p.relative_to(package)), "bytes": p.stat().st_size,
                                     "sha256": file_hash(p)} for p in sorted(package.iterdir())]
        report["package_bytes_measured"] = sum(p["bytes"] for p in report["package_files"])
        report["original_media_bytes"] = preflight["original_video_bytes"] + preflight["master_bytes_required_in_full"]
        report["software_assets_shared"] = ["web/brand/montara-logo.png", "web/brand/montara-watermark.png"]
        report["shared_asset_hashes"] = {p: file_hash(ROOT / p) for p in report["software_assets_shared"]}
        archive_started = time.perf_counter()
        for name, paths in (("package", sorted(package.iterdir())),
                            ("original_media", [Path(row["source"]) for row in preflight["sources"]] + [Path(original_master)])):
            archive = OUT / f"{name}.zip"
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as handle:
                for path in paths:
                    handle.write(path, path.name)
            report[name + "_zip_bytes"] = archive.stat().st_size
            report[name + "_zip_sha256"] = file_hash(archive)
        report["two_archives_prepare_sec"] = time.perf_counter() - archive_started
        common_config = baseline["report"]["selector_control"]["evidence"]["json_files"]["runtime/config.json"]
        for label in ("A", "A_repeat", "B"):
            folder = OUT / label; folder.mkdir()
            runtime = folder / "runtime"; runtime.mkdir()
            config = {k: v for k, v in common_config.items() if k in
                      {"branding", "band_name", "handle", "ffmpeg_path", "ffprobe_path", "spherical_landmarks", "spherical_source_path", "montara_branding_mode"}}
            (runtime / "config.json").write_text(json.dumps(config))
            is_b = label == "B"
            spec = {"label": label, "folder": str(folder), "runtime": str(runtime),
                    "project_data": str(b_project if is_b else HERE / "stage_project.json"),
                    "plan": str(b_plan if is_b else HERE / "stage_edit_plan.json"),
                    "master": str(master) if is_b else original_master, "bitrate": 18000000,
                    "mask": [str(ROOT / "tests/fixtures"), str(OUT / "A"), str(OUT / "A_repeat")] if is_b else [],
                    "originals": [*[r["path"] for r in project_data["inputs"]["videos"]], original_master] if is_b else []}
            spec_path = OUT / f"spec-{label}.json"; spec_path.write_text(json.dumps(spec))
            command = [sys.executable, str(Path(__file__).resolve()), "worker", str(spec_path)]
            if is_b:
                command = ["sudo", "-n", "unshare", "--mount", "--propagation", "private", *command]
            call(command, timeout=2100)
            result = json.loads((folder / "result.json").read_text()); results[label] = result
            print(f"SATURNO_FULL12_{label}_BEGIN", flush=True)
            print(json.dumps({"label":label,"export_sec":result["export_sec"],"frame_count":result["frame_count"],"native_360_calls":result["native_360_calls"],"qa_decoder_interventions":result["qa_decoder_interventions"],"sha256":result["sha256"]}), flush=True)
            print(f"SATURNO_FULL12_{label}_END", flush=True)
            if label == "A_repeat":
                report["AA"] = compare(results["A"], result)
                if not accepted(report["AA"]):
                    report["status"] = "FAIL_FULL_AA_B_SKIPPED"
                    break
            if is_b:
                report["AB"] = compare(results["A"], result)
                report["status"] = "PASS_FULL_PLAN_ISOLATED_AB" if accepted(report["AB"]) else "FAIL_FULL_PLAN_AB"
        report["summaries"] = {k: {f: v[f] for f in ("export_sec", "sha256", "bytes", "frame_count", "native_360_calls")} for k, v in results.items()}
    except Exception as exc:
        report.update(status="FULL_GATE_EXECUTION_ERROR", error=repr(exc))
    finally:
        report["worker_errors"] = {str(p.relative_to(OUT)): json.loads(p.read_text()) for p in OUT.glob("*/error.json")}
        (OUT / "REPORT.json").write_text(json.dumps(report, indent=2))
        print("SATURNO_FULL12_REPORT_BEGIN", flush=True)
        print(json.dumps({k:v for k,v in report.items() if k not in ("worker_errors",)}, default=str), flush=True)
        print("SATURNO_FULL12_REPORT_END", flush=True)
    print("SATURNO18_SUMMARY="+json.dumps({"status":report["status"],"AA":{k:report.get("AA",{}).get(k) for k in ("same_index_exact","video_exact","audio_exact","timeline_exact","file_exact")},"AB":{k:report.get("AB",{}).get(k) for k in ("same_index_exact","video_exact","audio_exact","timeline_exact","file_exact")},"error":report.get("error")},separators=(",",":")),flush=True)
    return 0 if report["status"] == "PASS_FULL_PLAN_ISOLATED_AB" else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        worker(sys.argv[2])
    else:
        raise SystemExit(main())
