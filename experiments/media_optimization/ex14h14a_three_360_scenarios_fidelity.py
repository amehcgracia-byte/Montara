#!/usr/bin/env python3
"""EX-14H-14A: Stage real HEVC 360 multi-pose fidelity screen, no engine edits.

Three scenarios x A/B = six real ExportStage exports. Changes only the local
temporary fixture's spherical_shot via a temporary in-process setup_project
wrapper. Hashes original BGR frames received by remap and BGR output before
encoding; checks preencoder bit-exact A/B, plus native calls and PCM audio.

Do not use instrumented Stage wall times as performance benchmark: BGR hashing
adds overhead. Real 360 source, 2 s, 60 frames; NOT a multicamera long E2E.
"""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

BASE = Path(__file__).with_name("ex14h11_stage_real_hevc_export_abba.py")
if not BASE.is_file():
    raise SystemExit("STOP: missing sibling EX14H11 harness")
spec = importlib.util.spec_from_file_location("verified_stage_harness", BASE)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)

SCENARIOS = (
    ("fixed_hold", {
        "type": "stage", "yaw": 0.0, "pitch": 0.0, "fov": 95.0,
        "projection_preset": "linear", "runtime_motion_enabled": True,
        "movement": "hold", "hold_motion_rate_deg_per_sec": 0.0,
    }),
    ("moving_pan", {
        "type": "stage", "yaw": 180.0, "pitch": -30.0, "fov": 100.0,
        "projection_preset": "linear", "runtime_motion_enabled": True,
        "hold_motion_rate_deg_per_sec": 9.0,
    }),
    ("seam_pole", {
        "type": "stage", "yaw": 179.4, "pitch": 68.0, "fov": 145.0,
        "projection_preset": "linear", "runtime_motion_enabled": True,
        "movement": "pan_right", "music_style": "frenetico",
        "hold_motion_rate_deg_per_sec": 9.0,
    }),
)

