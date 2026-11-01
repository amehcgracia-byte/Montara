#!/usr/bin/env python3
"""FOCUS S8: five-second side-by-side REAL camera cross-check.
Only writes one lightweight MP4 plus a manifest in /home/fer; engine untouched.
"""
import json, subprocess
from pathlib import Path
IPHONE=Path("/home/fer/lab-clips/originales/IMG_0044.MOV")
SONY=Path("/home/fer/lab-clips/originales/C0188.MP4")
OUT=Path("/home/fer/montara-focus-sync-s8.mp4")
META=Path("/home/fer/montara-focus-sync-s8.json")
OFFSET=703.7039
SONY_START=40.0
DURATION=5.0

def main():
    for p in (IPHONE,SONY):
        if not p.is_file():raise SystemExit("Missing original "+str(p))
    if OUT.exists() or META.exists():raise SystemExit("S8 outputs already exist; refusing overwrite")
    # Seek both sources on their own time axis; FFmpeg auto-applies display rotation.
    cmd=["ffmpeg","-nostdin","-hide_banner","-loglevel","error",
         "-ss",f"{OFFSET+SONY_START:.4f}","-i",str(IPHONE),
         "-ss",str(SONY_START),"-i",str(SONY),
         "-filter_complex",
         "[0:v]setpts=PTS-STARTPTS,fps=25,scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2,setsar=1[left];"
         "[1:v]setpts=PTS-STARTPTS,fps=25,scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2,setsar=1[right];"
         "[left][right]hstack=inputs=2,format=yuv420p[v];"
         "[1:a]asetpts=PTS-STARTPTS,aresample=48000[a]",
         "-map","[v]","-map","[a]","-t",str(DURATION),
         "-c:v","libx264","-preset","veryfast","-crf","27",
         "-c:a","aac","-b:a","96k","-movflags","+faststart","-y",str(OUT)]
    print("Creating 5s low-res AV comparison. Left=iPhone, right=Sony; sound=Sony.",flush=True)
    subprocess.run(cmd,check=True,timeout=150)
    if not OUT.is_file() or OUT.stat().st_size==0:raise RuntimeError("empty output")
    META.write_text(json.dumps({
      "left":"iPhone IMG_0044.MOV","right":"Sony C0188.MP4",
      "audio_source":"Sony only, for simple audition",
      "iphone_start_sec":OFFSET+SONY_START,"sony_start_sec":SONY_START,
      "duration_sec":DURATION,"estimated_audio_offset_sec":OFFSET,
      "limitations":"Inspection checks gross visual simultaneity; cannot establish frame-accurate AV/lip synchronization. Sony audio only."
    },indent=2)+"\n")
    print("VIDEO",OUT,"BYTES",OUT.stat().st_size)
    print("MANIFEST",META)
    print("INSPECTION: left/right gestures and visible drum strikes; no claim of frame accuracy.")
if __name__=="__main__":main()
