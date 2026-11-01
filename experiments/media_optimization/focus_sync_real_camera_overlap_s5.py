#!/usr/bin/env python3
"""FOCUS S5: real Sony vs iPhone audio overlap discovery using ZuckerVideos sync functions.
No engine edits, no saved audio, no media video decode, no cache changes.
"""
import json, subprocess, sys, time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"engine"))
from core.stages.sync import (
 SYNC_SAMPLE_RATE,SYNC_HOP_LENGTH,preprocess_sync_audio,normalize_envelope,
 recover_offset,normalized_overlap_correlation,verify_sync_stability
)
IPHONE=Path("/home/fer/lab-clips/originales/IMG_0044.MOV")
SONY=Path("/home/fer/lab-clips/originales/C0188.MP4")
DT=SYNC_HOP_LENGTH/SYNC_SAMPLE_RATE

def audio(path,start,duration):
 cmd=["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-ss",str(start),
      "-i",str(path),"-t",str(duration),"-map","0:a:0","-vn",
      "-ac","1","-ar",str(SYNC_SAMPLE_RATE),"-f","f32le","pipe:1"]
 r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120,check=True)
 return np.frombuffer(r.stdout,dtype="<f4").copy()

def onset(samples):
 import librosa
 samples=preprocess_sync_audio(samples,SYNC_SAMPLE_RATE)
 return normalize_envelope(librosa.onset.onset_strength(y=samples,sr=SYNC_SAMPLE_RATE,hop_length=SYNC_HOP_LENGTH))

def summarize(master,clip,label,clip_start):
 offsets,scores=normalized_overlap_correlation(master,clip)
 if not len(scores):raise RuntimeError("empty correlation")
 best=int(np.argmax(scores))
 lag=int(offsets[best])
 inferred=lag*DT-clip_start
 overlap_frames=max(0,min(len(clip),len(master)-lag)-max(0,-lag))
 result={"segment":label,"sony_segment_start_sec":clip_start,
 "candidate_iphone_sec_for_sony_zero":round(inferred,3),
 "peak_correlation":round(float(scores[best]),4),
 "overlap_sec":round(overlap_frames*DT,2),
 "clip_duration_sec":round(len(clip)*DT,2)}
 if overlap_frames>=int(12/DT):
  v=verify_sync_stability(master,clip,lag*DT)
  result["verification"]={"checked":v.get("checked"),
   "unstable_sync":v.get("unstable_sync"),"consensus_count":v.get("consensus_count"),
   "consensus_offset_sec":v.get("consensus_offset_sec")}
 return result

def main():
 for p in (IPHONE,SONY):
  if not p.is_file():raise SystemExit(f"Missing: {p}")
 begun=time.monotonic()
 print("Decoding camera audio only, not video ...",flush=True)
 master=onset(audio(IPHONE,0,986.825))
 sony=audio(SONY,0,89.76)
 segments=[("first_45s",0,45),("last_45s",44,45)]
 rows=[]
 for label,start,duration in segments:
  a=int(start*SYNC_SAMPLE_RATE);b=int((start+duration)*SYNC_SAMPLE_RATE)
  clip=onset(sony[a:b])
  row=summarize(master,clip,label,start)
  print(json.dumps(row,ensure_ascii=False),flush=True)
  rows.append(row)
 gap=abs(rows[0]["candidate_iphone_sec_for_sony_zero"]-rows[1]["candidate_iphone_sec_for_sony_zero"])
 print("INDEPENDENT_CANDIDATE_GAP_SEC",round(gap,3))
 print("INTERPRETATION: same-event hypothesis needs close independent offsets plus high-confidence/visual or manual confirmation; no verified match solely by this test.")
 print("ELAPSED_SEC",round(time.monotonic()-begun,3),"NO_FILES_WRITTEN")

if __name__=="__main__":main()
