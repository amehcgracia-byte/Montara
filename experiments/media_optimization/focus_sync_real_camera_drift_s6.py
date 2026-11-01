#!/usr/bin/env python3
"""FOCUS S6: independent real-camera offsets across Sony timeline; no engine writes."""
import sys, subprocess, time, json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"engine"))
from core.stages.sync import SYNC_SAMPLE_RATE,SYNC_HOP_LENGTH,preprocess_sync_audio,normalize_envelope,normalized_overlap_correlation
IP=Path("/home/fer/lab-clips/originales/IMG_0044.MOV")
SO=Path("/home/fer/lab-clips/originales/C0188.MP4")
DT=SYNC_HOP_LENGTH/SYNC_SAMPLE_RATE
def extract(p,dur):
 cmd=["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-i",str(p),"-t",str(dur),"-map","0:a:0","-vn","-ac","1","-ar",str(SYNC_SAMPLE_RATE),"-f","f32le","pipe:1"]
 r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=120)
 return np.frombuffer(r.stdout,dtype="<f4").copy()
def onset(y):
 import librosa
 return normalize_envelope(librosa.onset.onset_strength(y=preprocess_sync_audio(y,SYNC_SAMPLE_RATE),sr=SYNC_SAMPLE_RATE,hop_length=SYNC_HOP_LENGTH))
def main():
 for p in (IP,SO):
  if not p.exists():raise SystemExit("missing "+str(p))
 t0=time.monotonic()
 master=onset(extract(IP,986.825))
 sony=extract(SO,89.76)
 rows=[]
 for start in (0,16,32,48,64):
  duration=25
  y=sony[round(start*SYNC_SAMPLE_RATE):round((start+duration)*SYNC_SAMPLE_RATE)]
  if len(y)<24*SYNC_SAMPLE_RATE:raise RuntimeError("short audio")
  offs, scores=normalized_overlap_correlation(master,onset(y))
  ix=int(np.argmax(scores))
  lag=float(offs[ix]*DT)
  global_offset=lag-start
  rows.append({"sony_window_start":start,"sony_window_end":start+duration,
   "estimated_iphone_time_of_sony_zero":round(global_offset,4),
   "correlation":round(float(scores[ix]),4)})
 print(json.dumps(rows,ensure_ascii=False,indent=2))
 values=np.array([r["estimated_iphone_time_of_sony_zero"] for r in rows])
 x=np.array([r["sony_window_start"]+12.5 for r in rows])
 slope=float(np.polyfit(x,values,1)[0])
 print("OFFSET_RANGE_MS",round(float(np.ptp(values))*1000,2))
 print("DRIFT_SLOPE_MS_PER_MIN",round(slope*60*1000,2))
 print("ELAPSED_SEC",round(time.monotonic()-t0,2))
 print("CAUTION: time resolution ~23.22 ms per onset frame; these windows overlap and are not statistically independent. Report variation as measured; do not claim sub-ms drift precision.")
if __name__=="__main__":main()
