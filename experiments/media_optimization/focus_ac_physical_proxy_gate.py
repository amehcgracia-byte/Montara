#!/usr/bin/env python3
"""FOCUS A/C physical proxy gate. Generates isolated 360p test proxies from
the existing 720p E2E clips, validates the pinned engine's resolution and
timeline invariants. Does not export and does not modify source project.
"""
import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"engine"))

def ffprobe(path):
    p=subprocess.run(["ffprobe","-v","error","-show_entries",
        "format=duration:stream=index,codec_type,codec_name,width,height,avg_frame_rate",
        "-of","json",str(path)],capture_output=True,text=True,check=True)
    return json.loads(p.stdout)

def sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--project",type=Path,required=True)
    a.add_argument("--plan",type=Path,required=True)
    a.add_argument("--output",type=Path,required=True)
    args=a.parse_args()
    out=args.output.resolve()
    if out.exists(): a.error("Output already exists. Refusing overwrite.")
    raw=args.project.read_bytes()
    planraw=args.plan.read_bytes()
    project=copy.deepcopy(json.loads(raw))
    plan=copy.deepcopy(json.loads(planraw))
    videos=project["inputs"]["videos"]
    segments=plan["segments"]
    if len(videos)!=2 or len(segments)!=6:
        a.error("Safety gate expects only the known two-camera/six-segment E2E fixture")
    original_by_proxy={}
    records=[]
    out.mkdir(parents=True)
    for i,rec in enumerate(videos,1):
        src=Path(rec["path"]).resolve(strict=True)
        if not src.is_file():raise RuntimeError("Missing original")
        probe=ffprobe(src)
        stream=next(s for s in probe["streams"] if s["codec_type"]=="video")
        if (stream["width"],stream["height"])!=(1280,720):
            raise RuntimeError("Only 1280x720 originals are allowed in this controlled gate")
        dest=out/f"camera-{i}-proxy-360p.mp4"
        command=["ffmpeg","-hide_banner","-nostdin","-loglevel","error","-y",
            "-i",str(src),"-map","0:v:0","-map","0:a?","-vf",
            "scale=640:360,fps=30,format=yuv420p",
            "-c:v","libx264","-preset","veryfast","-crf","24","-c:a","aac","-b:a","128k",
            "-movflags","+faststart",str(dest)]
        subprocess.run(command,check=True,timeout=180)
        second=ffprobe(dest)
        v=next(s for s in second["streams"] if s["codec_type"]=="video")
        if (v["width"],v["height"])!=(640,360):raise AssertionError("Bad proxy dimensions")
        d0=float(probe["format"]["duration"]);d1=float(second["format"]["duration"])
        if abs(d0-d1)>0.10:raise AssertionError(f"Proxy duration mismatch {d0} vs {d1}")
        rec.setdefault("normalized",{})["path"]=str(dest)
        rec["normalized"]["kind"]="proxy"
        original_by_proxy[str(src)]=str(dest)
        records.append({"camera":i,"source_basename":src.name,"original_sha256":sha(src),
                        "source_duration":d0,"proxy_duration":d1,
                        "proxy_resolution":"640x360","proxy_bytes":dest.stat().st_size})
    from core.project import Project
    from core.stages.export import _segment_source_info
    mock=Project(out/"virtual_project",project)
    matches=[]
    for i,s in enumerate(segments,1):
        source=str(Path(s.get("source_path") or s.get("clip_path")).resolve())
        if source not in original_by_proxy:raise AssertionError(f"Unknown source for segment {i}")
        proxy=original_by_proxy[source]
        s["source_path"]=source
        s["clip_path"]=proxy
        r=_segment_source_info(mock,s)
        if r["source_path"]!=source or r["proxy_path"]!=proxy:
            raise AssertionError(f"Resolution incorrect segment {i}")
        original=plan["segments"][i-1]
        for k in ("camera_id","master_start_sec","clip_start_sec","duration_sec",
                  "spherical_shot","motion","flat_framing"):
            if s.get(k)!=original.get(k):raise AssertionError(f"Changed {k} segment {i}")
        matches.append({"segment":i,"original_and_proxy_resolved":True,"timeline_preserved":True})
    if args.project.read_bytes()!=raw or args.plan.read_bytes()!=planraw:
        raise AssertionError("Source JSON mutated")
    report={"status":"PASS_PHYSICAL_PROXY_GATE","records":records,"segments":matches,
            "project_original_sha256":hashlib.sha256(raw).hexdigest(),
            "plan_original_sha256":hashlib.sha256(planraw).hexdigest(),
            "important_limits":["Controlled 720p synthetic originals and 360p test proxies; not 4K/HDR/360.",
               "The saved edit plan was authored from originals, not computed from proxies.",
               "No export, visual fidelity, audio sync or cache reuse equivalence demonstrated.",
               "Does not change main/engine/mixer or existing user projects.",
               "The test transcodes small video samples; run under montara-bench."]}
    (out/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
