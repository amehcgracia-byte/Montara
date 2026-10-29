"""SATURNO-03D external QA evidence gate (never asserts true source timeline).

Requires Python 3.11+ and ffmpeg/ffprobe in PATH. Read-only on input media.
"""
import argparse,hashlib,json,math,subprocess
from pathlib import Path

def probe(path):
    p=subprocess.run(["ffprobe","-v","error","-show_entries",
        "stream=index,codec_type,codec_name,start_time,duration,time_base:format=start_time,duration",
        "-of","json",str(path)],capture_output=True,text=True,timeout=30)
    if p.returncode:raise ValueError("ffprobe failed: "+p.stderr[-400:])
    return json.loads(p.stdout)

def frames(path):
    p=subprocess.run(["ffprobe","-v","error","-select_streams","v:0",
        "-show_frames","-show_entries","frame=best_effort_timestamp_time,key_frame,pict_type",
        "-of","json",str(path)],capture_output=True,text=True,timeout=45)
    if p.returncode:raise ValueError("frame probe failed: "+p.stderr[-400:])
    return json.loads(p.stdout).get("frames",[])

def digest(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):h.update(chunk)
    return h.hexdigest()

def check_media(fragment,declared_origin,segment_origin,segment_duration,master=None,master_sha=None):
    path=Path(fragment)
    if not path.is_file():raise ValueError("missing fragment")
    for v in (declared_origin,segment_origin,segment_duration):
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):
            raise ValueError("invalid timing")
    if declared_origin<0 or segment_origin<0 or segment_duration<=0:raise ValueError("invalid window")
    meta=probe(path)
    stream=next((s for s in meta.get("streams",[]) if s.get("codec_type")=="video"),None)
    if not stream:raise ValueError("fragment has no video stream")
    points=[float(f["best_effort_timestamp_time"]) for f in frames(path)
        if f.get("best_effort_timestamp_time") is not None]
    if not points:raise ValueError("missing decoded frame timing")
    relative=segment_origin-declared_origin
    result={"schema":"saturno-03d-av-gate-v1",
        "status":"BLOCKED_SOURCE_TIMELINE_UNPROVEN","input_sha256":digest(path),
        "input_bytes":path.stat().st_size,"first_decoded_pts_sec":points[0],
        "last_decoded_pts_sec":max(points),"decoded_frame_count":len(points),
        "stream_time_base":stream.get("time_base"),
        "declared_source_origin_sec":declared_origin,
        "requested_source_window_sec":[segment_origin,segment_origin+segment_duration],
        "arithmetic_local_window_sec":[relative,relative+segment_duration],
        "reasons":["Fragment PTS alone do not prove original source-time correspondence.",
          "GOP closure, output equality, and Zucker E2E are not established."]}
    if master is not None:
        audio=Path(master)
        if not audio.is_file():raise ValueError("missing master")
        actual=digest(audio)
        if not master_sha or actual!=master_sha:raise ValueError("master SHA mismatch")
        streams=[s for s in probe(audio).get("streams",[]) if s.get("codec_type")=="audio"]
        if not streams:raise ValueError("master has no audio")
        result["master"]={"bytes":audio.stat().st_size,"sha256":actual,
            "codec":streams[0].get("codec_name")}
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--fragment",type=Path,required=True)
    p.add_argument("--source-origin",type=float,required=True)
    p.add_argument("--cut-start",type=float,required=True)
    p.add_argument("--cut-duration",type=float,required=True)
    p.add_argument("--master",type=Path)
    p.add_argument("--master-sha256")
    p.add_argument("--report",type=Path)
    a=p.parse_args()
    data=check_media(a.fragment,a.source_origin,a.cut_start,a.cut_duration,a.master,a.master_sha256)
    result=json.dumps(data,indent=2)+"\n"
    if a.report:a.report.write_text(result)
    else:print(result,end="")
    raise SystemExit(3)  # fail-closed, evidence is not acceptance
