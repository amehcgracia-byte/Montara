#!/usr/bin/env python3
"""EX-14H-14B: 15/18-second 360 Stage A/B, multiple real source windows.

Fidelity and performance modes deliberately separate: fidelity computes hashes
of real decoded input frames, map coordinates and projected preencoder BGR;
performance runs the same Stage without this expensive instrumentation.

Only run one job at a time on shared 8-vCPU VM. Temporary isolated project,
cache and exports. Never alters engine, global ffmpeg, or source originals.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

BASE=Path(__file__).with_name("ex14h11_stage_real_hevc_export_abba.py")
if not BASE.is_file():
    raise SystemExit("STOP: sibling EX14H11 Stage harness missing")
spec=importlib.util.spec_from_file_location("verified_stage_harness",BASE)
h=importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
MIN_FREE_GIB=12
WINDOWS=(600.0,840.0)
SHOT={
    "type":"stage", "yaw":179.4, "pitch":-30.0, "fov":110.0,
    "projection_preset":"linear", "runtime_motion_enabled":True,
    "hold_motion_rate_deg_per_sec":9.0,
}

def source_duration(path):
    raw=subprocess.check_output([
        "ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1",str(path)
    ],text=True).strip()
    return float(raw)

def available_ram_gib():
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return round(int(line.split()[1])/1024**2,2)
    raise RuntimeError("STOP: MemAvailable missing")

def safety(*, first=False):
    free=shutil.disk_usage("/home/fer").free/(1024**3)
    avail=available_ram_gib()
    if free<MIN_FREE_GIB:
        raise RuntimeError(f"STOP: disk free {free:.2f}GiB <{MIN_FREE_GIB}GiB")
    if avail<8:
        raise RuntimeError(f"STOP: available RAM {avail:.2f}GiB <8GiB")
    if first and os.getloadavg()[0]>2.5:
        raise RuntimeError(f"STOP: current host load {os.getloadavg()[0]:.2f} too high")
    # Conservative check for active JM ffmpeg/video jobs, without killing anything.
    ps=subprocess.check_output(["ps","-eo","user=,comm="],text=True)
    for line in ps.splitlines():
        fields=line.split(None,1)
        if len(fields)==2 and fields[0]=="jm" and fields[1] in ("ffmpeg","ffprobe"):
            raise RuntimeError("STOP: JM video process active")
    return {"disk_free_gib":round(free,2),"ram_available_gib":avail}

@contextmanager
def stage_params(seconds, start):
    old=h.setup_project
    def configured(destination, selected_source, mode):
        doc,segment=old(destination,selected_source,mode)
        segment.update({
            "clip_start_sec":start,"duration_sec":seconds,
            "frame_count":int(round(seconds*30)),
            "spherical_shot":dict(SHOT),
        })
        doc["name"]=f"EX14H14B-{int(seconds)}s-{int(start)}-{mode}"
        (destination/"project.json").write_text(
            json.dumps(doc,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        planfile=destination/"artifacts/edit_plan.json"
        plan=json.loads(planfile.read_text(encoding="utf-8"))
        plan.update({
            "segments":[segment],"duration_sec":seconds,
            "master_window_start_sec":0.0,"cut_count":0,
        })
        planfile.write_text(json.dumps(plan,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        return doc,segment
    h.setup_project=configured
    try:yield
    finally:h.setup_project=old

@contextmanager
def fidelity_observer():
    import core.spherical_motion as sm
    oldmap=sm.reproject_maps
    oldremap=sm.cv2.remap
    counts={"maps":0,"frames":0}
    digests={"input":hashlib.sha256(),"preencoder":hashlib.sha256(),"maps":hashlib.sha256()}
    def map_hook(*args,**kwargs):
        result=oldmap(*args,**kwargs)
        counts["maps"]+=1
        for arr in result:
            v=memoryview(arr)
            if not v.c_contiguous:
                raise RuntimeError("STOP: noncontiguous map")
            digests["maps"].update(v.cast("B"))
        return result
    def remap_hook(*args,**kwargs):
        source=args[0] if args else kwargs.get("src")
        if source is None or source.shape!=(1920,3840,3):
            raise RuntimeError("STOP: unexpected HEVC BGR shape")
        inp=memoryview(source)
        if not inp.c_contiguous:raise RuntimeError("STOP: input BGR noncontiguous")
        digests["input"].update(inp.cast("B"))
        result=oldremap(*args,**kwargs)
        output=result if result is not None else kwargs.get("dst")
        if output is None or output.shape!=(1080,1920,3):
            raise RuntimeError("STOP: unexpected projected BGR shape")
        v=memoryview(output)
        if not v.c_contiguous:raise RuntimeError("STOP: projected BGR noncontiguous")
        digests["preencoder"].update(v.cast("B"))
        counts["frames"]+=1
        return result
    sm.reproject_maps=map_hook
    sm.cv2.remap=remap_hook
    try:yield counts,digests
    finally:
        sm.reproject_maps=oldmap
        sm.cv2.remap=oldremap

def verify_audio_master():
    fixture=json.loads((h.REFERENCE/"project.json").read_text())
    master=(fixture.get("inputs",{}).get("master") or {}).get("path")
    if not master or not Path(master).is_file():
        raise RuntimeError("STOP: fixture audio master not available")
    return source_duration(Path(master))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=("fidelity","performance"),required=True)
    p.add_argument("--duration",type=int,choices=(15,18),default=15)
    args=p.parse_args()
    safety(first=True)
    if h.capture(["git","-C",str(h.ROOT),"rev-parse","--short","HEAD"])!="0f9ec03":
        raise RuntimeError("STOP: expected isolated experimental engine 0f9ec03")
    if h.capture(["git","-C",str(h.ROOT),"status","--porcelain"]):
        raise RuntimeError("STOP: experimental engine worktree dirty")
    if not (h.REFERENCE/"project.json").is_file():
        raise RuntimeError("STOP: reference Stage project missing")
    selected=h.source()
    source_length=source_duration(selected)
    master_length=verify_audio_master()
    if any(start+args.duration+0.2>source_length for start in WINDOWS):
        raise RuntimeError(f"STOP: 360 original duration {source_length:.1f}s too short for requested windows")
    if master_length < args.duration+0.1:
        raise RuntimeError(f"STOP: audio master {master_length:.1f}s too short for {args.duration}s")
    original_stat=(selected.stat().st_size,selected.stat().st_mtime_ns)
    h.FRAMES=args.duration*30
    sys.path.insert(0,str(h.ROOT))
    order=("A","B") if args.mode=="fidelity" else ("A","B","B","A")
    rows=[]
    print("EX14H14B_START "+json.dumps({
        "mode":args.mode,"duration_sec":args.duration,"frames_per_job":h.FRAMES,
        "window_starts_sec":WINDOWS,"order_per_window":order,
        "original_duration_sec":round(source_length,3),
        "master_duration_sec":round(master_length,3),
        "safety":safety(),
        "scope":"real original HEVC 360 Stage Reel 1080p30, single job at a time",
        "warning":"fidelity timings contain hashing; performance timings do not"
    }),flush=True)

    with tempfile.TemporaryDirectory(prefix="jupiter_ex14h14b_",dir="/home/fer") as tmp:
        root=Path(tmp)
        for wi,start in enumerate(WINDOWS):
            pairs=[]
            for j,mode in enumerate(order):
                safety()
                index=100*wi+j+1
                with stage_params(args.duration,start):
                    if args.mode=="fidelity":
                        with fidelity_observer() as (count,digest):
                            output=h.run_one(root,selected,mode,index)
                        if count["frames"]!=h.FRAMES:
                            raise RuntimeError(f"STOP: expected {h.FRAMES} frames, got {count['frames']}")
                        if not 1<=count["maps"]<=h.FRAMES:
                            raise RuntimeError(f"STOP: map count {count['maps']} invalid")
                        hashes={k:v.hexdigest() for k,v in digest.items()}
                    else:
                        output=h.run_one(root,selected,mode,index)
                        hashes={}
                if (selected.stat().st_size,selected.stat().st_mtime_ns)!=original_stat:
                    raise RuntimeError("STOP: original video metadata changed")
                row={
                    "window_start_sec":start,"mode":mode,"run":index,
                    "stage_wall_sec":output["wall_sec"],
                    "segment_ffmpeg_sec":output["segment_ffmpeg_sec"],
                    "frames":output["video_frames"],"audio_sha":output["audio_pcm_sha256"],
                    "final_rgb_sha":output["rgb_sha256"],
                    **({"map_calls":count["maps"],"stream_hashes":hashes}
                       if args.mode=="fidelity" else {}),
                }
                pairs.append(row)
                rows.append(row)
                print("EX14H14B_RUN "+json.dumps(row),flush=True)
            if len({r["audio_sha"] for r in pairs})!=1:
                raise RuntimeError("STOP: audio PCM not identical within window")
            if args.mode=="fidelity":
                a,b=pairs
                exact={k:a["stream_hashes"][k]==b["stream_hashes"][k]
                       for k in ("input","preencoder","maps")}
                result={"window_start_sec":start,
                        "exact":exact,"audio_exact":True,
                        "map_calls":[a["map_calls"],b["map_calls"]],
                        "pass":all(exact.values())}
                print("EX14H14B_FIDELITY_WINDOW "+json.dumps(result),flush=True)
                if not result["pass"]:
                    raise RuntimeError("STOP: fidelity A/B mismatch")
            else:
                a=[r["stage_wall_sec"] for r in pairs if r["mode"]=="A"]
                b=[r["stage_wall_sec"] for r in pairs if r["mode"]=="B"]
                ma,mb=sum(a)/2,sum(b)/2
                print("EX14H14B_PERFORMANCE_WINDOW "+json.dumps({
                    "window_start_sec":start,"mean_A_sec":round(ma,3),
                    "mean_B_sec":round(mb,3),
                    "stage_gain_pct":round(100*(ma-mb)/ma,2)
                }),flush=True)
    print("EX14H14B_RESULT "+json.dumps({
        "mode":args.mode,"duration_sec":args.duration,
        "windows_completed":len(WINDOWS),"runs_completed":len(rows),
        "audio_consistent_across_runs":len({r["audio_sha"] for r in rows})==1,
        "temp_media_cleaned":True
    }),flush=True)
    print("EX14H14B_COMPLETE",flush=True)


if __name__=="__main__":
    main()
