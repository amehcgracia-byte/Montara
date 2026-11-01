#!/usr/bin/env python3
"""FOCUS S7 — real camera visual cross-check at measured audio offset.

Creates one JPEG contact sheet and a JSON manifest outside the repo.
Does not modify engine, camera originals or synchronization artifacts.
"""
import json, subprocess, tempfile
from pathlib import Path

IPHONE=Path("/home/fer/lab-clips/originales/IMG_0044.MOV")
SONY=Path("/home/fer/lab-clips/originales/C0188.MP4")
OUTPUT=Path("/home/fer/montara-jupiter-focus-sync-s7.jpg")
MANIFEST=Path("/home/fer/montara-jupiter-focus-sync-s7.json")
OFFSET=703.7039
SONY_SECONDS=(10.,45.,80.)

def run(args):
    subprocess.run(args, check=True, timeout=100, stdout=subprocess.DEVNULL)

def extract(src,sec,target):
    run(["ffmpeg","-nostdin","-hide_banner","-loglevel","error",
         "-ss",f"{sec:.4f}","-i",str(src),"-map","0:v:0",
         "-frames:v","1","-vf","scale=640:360:force_original_aspect_ratio=decrease,"
         "pad=640:360:(ow-iw)/2:(oh-ih)/2:black,setsar=1",
         "-q:v","3","-y",str(target)])
    if not target.exists() or target.stat().st_size<1000:
        raise RuntimeError(f"No frame extracted from {src} at {sec}s")

def main():
    if OUTPUT.exists() or MANIFEST.exists():
        raise SystemExit("S7 output already exists: refusing overwrite")
    for f in [IPHONE,SONY]:
        if not f.is_file(): raise SystemExit(f"Missing input {f}")
    with tempfile.TemporaryDirectory(prefix="montara-fer-s7-") as d:
        d=Path(d)
        inputs=[]
        timestamps=[]
        for i,t in enumerate(SONY_SECONDS):
            ip=OFFSET+t
            sony_file=d/f"s{i}.jpg";iphone_file=d/f"i{i}.jpg"
            extract(SONY,t,sony_file);extract(IPHONE,ip,iphone_file)
            # Stack each column from one event-time, iPhone row first, Sony second.
            inputs += [str(iphone_file),str(sony_file)]
            timestamps.append({"sony_sec":t,"iphone_sec":round(ip,4)})
        cmd=["ffmpeg","-nostdin","-hide_banner","-loglevel","error"]
        for src in inputs: cmd+=["-i",src]
        # Top = iphone across timeline; bottom = sony at same approximate moments.
        layout="0_0|w0_0|w0+w1_0|0_h0|w0_h0|w0+w1_h0"
        # inputs order is iphone0 sony0 iphone1 sony1 iphone2 sony2
        # xstack reordering: [0][2][4][1][3][5]
        filt="[0:v][2:v][4:v][1:v][3:v][5:v]xstack=inputs=6:layout="+layout+"[v]"
        cmd+=["-filter_complex",filt,"-map","[v]","-frames:v","1",
              "-q:v","3","-y",str(OUTPUT)]
        run(cmd)
    MANIFEST.write_text(json.dumps({
      "summary":"Top row iPhone; bottom row Sony; columns Sony t=10,45,80s",
      "audio_offset_iphone_minus_sony_sec":OFFSET,
      "pairs":timestamps,
      "caveat":"Audio alignment is strong; visual comparison checks same action, not frame-accurate lip-sync."
    },indent=2)+"\n",encoding="utf-8")
    print("CONTACT_SHEET",OUTPUT,"BYTES",OUTPUT.stat().st_size)
    print("MANIFEST",MANIFEST)
    print("LAYOUT: iPhone TOP row; Sony BOTTOM row; columns Sony 10s / 45s / 80s")
    print("MANUAL REVIEW REQUIRED: compare performer gesture/events at matching timestamps")

if __name__=="__main__":main()
