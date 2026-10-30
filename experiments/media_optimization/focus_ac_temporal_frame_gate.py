#!/usr/bin/env python3
"""FOCUS A/C temporal mapping gate: sampled frame correspondence, bounded.
No full-media transcodes, no edits to originals or engine. Needs Pillow.
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path
from focus_ac_vm_cpu_guard import sample_cpu, processes

FILES=[
 ("iphone","IMG_0044.MOV","1-iphone-proxy.mp4",640,360),
 ("sony","C0188.MP4","2-sony-proxy.mp4",640,360),
 ("spherical","VID_20260824_204524_00_004.mp4","3-spherical-proxy.mp4",960,480)]
def frame(path,at,w,h):
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin",
         "-threads","2","-ss",str(at),"-i",str(path),"-frames:v","1",
         "-vf",f"scale={w}:{h}:flags=bilinear,format=rgb24",
         "-f","rawvideo","-pix_fmt","rgb24","-"]
    p=subprocess.run(cmd,capture_output=True,timeout=90)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors="replace")[-700:])
    if len(p.stdout)!=w*h*3:raise RuntimeError("Unexpected decoded frame size")
    return p.stdout
def mean_error(a,b):
    return sum(abs(x-y) for x,y in zip(a,b))/(len(a)*255)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source-dir",type=Path,default=Path("/home/fer/lab-clips/originales"))
    ap.add_argument("--stage-dir",type=Path,default=Path("/home/fer/montara-focus-ac-real-01"))
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--approved-by-chema",action="store_true")
    args=ap.parse_args()
    if not args.approved_by_chema:ap.error("Explicit --approved-by-chema required")
    if args.output.exists():ap.error("Refusing to overwrite existing report")
    load=os.getloadavg()[0]; cpu=sample_cpu(2); active=processes()
    if cpu is None or cpu>=65 or load >=(os.cpu_count() or 1)*.75 or active:
        raise SystemExit(f"VM busy: cpu={cpu}, load={load:.2f}, ffmpeg={active}")
    result={"status":"INCOMPLETE","preflight_cpu_percent":round(cpu,1),
            "sample_points":[0.5,2.0,3.5],"original_clip_offset_sec":10.0,
            "cameras":[],"note":"Mean absolute pixel error is diagnostic, not SSIM or proof of exact frame identity"}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    try:
        for name,original,proxy,w,h in FILES:
            if processes():raise RuntimeError("Concurrent ffmpeg detected; stop")
            src=args.source_dir/original; dst=args.stage_dir/proxy
            if not src.is_file() or not dst.is_file():raise RuntimeError(f"Missing media for {name}")
            differences=[]
            for at in result["sample_points"]:
                a=frame(src,10+at,w,h)
                b=frame(dst,at,w,h)
                differences.append({"original_sec":10+at,"proxy_sec":at,
                                    "mean_abs_normalized_pixel_error":round(mean_error(a,b),6)})
            # Threshold loose enough for lossy CRF30 proxy, yet detects obvious
            # erroneous timestamp and orientation. False passes possible.
            maxerr=max(v["mean_abs_normalized_pixel_error"] for v in differences)
            result["cameras"].append({"camera":name,"samples":differences,
                                      "max_error":maxerr,"sample_gate_pass":maxerr<0.20})
            args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
        result["status"]="PASS_SAMPLED_TIMING" if all(c["sample_gate_pass"] for c in result["cameras"]) else "REVIEW_FRAME_MISMATCH"
    except Exception as ex:
        result["status"]="ERROR";result["error"]=str(ex)
        raise
    finally:
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
        print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
