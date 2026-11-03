#!/usr/bin/env python3
"""EX14H11: real Stage ExportStage using source HEVC 360, project-local opt-in.

Use --smoke first, then --abba. Each run gets a separate project and cache root.
No global application changes, no edits of input assets, no retained MP4.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path("/home/fer/zucker-videos-ex14h09")
REFERENCE = Path("/home/fer/montara-focus-real-mini-01")
ORIGINALS = Path("/home/fer/lab-clips/originales")
FPS = 30
FRAMES = 60


def capture(command):
    return subprocess.check_output(command, text=True, stderr=subprocess.PIPE).strip()


def probe(path, frames=False):
    fields = "stream=codec_name,width,height,avg_frame_rate,nb_read_frames,codec_type"
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0"]
    if frames:
        cmd.append("-count_frames")
    cmd += ["-show_entries", fields, "-of", "json", str(path)]
    streams = json.loads(capture(cmd)).get("streams") or []
    if len(streams) != 1:
        raise RuntimeError("Video stream missing or ambiguous")
    return streams[0]


def source():
    candidates = []
    for p in sorted(ORIGINALS.iterdir()):
        if p.is_file() and p.suffix.lower() in (".mp4", ".mov"):
            meta = probe(p)
            if meta.get("codec_name") == "hevc" and (meta.get("width"), meta.get("height")) == (3840, 1920):
                candidates.append(p)
    if len(candidates) != 1:
        raise RuntimeError(f"STOP: expected exactly one real 360 source, got {len(candidates)}")
    return candidates[0]


def sha_stream(path, stream_type):
    if stream_type == "video":
        command = ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path),
                   "-map", "0:v:0", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"]
    else:
        command = ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path),
                   "-map", "0:a:0", "-ac", "2", "-ar", "48000",
                   "-f", "s16le", "pipe:1"]
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    sha = hashlib.sha256()
    count = 0
    assert proc.stdout is not None
    while True:
        block = proc.stdout.read(1024 * 1024)
        if not block:
            break
        sha.update(block)
        count += len(block)
    error = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
    if proc.wait() != 0 or not count:
        raise RuntimeError(f"Failed to decode {stream_type}: {error[-600:]}")
    return sha.hexdigest(), count


def setup_project(destination, selected_source, mode):
    shutil.copytree(REFERENCE, destination,
                    ignore=shutil.ignore_patterns("cache", "exports", "__pycache__"))
    doc = json.loads((destination / "project.json").read_text())
    plan = json.loads((destination / "artifacts/edit_plan.json").read_text())
    master = (doc.get("inputs", {}).get("master") or {}).get("path")
    if not master or not Path(master).is_file():
        raise RuntimeError("Existing project master audio not available")

    shot = {
        "type": "stage", "yaw": 180.0, "pitch": -30.0, "fov": 100.0,
        "projection_preset": "linear", "runtime_motion_enabled": True,
        "hold_motion_rate_deg_per_sec": 9.0
    }
    record = {
        "path": str(selected_source),
        "normalized": {"path": str(selected_source)},
        "probe": {
            "projection": "equirect", "width": 3840, "height": 1920,
            "bit_depth": 8, "hdr": False, "video_codec": "hevc",
            "codec_name": "hevc",
        },
    }
    segment = {
        "camera_id": "originales", "filename": selected_source.name,
        "source_path": str(selected_source), "clip_path": str(selected_source),
        "spherical_source_path": str(selected_source),
        "projection": "equirect",
        "master_start_sec": 0.0, "clip_start_sec": 840.0,
        "duration_sec": 2.0, "frame_count": FRAMES,
        "available_camera_ids": ["originales"],
        "camera_alternative_available": False, "manual_view": True,
        "spherical_shot": shot,
    }
    # Mirror the product invariant: the label must identify the actual render source.
    from core.stages.edit import _camera_id_from_render_path, validate_plan_camera_source_consistency
    source_camera = _camera_id_from_render_path(segment)
    if source_camera != "originales":
        raise RuntimeError(f"STOP: unexpected physical camera identity: {source_camera!r}")
    validate_plan_camera_source_consistency({"segments": [segment]})
    doc["name"] = f"EX14H11-{mode}"
    doc["inputs"]["videos"] = [record]
    doc.setdefault("settings", {}).pop("spherical_landmarks", None)
    doc["settings"].pop("spherical_landmarks_by_source", None)
    wizard = doc["settings"].setdefault("wizard", {})
    wizard.update({"platform": "reel", "reel_aspect": "16:9",
                   "reel_text_overlays": [], "reel_image_overlays": [],
                   "reel_video_overlays": []})
    exp = doc["settings"].setdefault("export", {})
    exp.update({"draft": False, "segment_workers": 1,
                "force_rerender_segments": True,
                "overlap_segment_verification": False,
                "verify_motion": True,
                "ex14h11_fast_wrap": mode == "B",
                "ex14h11_smart_unwrap": mode == "B"})
    plan.update({
        "platform": "reel", "reel_aspect": "16:9",
        "segments": [segment], "cut_count": 0,
        "camera_usage": {"originales": 1},
        "master_window_start_sec": 0.0,
        "duration_sec": 2.0, "warnings": []
    })
    for key in ("spherical_shot_usage", "spherical_shot_distribution",
                "camera_distribution", "spherical_recording_usage"):
        plan.pop(key, None)

    (destination / "project.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    (destination / "artifacts/edit_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    for name in ("export_manifest.json", "export_link_audit.json"):
        (destination / "artifacts" / name).unlink(missing_ok=True)
    return doc, segment


def run_one(base, selected_source, mode, number):
    from core.project import Project
    from core.stages import export as e
    project_dir = base / f"project_{number}_{mode}"
    root_cache = base / f"data_{number}_{mode}"
    root_cache.mkdir()
    doc, segment = setup_project(project_dir, selected_source, mode)

    previous = os.environ.get("ZUCKER_DATA_ROOT")
    os.environ["ZUCKER_DATA_ROOT"] = str(root_cache)
    try:
        project = Project(project_dir, doc)
        project.ensure_dirs()
        info = e._segment_source_info(project, segment)
        if not e._spherical_uses_original_motion(info, segment, False):
            raise RuntimeError("STOP: Stage would not choose original/native motion")
        audit_flags = e._spherical_optional_map_flags(project)
        print(f"RUN_{number}_{mode}_START flags={audit_flags}", flush=True)
        start = time.perf_counter()
        e.ExportStage().run(project, lambda percent, detail: None)
        elapsed = time.perf_counter() - start

        calls = doc.get("_ex14h11_native_calls") or []
        expected = {"fast_wrap": mode == "B", "smart_unwrap": mode == "B"}
        if not calls or any(item.get("flags") != expected or not item.get("source_original")
                            or item.get("frame_count") != FRAMES for item in calls):
            raise RuntimeError(f"Native calls missing/incorrect: {calls}")

        manifest = json.loads((project_dir / "artifacts/export_manifest.json").read_text())
        perf = (manifest.get("performance") or {})
        segments = perf.get("segments") or []
        if len(segments) != 1 or segments[0].get("cached") is not False or segments[0].get("rendered_from") != "original":
            raise RuntimeError(f"Did not export uncached original: {segments}")

        output_record = (manifest.get("exports") or [])[0]
        output = Path(output_record["path"])
        if not output.is_file():
            raise RuntimeError("Stage output missing")
        stream = probe(output, frames=True)
        if int(stream.get("nb_read_frames") or 0) != FRAMES or tuple(stream[k] for k in ("width", "height")) != (1920, 1080):
            raise RuntimeError(f"Unexpected Stage video metadata: {stream}")
        video_sha, video_bytes = sha_stream(output, "video")
        if video_bytes != FRAMES * 1920 * 1080 * 3:
            raise RuntimeError(f"Incorrect RGB output length: {video_bytes}")
        audio_sha, audio_bytes = sha_stream(output, "audio")
        result = {
            "run": number, "mode": mode, "wall_sec": round(elapsed, 3),
            "segment_ffmpeg_sec": segments[0].get("ffmpeg_sec"),
            "export_wall_sec": perf.get("total_wall_sec") or perf.get("wall_sec"),
            "native_calls": calls, "video_frames": FRAMES,
            "output_bytes": output.stat().st_size,
            "rgb_sha256": video_sha, "audio_pcm_sha256": audio_sha,
            "audio_pcm_bytes": audio_bytes,
            "warnings": manifest.get("warnings"),
            "scope": "real ExportStage Reel-horizontal, one moving 360 shot, not full EditStage",
        }
        print("RUN_DONE " + json.dumps(result, ensure_ascii=False), flush=True)
        return result
    finally:
        if previous is None:
            os.environ.pop("ZUCKER_DATA_ROOT", None)
        else:
            os.environ["ZUCKER_DATA_ROOT"] = previous


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("smoke", "abba"), required=True)
    args = parser.parse_args()
    if capture(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD^"]) != "2e76003":
        raise RuntimeError("STOP: expected one native-call audit commit on top of 2e76003")
    if capture(["git", "-C", str(ROOT), "status", "--porcelain"]):
        raise RuntimeError("STOP: uncommitted changes in engine worktree")
    changed = capture(["git", "-C", str(ROOT), "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"])
    if changed != "core/stages/export.py":
        raise RuntimeError(f"STOP: unexpected audit commit changed {changed!r}")
    if "_ex14h11_native_calls" not in (ROOT / "core/stages/export.py").read_text():
        raise RuntimeError("STOP: required Stage native-call audit missing")
    if shutil.disk_usage("/home/fer").free < 10 * 1024**3:
        raise RuntimeError("STOP: less than 10 GiB free on VM")
    if not (REFERENCE / "project.json").is_file():
        raise RuntimeError("STOP: reference project absent")
    selected_source = source()
    original_stat = (selected_source.stat().st_size, selected_source.stat().st_mtime_ns)
    sys.path.insert(0, str(ROOT))
    modes = ("A",) if args.mode == "smoke" else ("A", "B", "B", "A")
    results = []
    print(f"EX14H_11_STAGE_{args.mode.upper()}_START free_GiB="
          f"{shutil.disk_usage('/home/fer').free / 1024**3:.2f}", flush=True)
    with tempfile.TemporaryDirectory(prefix="jupiter_ex14h11_", dir="/home/fer") as temp:
        for i, mode in enumerate(modes, 1):
            result = run_one(Path(temp), selected_source, mode, i)
            results.append(result)
            if selected_source.stat().st_size != original_stat[0] or selected_source.stat().st_mtime_ns != original_stat[1]:
                raise RuntimeError("STOP: source original metadata changed")
            if shutil.disk_usage("/home/fer").free < 10 * 1024**3:
                raise RuntimeError("STOP: less than 10 GiB available during test")
    if args.mode == "abba":
        A = [x["wall_sec"] for x in results if x["mode"] == "A"]
        B = [x["wall_sec"] for x in results if x["mode"] == "B"]
        avg_a, avg_b = sum(A)/2, sum(B)/2
        result = {
            "A_mean_sec": round(avg_a, 3), "B_mean_sec": round(avg_b, 3),
            "wall_gain_pct": round(100 * (avg_a-avg_b)/avg_a, 2),
            "video_exact": len({x["rgb_sha256"] for x in results}) == 1,
            "audio_exact": len({x["audio_pcm_sha256"] for x in results}) == 1,
            "runs": results,
        }
        print("EX14H_11_STAGE_ABBA_RESULT " + json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        if not result["video_exact"] or not result["audio_exact"]:
            raise RuntimeError("EX14H_11_STAGE_DIFFERENCE: inspect before integration")
    else:
        print("EX14H_11_STAGE_SMOKE_PASS " + json.dumps(results[0], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
