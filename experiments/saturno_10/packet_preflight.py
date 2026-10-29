"""Packet/GOP dependency preflight for the EXACT saved Stage plan.

Uses FFmpeg's documented noise BSF with amount=0 solely to omit unneeded
whole GOPs, retaining PTS/DTS and first/last GOP. It does NOT certify a final
Zucker A/B export. Every needed decoded window and native colour profile is tested.
"""
from __future__ import annotations
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ.get("SATURNO_PACKET_OUT", "/tmp/saturno-packet-preflight"))


def run(args, binary=False):
    p = subprocess.run(list(map(str, args)), capture_output=True, text=not binary, timeout=300)
    if p.returncode:
        raise RuntimeError(f"returncode={p.returncode}: {p.stderr[-4000:]!r}")
    return p.stdout


def probe(path, packets=False):
    args = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams", "-show_format"]
    if packets:
        args += ["-show_packets", "-show_data_hash", "sha256", "-show_entries",
                 "stream=time_base,avg_frame_rate,r_frame_rate,width,height,start_time,duration:format=duration,start_time:packet=pts,dts,pts_time,dts_time,duration_time,size,flags,data_hash"]
    return json.loads(run(args + ["-of", "json", path]))


def choose_gops(packets, windows, frame_sec):
    starts = sorted({0, *[i for i, p in enumerate(packets) if "K" in p.get("flags", "")]})
    groups = [(s, starts[i + 1] if i + 1 < len(starts) else len(packets)) for i, s in enumerate(starts)]
    selected = {0, len(groups) - 1}  # Preserve container start and duration for colour analysis.
    for group, (a, b) in enumerate(groups):
        times = [float(p["pts_time"]) for p in packets[a:b] if "pts_time" in p]
        if any(start <= pts < end + frame_sec for pts in times for start, end in windows):
            selected.add(group)
    indices = [i for g in sorted(selected) for i in range(*groups[g])]
    return groups, sorted(selected), indices


def copy_sparse(source, target, source_probe, groups, selected):
    terms = [f"between(n\\,{groups[g][0]}\\,{groups[g][1] - 1})" for g in selected]
    bsf = "noise=amount=0:drop=not(" + "+".join(terms) + ")"
    time_base = source_probe["streams"][0]["time_base"]
    numerator, denominator = map(int, time_base.split("/"))
    if numerator != 1:
        raise ValueError("This predeclared MP4 fixture trial requires time_base numerator=1")
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-copyts", "-i", source,
           "-map", "0:v:0", "-an", "-c:v", "copy", "-bsf:v", bsf,
           "-avoid_negative_ts", "disabled", "-video_track_timescale", str(denominator),
           "-movflags", "+faststart", target]
    run(cmd)
    return list(map(str, cmd))