@contextmanager
def scenario_setup(shot, name):
    original = h.setup_project
    def configured(destination, selected_source, mode):
        doc, segment = original(destination, selected_source, mode)
        segment["spherical_shot"] = dict(shot)
        doc["name"] = f"EX14H14-{name}-{mode}"
        path = destination / "project.json"
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
        planpath = destination / "artifacts/edit_plan.json"
        plan = json.loads(planpath.read_text(encoding="utf-8"))
        plan["segments"] = [segment]
        planpath.write_text(json.dumps(plan, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
        return doc, segment
    h.setup_project = configured
    try:
        yield
    finally:
        h.setup_project = original


@contextmanager
def observe_preencoder():
    import core.spherical_motion as sm
    original_remap = sm.cv2.remap
    original_maps = sm.reproject_maps
    input_hashes = []
    output_hashes = []
    map_calls = [0]
    map_hashes = []
    def maps_wrapper(*args, **kwargs):
        result = original_maps(*args, **kwargs)
        map_calls[0] += 1
        # Hash a map representation to ensure A/B produce same reprojection
        # coordinates, independently of the source frame.
        map_hash = hashlib.sha256()
        for arr in result:
            view = memoryview(arr)
            if not view.c_contiguous:
                raise RuntimeError("STOP: noncontiguous coordinate map")
            map_hash.update(view.cast("B"))
        map_hashes.append(map_hash.hexdigest())
        return result
    def remap_wrapper(*args, **kwargs):
        source = args[0] if args else kwargs.get("src")
        if source is None or source.shape != (1920, 3840, 3):
            raise RuntimeError("STOP: unexpected HEVC frame shape")
        inp = memoryview(source)
        if not inp.c_contiguous:
            raise RuntimeError("STOP: noncontiguous HEVC frame")
        input_hashes.append(hashlib.sha256(inp.cast("B")).hexdigest())
        result = original_remap(*args, **kwargs)
        output = result if result is not None else kwargs.get("dst")
        if output is None or output.shape != (1080, 1920, 3):
            raise RuntimeError("STOP: unexpected BGR output frame shape")
        view = memoryview(output)
        if not view.c_contiguous:
            raise RuntimeError("STOP: noncontiguous BGR frame")
        output_hashes.append(hashlib.sha256(view.cast("B")).hexdigest())
        return result
    sm.reproject_maps = maps_wrapper
    sm.cv2.remap = remap_wrapper
    try:
        yield {
            "input_hashes":input_hashes, "output_hashes":output_hashes,
            "map_calls":map_calls, "map_hashes":map_hashes
        }
    finally:
        sm.reproject_maps = original_maps
        sm.cv2.remap = original_remap


def main():
    if h.capture(["git","-C",str(h.ROOT),"rev-parse","--short","HEAD"]) != "0f9ec03":
        raise RuntimeError("STOP: expected isolated lab engine at 0f9ec03")
    if h.capture(["git","-C",str(h.ROOT),"status","--porcelain"]):
        raise RuntimeError("STOP: dirty engine checkout")
    if shutil.disk_usage("/home/fer").free < 12 * 1024**3:
        raise RuntimeError("STOP: less than 12 GiB disk free")
    selected = h.source()
    original_stat = (selected.stat().st_size, selected.stat().st_mtime_ns)
    sys.path.insert(0, str(h.ROOT))
    results = []
    print("EX14H14A_START " + json.dumps({
        "scenarios":[name for name,_ in SCENARIOS],
        "source":"real original HEVC 3840x1920",
        "exports_per_scenario":2, "frames_per_export":60,
        "warning":"hashed map/BGR buffers distort timings; no speed claim",
    }),flush=True)
    with tempfile.TemporaryDirectory(prefix="jupiter_ex14h14a_",dir="/home/fer") as tmp:
        root=Path(tmp)
        for scenario_index,(name,shot) in enumerate(SCENARIOS):
            scenario_results=[]
            for mode_index, mode in enumerate(("A","B")):
                if shutil.disk_usage("/home/fer").free < 12 * 1024**3:
                    raise RuntimeError("STOP: disk free under safety threshold")
                with scenario_setup(shot,name),observe_preencoder() as recorded:
                    output=h.run_one(root,selected,mode,1+scenario_index*2+mode_index)
                inputs=recorded["input_hashes"]
                frames=recorded["output_hashes"]
                map_hashes=recorded["map_hashes"]
                map_calls=recorded["map_calls"][0]
                if len(inputs)!=60 or len(frames)!=60 or map_calls<1 or map_calls>60:
                    raise RuntimeError(
                        f"STOP: scenario={name} {mode}, frames={len(frames)}, maps={map_calls}"
                    )
                if (selected.stat().st_size, selected.stat().st_mtime_ns)!=original_stat:
                    raise RuntimeError("STOP: input video changed")
                summary={
                    "scenario":name,"mode":mode,
                    "input_sha_sequence":hashlib.sha256("".join(inputs).encode()).hexdigest(),
                    "preencoder_sha_sequence":hashlib.sha256("".join(frames).encode()).hexdigest(),
                    "map_sha_sequence":hashlib.sha256("".join(map_hashes).encode()).hexdigest(),
                    "map_calls":map_calls,
                    "audio_sha":output["audio_pcm_sha256"],
                    "output_frames":output["video_frames"],
                    "warnings":output["warnings"],
                    "raw_inputs":inputs,"raw_outputs":frames,"raw_maps":map_hashes
                }
                scenario_results.append(summary)
                print("EX14H14A_RUN "+json.dumps({
                    k:v for k,v in summary.items() if not k.startswith("raw_")
                }),flush=True)
            a,b=scenario_results
            comparison={
                "scenario":name,
                "decoded_input_exact_frames":sum(x==y for x,y in zip(a["raw_inputs"],b["raw_inputs"])),
                "preencoder_exact_frames":sum(x==y for x,y in zip(a["raw_outputs"],b["raw_outputs"])),
                "map_count_a":a["map_calls"],
                "map_count_b":b["map_calls"],
                "map_hashes_exact":a["raw_maps"]==b["raw_maps"],
                "audio_pcm_exact":a["audio_sha"]==b["audio_sha"],
                "pass":a["raw_inputs"]==b["raw_inputs"] and
                       a["raw_outputs"]==b["raw_outputs"] and
                       a["raw_maps"]==b["raw_maps"] and
                       a["audio_sha"]==b["audio_sha"],
            }
            results.append(comparison)
            print("EX14H14A_SCENARIO "+json.dumps(comparison),flush=True)
    report={"scenarios_passed":sum(x["pass"] for x in results),
            "scenarios_total":len(SCENARIOS),
            "details":results,
            "scope":"single 2-second original HEVC clip, 3 authored viewpoints, 2 runs each",
            "no_production_changes":True}
    print("EX14H14A_RESULT "+json.dumps(report,indent=2),flush=True)
    if not all(x["pass"] for x in results):
        raise RuntimeError("STOP: preencoder fidelity mismatch in one or more scenarios")
    print("EX14H14A_COMPLETE_TEMP_FILES_CLEANED",flush=True)


if __name__=="__main__":
    main()
