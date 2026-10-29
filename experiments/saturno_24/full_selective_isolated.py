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
HERE = ROOT / "experiments/saturno_10"
OUT = Path(os.environ.get("SATURNO_FULL_OUT", "/tmp/saturno-full24"))


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
    assert decoder_control is not None and len(decoder_control["interventions"]) >= 7, "Expected at least seven QA decoder interventions including possible failed encoder attempts"
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
    """True full real Stage export with intentionally lengthened inputs and sparse GOP B."""
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"experiment":"SATURNO-24","status":"NOT_RUN","scope":"full saved Stage A/A/B with lengthened real camera fixtures and genuinely removed GOPs","limitations":"Lengthened fixtures are controlled video copies, not independent long field recordings; no remote transfer"}
    results = {}
    try:
        sys.path.insert(0,str(HERE))
        from packet_preflight import probe,choose_gops,copy_sparse,rewrite
        baseline=json.loads((HERE/"stage_results_40882186838.json").read_text())
        original_data=json.loads((HERE/"stage_project.json").read_text())
        original_plan=json.loads((HERE/"stage_edit_plan.json").read_text())
        source_dir=OUT/"extended_sources";source_dir.mkdir()
        package=OUT/"package";package.mkdir()
        mapping_a={};mapping_b={};source_rows=[]
        for record in original_data["inputs"]["videos"]:
            original=Path(record["path"])
            assert original.exists()
            video_only=source_dir/("base-"+original.name)
            call(["ffmpeg","-v","error","-nostdin","-y","-i",original,
                 "-map","0:v:0","-an","-c:v","copy",video_only],timeout=180)
            concat=source_dir/(original.stem+".txt")
            concat.write_text("".join("file '"+str(video_only)+"'\n" for _ in range(3)))
            manifest_lines=concat.read_text().splitlines()
            assert manifest_lines==["file '"+str(video_only)+"'"]*3, "Concat manifest malformed"
            expanded=source_dir/original.name
            call(["ffmpeg","-v","error","-nostdin","-y","-f","concat","-safe","0",
                 "-i",concat,"-map","0:v:0","-an","-c:v","copy",
                 "-avoid_negative_ts","disabled",expanded],timeout=180)
            original_probe=probe(str(expanded),packets=True)
            first_probe=probe(str(video_only),packets=False)
            first_duration=float(first_probe["format"]["duration"])
            fps=float(record["probe"]["fps"])
            segments=[x for x in original_plan["segments"] if x.get("source_path")==str(original)]
            assert segments
            windows=[(float(x["clip_start_sec"]),float(x["clip_start_sec"])+float(x["duration_sec"])) for x in segments]
            # Preserve complete first iteration, to guarantee every Stage input dependency.
            # This is intentionally conservative; only later unused repetitions are candidates.
            windows.append((0.,first_duration+2/max(fps,1)))
            # Colour analysis may inspect across whole expanded input.
            sys.path.insert(0,str(ROOT/"engine"))
            from core.project import Project
            import core.stages.export as export
            probe_project=Project(OUT/"colour-probe",original_data)
            sample_points=export._visible_color_samples(probe_project,segments) if record.get("probe",{}).get("projection")=="equirect" else None
            colour_cmd=export.color_sample_commands(str(expanded),float(original_probe["format"]["duration"]),samples=sample_points)
            for cmd in colour_cmd:
                a=float(cmd[cmd.index("-ss")+1]);length=float(cmd[cmd.index("-t")+1]);windows.append((a,a+length))
            groups,selected,indices=choose_gops(original_probe["packets"],windows,1/max(fps,1))
            assert len(selected)<len(groups),{"name":original.name,"groups":len(groups),"selected":len(selected)}
            packed=package/original.name
            copy_sparse(str(expanded),str(packed),original_probe,groups,selected)
            package_probe=probe(str(packed),packets=True)
            expected=[original_probe["packets"][i] for i in indices]
            assert len(expected)==len(package_probe["packets"])
            assert all(all(a.get(k)==b.get(k) for k in ("data_hash","pts","dts")) for a,b in zip(expected,package_probe["packets"]))
            mapping_a[str(original)]=str(expanded)
            mapping_b[str(original)]=str(packed)
            normalized=record.get("normalized",{}).get("path")
            if normalized:
                mapping_a[normalized]=str(expanded)
                mapping_b[normalized]=str(packed)
            source_rows.append({"camera":original.name,"expanded_bytes":expanded.stat().st_size,
                "package_bytes":packed.stat().st_size,"gops_total":len(groups),"gops_retained":len(selected),
                "source_packets":len(original_probe["packets"]),"retained_packets":len(indices),
                "colour_sample_windows":len(colour_cmd),"stage_windows":len(segments)})
        assert any(r["gops_retained"]<r["gops_total"] for r in source_rows)
        report["source_rows"]=source_rows
        original_master=original_data["inputs"]["master"]["path"]
        master=package/"master.mp3";shutil.copy2(original_master,master)
        mapping_b[original_master]=str(master)
        a_project=OUT/"a-project.json";a_project.write_text(json.dumps(rewrite(copy.deepcopy(original_data),mapping_a)))
        a_plan=OUT/"a-plan.json";a_plan.write_text(json.dumps(rewrite(copy.deepcopy(original_plan),mapping_a)))
        b_project=package/"project.json";b_project.write_text(json.dumps(rewrite(copy.deepcopy(original_data),mapping_b)))
        b_plan=package/"plan.json";b_plan.write_text(json.dumps(rewrite(copy.deepcopy(original_plan),mapping_b)))
        report["original_media_bytes"]=sum(r["expanded_bytes"] for r in source_rows)+Path(original_master).stat().st_size
        report["package_media_bytes"]=sum(r["package_bytes"] for r in source_rows)+master.stat().st_size
        report["video_bytes_saved"]=sum(r["expanded_bytes"]-r["package_bytes"] for r in source_rows)
        assert report["video_bytes_saved"]>0
        config=baseline["report"]["selector_control"]["evidence"]["json_files"]["runtime/config.json"]
        for label in ("A","A_repeat","B"):
            folder=OUT/label;folder.mkdir()
            runtime=folder/"runtime";runtime.mkdir()
            (runtime/"config.json").write_text(json.dumps({k:v for k,v in config.items() if k in
                {"branding","band_name","handle","ffmpeg_path","ffprobe_path","spherical_landmarks","spherical_source_path","montara_branding_mode"}}))
            is_b=label=="B"
            spec={"label":label,"folder":str(folder),"runtime":str(runtime),
                "project_data":str(b_project if is_b else a_project),
                "plan":str(b_plan if is_b else a_plan),
                "master":str(master) if is_b else original_master,"bitrate":18000000,
                "mask":[str(ROOT/"tests/fixtures"),str(source_dir),str(OUT/"A"),str(OUT/"A_repeat")] if is_b else [],
                "originals":[*[str(source_dir/Path(v["path"]).name) for v in original_data["inputs"]["videos"]],original_master] if is_b else []}
            spec_file=OUT/f"spec-{label}.json";spec_file.write_text(json.dumps(spec))
            command=[sys.executable,str(Path(__file__).resolve()),"worker",str(spec_file)]
            if is_b:command=["sudo","-n","unshare","--mount","--propagation","private",*command]
            call(command,timeout=2100)
            result=json.loads((folder/"result.json").read_text());results[label]=result
            print("SATURNO24_RENDER="+json.dumps({"label":label,"frames":result["frame_count"],
                "duration_sec":result["export_sec"],"sha256":result["sha256"],
                "native_360_calls":result["native_360_calls"],
                "qa_decoder_interventions":result["qa_decoder_interventions"]},separators=(",",":")),flush=True)
            if label=="A_repeat":
                report["AA"]=compare(results["A"],result)
                if not accepted(report["AA"]):
                    report["status"]="FAIL_AA_B_SKIPPED";break
            if is_b:
                report["AB"]=compare(results["A"],result)
                report["status"]="PASS_FULL_SELECTIVE_ISOLATED_AB" if accepted(report["AB"]) else "FAIL_FULL_SELECTIVE_AB"
        report["renders"]={k:{"sha256":v["sha256"],"frames":v["frame_count"],
            "seconds":v["export_sec"]} for k,v in results.items()}
    except Exception as exc:
        report.update(status="OPERATIONAL_ERROR",error=repr(exc))
    finally:
        (OUT/"REPORT.json").write_text(json.dumps(report,indent=2))
        summary={k:v for k,v in report.items() if k not in ("source_rows",)}
        print("SATURNO24_SUMMARY="+json.dumps(summary,separators=(",",":")),flush=True)
    return 0 if report["status"]=="PASS_FULL_SELECTIVE_ISOLATED_AB" else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        worker(sys.argv[2])
    else:
        raise SystemExit(main())
