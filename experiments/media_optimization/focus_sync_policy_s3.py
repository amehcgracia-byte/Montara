#!/usr/bin/env python3
"""FOCUS S3: compare global argmax, overlap gate, and thirds-consensus guard.
Read-only mathematical stress test. Does not modify ZuckerVideos.
"""
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"engine"))
from core.stages.sync import SYNC_HOP_LENGTH, SYNC_SAMPLE_RATE, normalized_overlap_correlation, verify_sync_stability
DT=SYNC_HOP_LENGTH/SYNC_SAMPLE_RATE
T=np.arange(0,150,DT)
rng=np.random.default_rng(42)
M=rng.exponential(.15,len(T)).astype(np.float32)
for sec in np.arange(1,149,.73):
 i=int(sec/DT); M[i:i+3]+=np.array([2.,1.2,.4],dtype=np.float32)

def check(label,clip,actual):
 offsets,corr=normalized_overlap_correlation(M,clip)
 overlap=np.minimum(len(clip),len(M)-offsets)-np.maximum(0,-offsets)
 overlap=np.maximum(overlap,0)
 current=int(np.argmax(corr))
 threshold=max(1,int(round(.8*len(clip))))
 elig=np.where(overlap>=threshold)[0]
 gated=int(elig[np.argmax(corr[elig])]) if len(elig) else None
 def sec(idx):return float(offsets[idx]*DT) if idx is not None else None
 csec=sec(current)
 verification=verify_sync_stability(M,clip,csec)
 consensus=verification.get("consensus_offset_sec")
 gap=abs(csec-consensus) if consensus is not None else None
 guarded=(gap is not None and gap>.150)
 print(f"{label}: expected={actual:.3f}s; current={csec:.3f}s err={abs(csec-actual):.3f}s overlap={overlap[current]*DT:.2f}s/{len(clip)*DT:.2f}s")
 print(f"   80pct gate={sec(gated)}; thirds_consensus={consensus}; discrepancy={gap}; guard_flag={guarded}; thirds_checked={verification.get('checked')}")

for drift in (0,.05,.10,.25):
 ct=np.arange(0,80,DT)
 clip=np.interp(ct+12+drift*ct/80,T,M).astype(np.float32)
 check(f"DRIFT {int(drift*1000)}ms",clip,12.0)
# Valid genuine short clip, fully present within master.
ct=np.arange(0,12,DT)
clip=np.interp(ct+35,T,M).astype(np.float32)
check("LEGITIMATE SHORT 12s",clip,35)
# Legitimate partial overlap: 20s clip starts 8s before the master begins.
ct=np.arange(0,20,DT)
clip=np.interp(ct-8,T,M,left=0,right=0).astype(np.float32)
check("LEGITIMATE PARTIAL -8s",clip,-8)
print("NOTE: 80% gate is illustrative; short overlap can be legitimate. No production recommendation without real cases.")