def window_hash(path, start, duration, native_360=False):
    args = ["ffmpeg", "-nostdin", "-v", "error", "-threads", "2", "-ss", str(start), "-i", path]
    if native_360:
        args += ["-vf", "fps=30,format=bgr24", "-frames:v", str(max(1, round(duration * 30))),
                 "-pix_fmt", "bgr24"]
    else:
        args += ["-t", str(duration), "-pix_fmt", "yuv420p"]
    args += ["-map", "0:v:0", "-an", "-fps_mode", "passthrough", "-f", "rawvideo", "-"]
    raw = run(args, binary=True)
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def rewrite(value, mapping):
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [rewrite(x, mapping) for x in value]
    if isinstance(value, dict):
        return {mapping.get(k, k): rewrite(v, mapping) for k, v in value.items()}
    return value


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    package = OUT / "package"
    package.mkdir()
    plan = json.loads(Path(__file__).with_name("stage_edit_plan.json").read_text())
    project_data = json.loads(Path(__file__).with_name("stage_project.json").read_text())
    os.environ["ZUCKER_DATA_ROOT"] = str(OUT / "fresh-analysis-runtime")
    sys.path.insert(0, str(ROOT / "engine"))
    from core.project import Project
    import core.stages.export as export
    project = Project(OUT / "project-A", project_data)
    project.ensure_dirs()
    report = {"status": "NOT_RUN", "scope": "GOP and decoded-input/colour preflight, NOT final rendered A/B",
              "stage_reference_run": 40882186838, "sources": [], "native_final_ab_approved": False,
              "method": "FFmpeg stream-copy; noise BSF amount=0; retain whole GOPs plus first/last; original timestamps"}
    try:
        mapping = {}
        checks = []
        started = time.perf_counter()
        for record in project_data["inputs"]["videos"]:
            source = Path(record["path"])
            segments = [s for s in plan["segments"] if s.get("source_path") == str(source)]
            assert segments, "No selected source can disappear from dependency accounting"
            windows = [(float(s["clip_start_sec"]), float(s["clip_start_sec"]) + float(s["duration_sec"])) for s in segments]
            original_probe = probe(source, packets=True)
            duration = float(original_probe["format"]["duration"])
            spherical = record.get("probe", {}).get("projection") == "equirect"
            samples = export._visible_color_samples(project, segments) if spherical else None
            colour_commands = export.color_sample_commands(str(source), duration, samples=samples)
            for cmd in colour_commands:
                start = float(cmd[cmd.index("-ss") + 1])
                length = float(cmd[cmd.index("-t") + 1])
                windows.append((start, start + length))
            fps = float(record["probe"]["fps"])
            groups, selected, indices = choose_gops(original_probe["packets"], windows, 1 / fps)
            target = package / source.name
            command = copy_sparse(source, target, original_probe, groups, selected)
            target_probe = probe(target, packets=True)
            expected = [original_probe["packets"][i] for i in indices]
            received = target_probe["packets"]
            packet_exact = len(expected) == len(received) and all(
                all(a.get(k) == b.get(k) for k in ("data_hash", "pts", "dts")) for a, b in zip(expected, received))
            duration_exact = original_probe["format"]["duration"] == target_probe["format"]["duration"]
            window_records = []
            for segment in segments:
                # Match the actual decoder path: full float seek for moving 360;
                # millisecond-rounded seek/duration for the ordinary command base.
                start = float(segment["clip_start_sec"])
                length = float(segment["duration_sec"])
                if not spherical:
                    start, length = float(f"{start:.3f}"), float(f"{length:.3f}")
                a = window_hash(source, start, length, spherical)
                b = window_hash(target, start, length, spherical)
                window_records.append({"start": start, "duration": length, "native_360_decoder": spherical,
                                       "A": a, "B": b, "exact": a == b and a["bytes"] > 0})
            row = {"source": str(source), "target": str(target), "source_bytes": source.stat().st_size,
                   "target_bytes": target.stat().st_size, "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                   "target_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                   "groups_total": len(groups), "groups_selected": selected, "group_packet_ranges": groups,
                   "source_packets": len(original_probe["packets"]), "retained_packets": len(received),
                   "original_video_packet_bytes": sum(int(p["size"]) for p in original_probe["packets"]),
                   "retained_video_packet_bytes": sum(int(p["size"]) for p in expected),
                   "packet_payload_and_pts_dts_exact": packet_exact, "duration_exact": duration_exact,
                   "duration_A": original_probe["format"]["duration"], "duration_B": target_probe["format"]["duration"],
                   "needed_windows": windows, "colour_commands_A": colour_commands,
                   "selected_window_comparisons": window_records, "command": command}
            report["sources"].append(row)
            checks.extend([packet_exact, duration_exact, all(r["exact"] for r in window_records)])
            mapping[str(source)] = str(target)
            normalized = record.get("normalized", {}).get("path")
            if normalized:
                mapping[normalized] = str(target)
            print(json.dumps({k: row[k] for k in ("source", "source_bytes", "target_bytes", "groups_total", "groups_selected", "packet_payload_and_pts_dts_exact", "duration_exact")}), flush=True)
        report["prepare_and_window_checks_sec"] = time.perf_counter() - started
        # Fresh project-local identities: no reuse of A's colour cache keys/results.
        a_profiles = export._color_profiles_for_segments(project, plan["segments"], [], None)
        b_project = Project(OUT / "project-B", rewrite(copy.deepcopy(project_data), mapping))
        b_project.ensure_dirs()
        b_segments = rewrite(copy.deepcopy(plan["segments"]), mapping)
        b_profiles = export._color_profiles_for_segments(b_project, b_segments, [], None)
        # Original 360 clip key is a proxy filename; map both sides by source identity.
        a_canonical = {Path(export._segment_source_info(project, s)["source_path"]).name: a_profiles[s["clip_path"]] for s in plan["segments"]}
        b_canonical = {Path(export._segment_source_info(b_project, s)["source_path"]).name: b_profiles[s["clip_path"]] for s in b_segments}
        report.update(colour_A=a_canonical, colour_B=b_canonical, colour_exact=a_canonical == b_canonical)
        checks.append(report["colour_exact"])
        source_video_bytes = sum(s["source_bytes"] for s in report["sources"])
        package_video_bytes = sum(s["target_bytes"] for s in report["sources"])
        master_bytes = Path(project_data["inputs"]["master"]["path"]).stat().st_size
        packaged_master = package / "master.mp3"
        shutil.copy2(project_data["inputs"]["master"]["path"], packaged_master)
        mapping[project_data["inputs"]["master"]["path"]] = str(packaged_master)
        (package / "stage_edit_plan.json").write_text(json.dumps(rewrite(plan, mapping)))
        (package / "stage_project.json").write_text(json.dumps(rewrite(project_data, mapping)))
        metadata_bytes = sum((package / name).stat().st_size for name in ("stage_edit_plan.json", "stage_project.json"))
        report.update(original_video_bytes=source_video_bytes, packaged_video_bytes=package_video_bytes,
                      master_bytes_required_in_full=master_bytes,
                      media_fraction_including_master=(package_video_bytes + master_bytes) / (source_video_bytes + master_bytes),
                      measured_plan_project_metadata_bytes=metadata_bytes,
                      media_plus_plan_project_bytes=package_video_bytes + master_bytes + metadata_bytes,
                      metadata_transport_manifest_and_assets_still_not_counted=True,
                      gop_video_payload_fraction=sum(s["retained_video_packet_bytes"] for s in report["sources"]) / sum(s["original_video_packet_bytes"] for s in report["sources"]),
                      isolation_limitation="This preflight recomputes B colour from mapped sources, but does not sandbox B. Final export A/B requires source/cache masking.",
                      status="PASS_INPUT_PREFLIGHT" if all(checks) else "FAIL_INPUT_PREFLIGHT")
    except Exception as exc:
        report.update(status="PREFLIGHT_EXECUTION_ERROR", error=repr(exc))
    finally:
        (OUT / "REPORT.json").write_text(json.dumps(report, indent=2))
        print("SATURNO_PACKET_PREFLIGHT_BEGIN", flush=True)
        print(json.dumps(report), flush=True)
        print("SATURNO_PACKET_PREFLIGHT_END", flush=True)
    return 0 if report["status"] == "PASS_INPUT_PREFLIGHT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
