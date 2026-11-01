#!/usr/bin/env python3
"""EX-05: bounded native-remap CPU A/B on real 360 source. No engine changes.

Measure changing-pose map generation + 3 remapping variants on identical frames.
Reference = current cv2.INTER_CUBIC with float maps. No files written.
"""
import json, math, subprocess, sys, time
from pathlib import Path
import numpy as np
import cv2

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"engine"))
from core.spherical_motion import reproject_maps

SOURCE=Path("/home/fer/lab-clips/originales/VID_20260824_204524_00_004.mp4")
SW,SH=3840,1920
OW,OH=960,540
FPS=6
DURATION=2
START=840
SHOT={"yaw":180.0,"pitch":-30.0,"fov":100.0,"type":"full_stage","projection_preset":"linear",
      "roll":0,"runtime_motion_enabled":True}
def ms(t): return round(t*1000,3)
def timed(f):
    t=time.perf_counter()
    v=f()
    return v,time.perf_counter()-t
def main():
    if not SOURCE.is_file():raise SystemExit("Missing real 360 sample")
    print("VERSIONS",json.dumps({"opencv":cv2.__version__,"numpy":np.__version__,"source_size":[SW,SH],"output_size":[OW,OH],"frames_limit":FPS*DURATION}),flush=True)
    cmd=["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-ss",str(START),"-i",str(SOURCE),
         "-t",str(DURATION),"-map","0:v:0","-vf",f"fps={FPS},format=bgr24",
         "-an","-f","rawvideo","pipe:1"]
    proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    assert proc.stdout is not None
    nbytes=SW*SH*3
    frame_times=[]
    try:
        for i in range(FPS*DURATION):
            data=bytearray(nbytes)
            view=memoryview(data)
            filled=0
            while filled<nbytes:
                n=proc.stdout.readinto(view[filled:])
                if not n: break
                filled+=n
            if filled!=nbytes:
                raise RuntimeError(f"Decoder frame {i}: received {filled}/{nbytes}")
            frame=np.frombuffer(data,np.uint8).reshape(SH,SW,3)
            pose=(180+0.3*i,-30.0,100.0)
            maps,gen_sec=timed(lambda:reproject_maps((SW,SH),(OW,OH),SHOT,pose))
            cubic,cubic_sec=timed(lambda:cv2.remap(frame,*maps,interpolation=cv2.INTER_CUBIC,borderMode=cv2.BORDER_WRAP))
            linear,linear_sec=timed(lambda:cv2.remap(frame,*maps,interpolation=cv2.INTER_LINEAR,borderMode=cv2.BORDER_WRAP))
            fixed,convert_sec=timed(lambda:cv2.convertMaps(*maps,cv2.CV_16SC2))
            linear_fixed,fixed_sec=timed(lambda:cv2.remap(frame,*fixed,interpolation=cv2.INTER_LINEAR,borderMode=cv2.BORDER_WRAP))
            # Comparison to bicubic reference. Differences include interpolation method.
            mae=float(np.abs(cubic.astype(np.int16)-linear.astype(np.int16)).mean())
            psnr=float(cv2.PSNR(cubic,linear))
            fixed_delta=float(np.abs(linear.astype(np.int16)-linear_fixed.astype(np.int16)).mean())
            frame_times.append({"frame":i,"map_ms":ms(gen_sec),"cubic_ms":ms(cubic_sec),
                "linear_ms":ms(linear_sec),"convert_ms":ms(convert_sec),"fixed_remap_ms":ms(fixed_sec),
                "mae_cubic_linear":round(mae,4),"psnr_cubic_linear_db":round(psnr,3),
                "mae_linear_fixed":round(fixed_delta,4)})
        proc.stdout.close()
        err=proc.stderr.read().decode(errors="replace") if proc.stderr else ""
        code=proc.wait(timeout=20)
        if code:raise RuntimeError(f"ffmpeg decoder exit {code}: {err[-500:]}")
    finally:
        if proc.poll() is None:proc.kill();proc.wait()
    # Exclude first frame (thread pool/warmup cold-start) from comparative averages.
    rows=frame_times[1:]
    keys=("map_ms","cubic_ms","linear_ms","convert_ms","fixed_remap_ms","mae_cubic_linear","psnr_cubic_linear_db","mae_linear_fixed")
    avg={k:round(float(np.mean([r[k] for r in rows])),4) for k in keys}
    base=avg["map_ms"]+avg["cubic_ms"]
    alt=avg["map_ms"]+avg["linear_ms"]
    fixed=avg["map_ms"]+avg["convert_ms"]+avg["fixed_remap_ms"]
    print("AVERAGES_EXCLUDING_FIRST_FRAME",json.dumps(avg),flush=True)
    print("PIPELINE_COMPARE",json.dumps({"baseline_map_plus_cubic_ms":round(base,3),
        "map_plus_linear_ms":round(alt,3),"map_plus_convert_plus_fixed_ms":round(fixed,3),
        "linear_savings_pct":round(100*(1-alt/base),2),
        "fixed_savings_pct":round(100*(1-fixed/base),2)}),flush=True)
    print("ALL_FRAMES",json.dumps(frame_times),flush=True)
    print("LIMITATIONS: real 360 input, dynamic poses, 960x540 only; excludes encode and audio; no whole-export speedup claim. PSNR compares linear to cubic, not to ground truth.")
    print("NO_FILES_WRITTEN")
if __name__=="__main__":main()
