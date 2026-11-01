#!/usr/bin/env python3
"""F4 real 360 Lanczos vs linear. Isolated, controlled; no engine edits."""
import argparse,json,os,subprocess,time
from pathlib import Path
from focus_ac_vm_cpu_guard import sample_cpu,processes
SOURCE=Path("/home/fer/lab-clips/originales/VID_20260824_204524_00_004.mp4")
def run(cmd,timeout):
 t=time.monotonic()
 r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=timeout)
 if r.returncode:raise RuntimeError(f"Command failed ({r.returncode}): {r.stderr[-1800:]}")
 return round(time.monotonic()-t,3),r
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--output",type=Path,required=True)
 p.add_argument("--approved-by-chema",action="store_true")
 a=p.parse_args()
 if not a.approved_by_chema:p.error("Explicit shared VM permission required")
 if a.output.exists():p.error("Output already exists, refuse overwrite")
 cpu=sample_cpu(2);load=os.getloadavg()[0];busy=processes()
 if cpu is None or cpu>=65 or load >= (os.cpu_count() or 1)*.75 or busy:
  p.error(f"Busy CPU={cpu}, load={load}, FFmpeg={busy}")
 if not SOURCE.is_file():p.error("360 original unavailable")
 a.output.mkdir(parents=True)
 params={"source":SOURCE.name,"start_sec":10,"duration_sec":5,
         "geometry":"yaw35 pitch12 h_fov100 v_fov62 1920x1080",
         "codec":"libx264 CRF23 preset veryfast threads2","repeats":2,
         "run_order":["lanczos","linear","linear","lanczos"]}
 report={"status":"INCOMPLETE","settings":params,"preflight_cpu_percent":cpu,"runs":[]}
 try:
  for idx,interp in enumerate(params["run_order"],1):
   output=a.output/f"real360_{idx}_{interp}.mp4"
   filt=f"v360=input=equirect:output=flat:yaw=35:pitch=12:h_fov=100:v_fov=62:w=1920:h=1080:interp={interp},format=yuv420p"
   cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-threads","2",
        "-ss","10","-i",str(SOURCE),"-t","5","-vf",filt,
        "-an","-c:v","libx264","-preset","veryfast","-crf","23","-threads","2","-y",str(output)]
   elapsed,_=run(cmd,150)
   report["runs"].append({"order":idx,"interp":interp,"wall_sec":elapsed,"bytes":output.stat().st_size,"file":output.name})
  # compare first pair, same decoded pixels frame-by-frame; video quality relative to Lanczos only
  ssimcmd=["ffmpeg","-hide_banner","-nostdin","-i",str(a.output/"real360_1_lanczos.mp4"),
           "-i",str(a.output/"real360_2_linear.mp4"),"-lavfi","ssim","-f","null","-"]
  secs,s=run(ssimcmd,75)
  line=next((z.strip() for z in reversed(s.stderr.splitlines()) if "SSIM" in z and "All:" in z),"")
  report["ssim_vs_lanczos"]=line
  report["ssim_wall_sec"]=secs
  byname={k:[v["wall_sec"] for v in report["runs"] if v["interp"]==k] for k in ("lanczos","linear")}
  report["seconds_by_interp"]=byname
  import statistics
  baseline=statistics.median(byname["lanczos"]);fast=statistics.median(byname["linear"])
  report["relative_time_saving_percent"]=round(100*(baseline-fast)/baseline,2)
  report["status"]="PASS_F4_REAL_PAIR_MEASURED" if line else "REVIEW_MISSING_SSIM"
 except Exception as e:
  report["status"]="FAIL";report["error"]=repr(e);raise
 finally:
  (a.output/"report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
  print(json.dumps(report,indent=2,ensure_ascii=False))
if __name__=="__main__":main()
