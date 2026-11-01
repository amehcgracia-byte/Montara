#!/usr/bin/env python3
"""JUPITER FOCUS A/C: real iPhone original ExportStage gate, isolated from prior project.
No EditStage, no mutations to source project/engine, no input media copies.
"""
import argparse, copy, json, os, shutil, subprocess, sys, time, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine"))
from focus_ac_vm_cpu_guard import sample_cpu, processes

SRC = Path("/home/fer/montara-focus-real-mini-01")
IPHONE = Path("/home/fer/lab-clips/originales/IMG_0044.MOV")
PROXY = Path("/home/fer/montara-focus-ac-real-01/1-iphone-proxy.mp4")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--approved-by-chema", action="store_true")
    a = ap.parse_args()
    if not a.approved_by_chema:
        ap.error("shared VM experiment needs approval")
    out = a.output.resolve()
    if out.exists():
        ap.error("output already exists: will not overwrite prior data")
    for f in (SRC / "project.json", SRC / "artifacts/edit_plan.json", IPHONE, PROXY):
        if not f.is_file():
            ap.error(f"missing prerequisite: {f}")
    if shutil.disk_usage(out.parent).free < 5 * 1024**3:
        ap.error("less than 5 GiB free: refuse render")
    cpu = sample_cpu(2)
    if cpu is None or cpu >= 65 or os.getloadavg()[0] >= (os.cpu_count() or 1) * .75 or processes():
        ap.error(f"VM busy (cpu={cpu}, load={os.getloadavg()[0]:.2f}, media_processes={processes()})")

    # Clone small reference project but do not carry generated caches or exports.
    shutil.copytree(SRC, out, ignore=shutil.ignore_patterns("cache", "exports"))
    data = json.loads((out / "project.json").read_text())
    plan = json.loads((out / "artifacts/edit_plan.json").read_text())
    originals = data.get("inputs", {}).get("videos", [])
    irecord = next((rec for rec in originals if Path(rec.get("path") or "").name == IPHONE.name), None)
    if irecord is None:
        raise ValueError("iPhone not in real project input registry")
    if Path((irecord.get("normalized") or {}).get("path") or "").resolve() != PROXY.resolve():
        raise ValueError("iPhone proxy binding mismatch")
    segs = plan.get("segments") or []
    if len(segs) != 1:
        raise ValueError("requires exactly one existing edited segment")
    seg = segs[0]
    if not (abs(float(seg.get("duration_sec") or 0) - 4) < .02 and abs(float(seg.get("clip_start_sec") or 0) - 10) < .02):
        raise ValueError("reference source must be a 4 s segment from original t=10")
    seg.update({"source_path": str(IPHONE), "clip_path": str(PROXY), "filename": IPHONE.name,
                "camera_id": "originales", "available_camera_ids": ["originales"],
                "camera_alternative_available": False, "projection": None})
    seg.pop("director_quality", None) # heavy old analysis is not needed for ExportStage
    settings = data.setdefault("settings", {}).setdefault("export", {})
    settings.update({"force_rerender_segments": True, "segment_workers": 1, "draft": False})
    (out / "project.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    (out / "artifacts/edit_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    for file in ("export_manifest.json", "export_link_audit.json"):
        (out / "artifacts" / file).unlink(missing_ok=True)

    report = {"status": "INCOMPLETE", "reference_project": str(SRC), "project": str(out),
              "original": IPHONE.name, "proxy": PROXY.name, "source_start_sec": 10.0,
              "duration_sec": 4.0, "preflight_cpu_percent": cpu,
              "limits": ["ExportStage only, not complete real music sync or EditStage",
                         "Output may have YouTube intro/outro; validate source segment via manifest",
                         "Original orientation needs visual confirmation"]}
    start = time.monotonic()
    try:
        from core.project import Project
        from core.stages.export import ExportStage, _segment_source_info
        project = Project(out, data)
        project.ensure_dirs()
        resolved = _segment_source_info(project, seg)
        if str(Path(resolved["source_path"]).resolve()) != str(IPHONE.resolve()):
            raise ValueError("resolver failed to select iPhone original")
        if str(Path(resolved["proxy_path"]).resolve()) != str(PROXY.resolve()):
            raise ValueError("resolver failed to preserve iPhone proxy")
        report["resolver"] = {"original": resolved["source_path"], "proxy": resolved["proxy_path"]}
        def progress(p, msg=None):
            pass
        ExportStage().run(project, progress)
        manifest = json.loads((out / "artifacts/export_manifest.json").read_text())
        perf = manifest.get("performance", {}).get("segments") or []
        report["segment_performance"] = perf
        report["manifest_keys"] = sorted(manifest)
        if not perf or any(s.get("rendered_from") != "original" or s.get("cached") is not False for s in perf):
            raise RuntimeError("original uncached segment render not proven")
        mp4 = list((out / "exports").rglob("*.mp4"))
        if len(mp4) != 1:
            raise RuntimeError(f"expected exactly one final mp4; got {len(mp4)}")
        result = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
            "stream=width,height,avg_frame_rate,codec_name:stream_side_data=rotation", "-of", "json", str(mp4[0])],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=True)
        report["ffprobe_output"] = json.loads(result.stdout)
        report["output_bytes"] = mp4[0].stat().st_size
        report["output_mp4"] = str(mp4[0])
        report["status"] = "PASS_IPHONE_ORIGINAL_UNCACHED_EXPORT_NEEDS_VISUAL_REVIEW"
    except BaseException as exc:
        report["status"] = "FAIL"
        report["error"] = repr(exc)
        report["traceback_tail"] = traceback.format_exc()[-1800:]
        raise
    finally:
        report["elapsed_sec"] = round(time.monotonic() - start, 3)
        (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps(report, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
