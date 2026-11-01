#!/usr/bin/env python3
"""FOCUS S4: real Sony camera audio through actual onset frontend + offset/consistency.
Temporary audio is decoded into memory with ffmpeg; no media files, no engine edits.
"""
import json, os, subprocess, sys, time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"engine"))
from core.stages.sync import (
    SYNC_HOP_LENGTH, SYNC_SAMPLE_RATE, normalized_onset_envelope,
    recover_offset, verify_sync_stability
)
SOURCE=Path("/home/fer/lab-clips/originales/C0188.MP4")
DT=SYNC_HOP_LENGTH/SYNC_SAMPLE_RATE

def decode(start,duration):
    cmd=["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-ss",str(start),
         "-i",str(SOURCE),"-t",str(duration),"-map","0:a:0","-vn",
         "-ac","1","-ar",str(SYNC_SAMPLE_RATE),"-f","f32le","pipe:1"]
    r=subprocess.run(cmd,capture_output=True,timeout=90,check=True)
    return np.frombuffer(r.stdout,dtype="<f4").copy()

def onset_from_samples(samples):
    # Same library frontend (bandpass/compression + onset strength) as SyncStage;
    # load-independent: avoid writing a WAV solely for librosa.load.
    import librosa
    from core.stages.sync import preprocess_sync_audio,normalize_envelope
    y=preprocess_sync_audio(samples,SYNC_SAMPLE_RATE)
    return normalize_envelope(librosa.onset.onset_strength(y=y,sr=SYNC_SAMPLE_RATE,hop_length=SYNC_HOP_LENGTH))

def main():
    if not SOURCE.is_file():raise SystemExit("Missing camera")
    started=time.monotonic()
    # Sony real 89.76sec. Master is 76sec, camera clip = master sec 12..64 = 52sec.
    real=decode(0,76)
    if len(real)<70*SYNC_SAMPLE_RATE:raise RuntimeError("audio unexpectedly short")
    t=np.arange(len(real))/SYNC_SAMPLE_RATE
    print("Real audio decoded seconds:",round(len(real)/SYNC_SAMPLE_RATE,2),flush=True)
    master=onset_from_samples(real)
    clip_duration=52
    ct=np.arange(clip_duration*SYNC_SAMPLE_RATE)/SYNC_SAMPLE_RATE
    rows=[]
    for drift in (0,.05,.10,.25):
        # Deterministic resampling of real audio, not of an artificial onset envelope
        positions=12+ct+drift*ct/clip_duration
        clip_samples=np.interp(positions,t,real,left=0,right=0).astype(np.float32)
        clip_env=onset_from_samples(clip_samples)
        offset,confidence=recover_offset(master,clip_env)
        verify=verify_sync_stability(master,clip_env,offset)
        consensus=verify.get("consensus_offset_sec")
        gap=abs(offset-consensus) if consensus is not None else None
        row={"drift_ms":round(drift*1000),"expected_start_sec":12,
             "global_offset_sec":round(offset,4),"error_initial_ms":round((offset-12)*1000,1),
             "confidence":round(confidence,2),"thirds_checked":verify.get("checked"),
             "thirds_consensus_sec":round(consensus,4) if consensus is not None else None,
             "global_consensus_gap_ms":round(1000*gap,2) if gap is not None else None,
             "unstable_current":verify.get("unstable_sync"),
             "guardrail_candidate":bool(gap is not None and gap>.150)}
        rows.append(row)
        print(json.dumps(row,ensure_ascii=False),flush=True)
    print("Elapsed seconds",round(time.monotonic()-started,2))
    print("LIMITS: one Sony source, derived clips not independently recorded; no real camera-to-camera overlap or full SyncStage validation")
    print("No files written")

if __name__=="__main__":main()
