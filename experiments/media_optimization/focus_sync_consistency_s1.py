#!/usr/bin/env python3
"""FOCUS S1 — deterministic sync-offset and drift stress test; no video / engine writes."""
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine"))
from core.stages.sync import SYNC_HOP_LENGTH, SYNC_SAMPLE_RATE, recover_offset, verify_sync_stability

DT = SYNC_HOP_LENGTH / SYNC_SAMPLE_RATE
MASTER_SECONDS = 150.0
CLIP_SECONDS = 80.0
KNOWN_OFFSET = 12.0
OUT = Path("/home/fer/montara-jupiter-focus-sync-s1.json")

def signal():
    rng = np.random.default_rng(42)
    t = np.arange(0, MASTER_SECONDS, DT)
    master = rng.exponential(0.15, len(t)).astype(np.float32)
    for sec in np.arange(1, 149, .73):
        i = int(sec/DT)
        master[i:i+3] += np.array([2.,1.2,.4], dtype=np.float32)
    return t, master

def main():
    if OUT.exists():
        raise SystemExit(f"Report exists; refusing overwrite: {OUT}")
    t, master = signal()
    ct = np.arange(0, CLIP_SECONDS, DT)
    rows = []
    for drift in (0., .05, .10, .25):
        positions = ct + KNOWN_OFFSET + drift * ct / CLIP_SECONDS
        clip = np.interp(positions, t, master).astype(np.float32)
        tick=time.perf_counter()
        offset, confidence = recover_offset(master, clip)
        verification=verify_sync_stability(master, clip, offset)
        consensus=verification.get("consensus_offset_sec")
        gap=abs(offset-consensus) if consensus is not None else None
        rows.append({
            "drift_ms_over_80s": round(drift*1000),
            "known_initial_offset_sec": KNOWN_OFFSET,
            "global_offset_sec": round(offset, 6),
            "global_confidence": round(confidence, 3),
            "initial_offset_error_ms": round((offset-KNOWN_OFFSET)*1000, 2),
            "consensus_sec": round(consensus, 6) if consensus is not None else None,
            "global_consensus_gap_ms": round(gap*1000, 2) if gap is not None else None,
            "unstable_sync": verification.get("unstable_sync"),
            "consensus_count": verification.get("consensus_count"),
            "verification_delta_ms": round(1000*verification.get("delta_sec",0),2),
            "thirds": verification.get("segments"),
            "elapsed_sec": round(time.perf_counter()-tick,3),
            "guardrail_candidate_reject_if_gap_over_150ms": bool(gap is not None and gap > .150)
        })
        print(json.dumps(rows[-1],ensure_ascii=False),flush=True)
    report={"description":"synthetic onset-envelope stress test, not SyncStage end to end",
            "sample_hop_seconds":DT,"seed":42,"results":rows,
            "caveats":["No audio decoding, librosa onset extraction or real clips", "A match between thirds is not sufficient evidence of alignment with global offset",
                       "Guardrail candidate is analysis only, not a production rule or verified threshold"]}
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("REPORT:",OUT)

if __name__=="__main__":
    main()
