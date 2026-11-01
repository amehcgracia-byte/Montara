#!/usr/bin/env python3
"""FOCUS S2: inspect correlation peak overlaps; no engine changes or media I/O."""
import sys, json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"engine"))
from core.stages.sync import SYNC_HOP_LENGTH, SYNC_SAMPLE_RATE, normalized_overlap_correlation

DT=SYNC_HOP_LENGTH/SYNC_SAMPLE_RATE
T=np.arange(0,150,DT)
rng=np.random.default_rng(42)
MASTER=rng.exponential(.15,len(T)).astype(np.float32)
for sec in np.arange(1,149,.73):
    i=int(sec/DT)
    MASTER[i:i+3]+=np.array([2.,1.2,.4],dtype=np.float32)
CT=np.arange(0,80,DT)

def main():
    rows=[]
    for drift in (0.,.05,.10,.25):
        clip=np.interp(CT+12+drift*CT/80,T,MASTER).astype(np.float32)
        offsets, scores=normalized_overlap_correlation(MASTER,clip)
        # Distinct candidate maxima, separated by >=1 sec
        order=np.argsort(scores)[::-1]
        selected=[]
        for idx in order:
            lag=int(offsets[idx]); seconds=lag*DT
            if any(abs(seconds-c["offset_sec"])<1 for c in selected):
                continue
            clip_start=max(0,-lag)
            clip_end=min(len(clip),len(MASTER)-lag)
            overlap=max(0,clip_end-clip_start)*DT
            selected.append({"offset_sec":round(seconds,4),"correlation":round(float(scores[idx]),5),
                             "overlap_sec":round(overlap,3),
                             "overlap_fraction_clip":round(overlap/(len(clip)*DT),4)})
            if len(selected)>=8:break
        near=np.where(np.abs(offsets*DT-12)<.5)[0]
        ideal_idx=near[np.argmax(scores[near])] if len(near) else None
        row={"drift_ms":int(drift*1000),"top_candidates":selected,
             "best_near_expected":(None if ideal_idx is None else {
                 "offset_sec":round(float(offsets[ideal_idx]*DT),4),
                 "correlation":round(float(scores[ideal_idx]),5)}),
             "hypothesis":"High-scoring partial overlap candidate can dominate global alignment"}
        rows.append(row)
        print(json.dumps(row,ensure_ascii=False,indent=2),flush=True)
    print("=== No files written; no production code changed ===")

if __name__=="__main__":
    main()
