#!/usr/bin/env python3
"""EX-06: bounded 1080p real spherical frame CPU remap validation.
Reads real camera source, measures OpenCV variants and writes only one A/B JPEG.
No engine changes, no video encoding. All benchmark comparisons use same maps/frame.
"""
import json, subprocess, sys, time
from pathlib import Path
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"engine"))
from core.spherical_motion import reproject_maps
SRC=Path("/home/fer/lab-clips/originales/VID_20260824_204524_00_004.mp4")
OUT=Path("/home/fer/montara-focus-export-ex06-review.jpg")
SW,SH=3840,1920; OW,OH=1920,1080
SHOT={"yaw":180.,"pitch":-30.,"fov":100.,"type":"full_stage","projection_preset":"linear","roll":0,"runtime_motion_enabled":True}
def timeit(fn):
 t=time.perf_counter();v=fn();return v,(time.perf_counter()-t)*1000
def main():
 if not SRC.exists():raise SystemExit("Original source missing")
 if OUT.exists():raise SystemExit("Output review JPG exists; refusing overwrite")
 print("ENV",json.dumps({"opencv":cv2.__version__,"numpy":np.__version__,"out":[OW,OH],"frames":6}),flush=True)
 cmd=["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-ss","840","-i",str(SRC),"-t","1",
      "-map","0:v:0","-vf","fps=6,format=bgr24","-an","-f","rawvideo","pipe:1"]
 proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 rows=[]
 try:
  for i in range(6):
   b=bytearray(SW*SH*3);v=memoryview(b);got=0
   while got<len(b):
    n=proc.stdout.readinto(v[got:])
    if not n:break
    got+=n
   if got<len(b):raise RuntimeError(f"Decoder produced {got}/{len(b)} bytes for frame {i}")
   frame=np.frombuffer(b,np.uint8).reshape(SH,SW,3)
   pose=(180.+i*.3,-30.,100.)
   maps,tm=timeit(lambda:reproject_maps((SW,SH),(OW,OH),SHOT,pose))
   cub,tc=timeit(lambda:cv2.remap(frame,*maps,interpolation=cv2.INTER_CUBIC,borderMode=cv2.BORDER_WRAP))
   lin,tl=timeit(lambda:cv2.remap(frame,*maps,interpolation=cv2.INTER_LINEAR,borderMode=cv2.BORDER_WRAP))
   fixed,tconv=timeit(lambda:cv2.convertMaps(*maps,cv2.CV_16SC2))
   linfix,tf=timeit(lambda:cv2.remap(frame,*fixed,interpolation=cv2.INTER_LINEAR,borderMode=cv2.BORDER_WRAP))
   rows.append({"frame":i,"map_ms":round(tm,2),"cubic_ms":round(tc,2),"linear_ms":round(tl,2),
     "convert_ms":round(tconv,2),"fixed_ms":round(tf,2),
     "psnr_cubic_linear":round(float(cv2.PSNR(cub,lin)),3),
     "mae_cubic_linear":round(float(np.abs(cub.astype(np.int16)-lin.astype(np.int16)).mean()),4),
     "fixed_equal_linear":bool(np.array_equal(lin,linfix))})
   if i==3:
    # 1600x450 scaled side by side for download; do not use for full-resolution pixel QA.
    a=cv2.resize(cub,(800,450));z=cv2.resize(lin,(800,450))
    combined=np.hstack([a,z]);cv2.imwrite(str(OUT),combined,[int(cv2.IMWRITE_JPEG_QUALITY),88])
  proc.stdout.close();err=proc.stderr.read().decode(errors="replace");code=proc.wait(timeout=20)
  if code:raise RuntimeError(f"Decoder exit={code}: {err[-500:]}")
 finally:
  if proc.poll() is None:proc.kill();proc.wait()
 good=rows[1:];avg={k:round(float(np.mean([v[k] for v in good])),3) for k in ("map_ms","cubic_ms","linear_ms","convert_ms","fixed_ms","psnr_cubic_linear","mae_cubic_linear")}
 baseline=avg["map_ms"]+avg["cubic_ms"];simple=avg["map_ms"]+avg["linear_ms"];fixed=avg["map_ms"]+avg["convert_ms"]+avg["fixed_ms"]
 print("WARM_MEAN",json.dumps(avg),flush=True)
 print("COMPARISON",json.dumps({"baseline_ms":round(baseline,2),"simple_ms":round(simple,2),"fixed_ms":round(fixed,2),
  "simple_saving_pct":round(100*(1-simple/baseline),2),"fixed_saving_pct":round(100*(1-fixed/baseline),2),
  "all_fixed_equal":all(x["fixed_equal_linear"] for x in rows)}),flush=True)
 print("PER_FRAME",json.dumps(rows),flush=True)
 print("REVIEW_IMAGE",OUT,"bytes",OUT.stat().st_size)
 print("LIMITS: sample 6 frames at 1080p. Excludes FFmpeg decode/encode, concurrency, Metal and E2E. Review JPEG has cubic LEFT vs linear RIGHT.")
if __name__=="__main__":main()
