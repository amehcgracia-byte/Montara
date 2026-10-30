#!/usr/bin/env python3
"""FOCUS A/C offline edit-plan invariants: zero FFmpeg / no source media reads.

Compare an original-authored reference plan to a proxy-authored candidate.
This is a semantic comparison, not a proof that the editor will choose the
same cuts. Divergences fail closed, with bounded diagnostics.
"""
import argparse
import json
import math
from pathlib import Path

FIELDS = (
    "camera_id", "master_start_sec", "clip_start_sec", "duration_sec",
    "clip_offset_sec", "projection", "spherical_shot", "motion",
    "flat_framing", "title", "editorial_subject"
)
NUMERIC = {"master_start_sec", "clip_start_sec", "duration_sec", "clip_offset_sec"}

def check(reference, candidate, tolerance=0.001):
    a=reference.get("segments", [])
    b=candidate.get("segments", [])
    errors=[]
    if len(a)!=len(b):
        errors.append(f"segment counts differ: original={len(a)} proxy={len(b)}")
    for i,(x,y) in enumerate(zip(a,b),1):
        for key in FIELDS:
            if key not in x and key not in y:continue
            if key not in x or key not in y:
                errors.append(f"segment {i}: field {key} missing on one side")
                continue
            v,w=x[key],y[key]
            if key in NUMERIC and isinstance(v,(int,float)) and isinstance(w,(int,float)):
                same=math.isfinite(v) and math.isfinite(w) and abs(v-w)<=tolerance
            else:
                same=v==w
            if not same:
                errors.append(f"segment {i}: {key} differs ({str(v)[:140]} vs {str(w)[:140]})")
        for key in ("source_path","clip_path"):
            if not y.get(key):errors.append(f"segment {i}: candidate {key} missing")
    return errors

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reference",type=Path,required=True)
    p.add_argument("--candidate",type=Path,required=True)
    p.add_argument("--tolerance",type=float,default=0.001)
    args=p.parse_args()
    if args.tolerance<0:p.error("negative tolerance")
    ref=json.loads(args.reference.read_text())
    cand=json.loads(args.candidate.read_text())
    errors=check(ref,cand,args.tolerance)
    print(json.dumps({"status":"PASS" if not errors else "FAIL",
      "reference_segments":len(ref.get("segments",[])),
      "candidate_segments":len(cand.get("segments",[])),
      "errors_total":len(errors),"first_errors":errors[:20],
      "limitations":"Metadata/timeline invariants only; not rendering, media identity, or audio sync."},
      ensure_ascii=False,indent=2))
    if errors:raise SystemExit(1)
if __name__=="__main__":main()
