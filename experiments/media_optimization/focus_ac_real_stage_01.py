#!/usr/bin/env python3
"""FOCUS A/C single real-media handoff experiment; run ONLY on explicit clearance.

Stages short real-media proxies, confirms source/proxy engine resolution, creates a
minimal laboratory edit-plan fixture, measures CPU and elapsed time, and reports.
Does NOT run Zucker edit planning or final render. Source files are never written.
Uses isolated output directory; output must not exist.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"engine"))
from focus_ac_vm_cpu_guard import sample_cpu, processes

SOURCES=[
    ("iphone","IMG_0044.MOV",640,360),
    ("sony","C0188.MP4",640,360),
    ("spherical","VID_20260824_204524_00_004.mp4",960,480),
]

def probe(path):
    result=subprocess.run(["ffprobe","-v","error","-select_streams","v:0",
      "-show_entries","stream=codec_name,width,height,avg_frame_rate,side_data_list:format=duration",
      "-of","json",str(path)],capture_output=True,text=True,timeout=45,check=True)
    return json.loads(result.stdout)

def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(2*1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def safety():
    util=sample_cpu(2)
    load=os.getloadavg()
    active=processes()
    cores=os.cpu_count() or 1
    if active or util is None or util>=65 or load[0]>=cores*.75:
        raise RuntimeError(f"Shared VM busy: cpu={util:.1f}% load={load[0]:.1f} ffmpeg/ffprobe={active}")
    return {"cpu_percent":round(util,1),"load_1m":round(load[0],2),"logical_cpus":cores}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-dir",type=Path,default=Path("/home/fer/lab-clips/originales"))
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--seconds",type=float,default=4.0)
    p.add_argument("--start",type=float,default=10.0)
    p.add_argument("--approved-by-chema",action="store_true",
                  help="Operator confirms Chema explicitly cleared CPU time")
    args=p.parse_args()
    if not args.approved_by_chema:
        p.error("Require explicit --approved-by-chema; never auto-launch heavy jobs")
    if not 1<=args.seconds<=6 or not 0<=args.start<=120:
        p.error("Only 1..6 seconds from offset 0..120 allowed")
    out=args.output.resolve()
    if out.exists():p.error("Refusing to overwrite output directory")
    files=[(name,(args.source_dir/f).resolve(strict=True),w,h) for name,f,w,h in SOURCES]
    for _,src,_,_ in files:
        if not src.is_file():p.error(f"Missing original: {src.name}")
    if shutil.disk_usage(out.parent if out.parent.exists() else Path("/home/fer")).free < 1_500_000_000:
        p.error("Less than 1.5GB free disk: refuse")
    first=safety()
    import time as _t
    begin=_t.monotonic()
    out.mkdir(parents=True)
    report={"experiment":"FOCUS_AC_REAL_STAGE_01","preflight":first,
        "started_epoch":time.time(),"sources":[],"segments":[],
        "status":"INCOMPLETE","true_proxy_authored_edit_plan":False,
        "render_from_originals":False,
        "limitations":["Lab fixture only; no Zucker cut/edit stage invoked.",
          "No final export / frame / audio parity verified.",
          "Hashing reads entire original files; can consume disk I/O under shared VM.",
          "For iPhone, FFmpeg autorotation changes proxy display orientation; ensure comparison by display matrix."]}
    try:
        # Do not compete with a suddenly active Chema FFmpeg between sources.
        for idx,(name,src,w,h) in enumerate(files):
            safety()
            before=probe(src)
            sha_before=digest(src)
            dst=out/f"{idx+1}-{name}-proxy.mp4"
            # The 360 input is kept equirectangular; flat originals are scaled
            # after autorotation. No forced FPS conversion.
            vf=f"scale={w}:{h}:flags=bilinear,format=yuv420p"
            cmd=["ffmpeg","-hide_banner","-nostdin","-loglevel","error",
              "-threads","2","-ss",str(args.start),"-t",str(args.seconds),
              "-i",str(src),"-map","0:v:0","-an","-vf",vf,
              "-c:v","libx264","-threads","2","-preset","ultrafast",
              "-crf","30","-movflags","+faststart","-y",str(dst)]
            start=_t.monotonic()
            subprocess.run(cmd,check=True,timeout=180)
            elapsed=round(_t.monotonic()-start,3)
            after=probe(dst)
            sha_after=digest(src)
            if sha_after!=sha_before:raise RuntimeError(f"Original modified {src.name}")
            d=float(after["format"]["duration"])
            if not abs(d-args.seconds)<.5:raise RuntimeError(f"Proxy duration unexpected {name}: {d}")
            rec={"camera_id":name,"path":str(src),
                 "normalized":{"path":str(dst),"kind":"proxy"},
                 "probe":{"projection":"equirect" if name=="spherical" else None,
                          "width":before["streams"][0]["width"],"height":before["streams"][0]["height"]}}
            from core.project import Project
            from core.stages.export import _segment_source_info
            segment={"camera_id":name,"source_path":str(src),
               "clip_path":str(dst),"master_start_sec":0.0,
               "clip_start_sec":args.start,"duration_sec":args.seconds,
               "projection":"equirect" if name=="spherical" else None}
            resolved=_segment_source_info(Project(out,{"inputs":{"videos":[rec]}}),segment)
            if resolved["source_path"]!=str(src) or resolved["proxy_path"]!=str(dst):
                raise RuntimeError(f"Engine handoff mismatch: {name}")
            report["sources"].append({"camera":name,"original":src.name,
               "original_sha256":sha_before,"original_size":src.stat().st_size,
               "original_codec":before["streams"][0]["codec_name"],
               "proxy":dst.name,"proxy_size":dst.stat().st_size,
               "proxy_resolution":f"{w}x{h}","proxy_duration":d,
               "transcode_seconds":elapsed,"engine_resolver_pass":True})
            report["segments"].append(segment)
            (out/"report.json").write_text(json.dumps(report,indent=2)+"\n")
        report["status"]="PASS_REAL_MEDIA_HANDOFF_FIXTURE"
        report["total_seconds"]=round(_t.monotonic()-begin,3)
    except BaseException as exc:
        report["status"]="FAIL_OR_INTERRUPTED"
        report["error"]=str(exc)
        raise
    finally:
        (out/"report.json").write_text(json.dumps(report,indent=2)+"\n")
        print(json.dumps({"status":report["status"],"total_seconds":report.get("total_seconds"),
           "cameras_completed":len(report["sources"]),"output":str(out),
           "limits":report["limitations"]},indent=2))

if __name__=="__main__":main()
