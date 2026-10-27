"""B06: measure proxy video/audio timestamp mapping with synthetic synced events.

Uses the exact FFmpeg proxy options in local_media.proxies.prepare().
Runs without Zucker, network, GPU, or large footage.
"""
import json
import subprocess
import tempfile
from pathlib import Path


def call(args):
    p=subprocess.run(args, text=True, capture_output=True)
    if p.returncode: raise RuntimeError(p.stderr[-1600:])
    return p.stdout


def first_pts(path, kind):
    selector="v:0" if kind=="video" else "a:0"
    entries="frame=best_effort_timestamp_time"
    d=json.loads(call(["ffprobe","-v","error","-select_streams",selector,
                      "-show_entries",entries,"-of","json",str(path)]))
    times=[float(f["best_effort_timestamp_time"]) for f in d["frames"]
           if "best_effort_timestamp_time" in f]
    if not times: raise AssertionError(f"No {kind} frames")
    return times


def run(work):
    source=work/"source.mp4"
    proxy=work/"proxy.mp4"
    # Synchronized 30 fps camera video and PCM-derived 48 kHz audio, 4 seconds.
    call(["ffmpeg","-v","error","-y","-f","lavfi","-i",
          "testsrc2=size=640x360:rate=30:duration=4",
          "-f","lavfi","-i","sine=frequency=440:sample_rate=48000:duration=4",
          "-c:v","libx264","-preset","ultrafast","-c:a","aac",str(source)])
    call(["ffmpeg","-v","error","-nostdin","-y","-copyts","-start_at_zero",
          "-i",str(source),"-map","0:v:0","-map","0:a:0?",
          "-vf","scale=w='min(960,iw)':h=-2","-fps_mode","passthrough",
          "-c:v","libx264","-preset","veryfast","-crf","28",
          "-pix_fmt","yuv420p","-c:a","aac","-b:a","96k",
          "-movflags","+faststart",str(proxy)])
    result={}
    for kind in ("video","audio"):
        a,b=first_pts(source,kind),first_pts(proxy,kind)
        result[kind]={
            "original_first_s":a[0],"proxy_first_s":b[0],
            "original_last_s":a[-1],"proxy_last_s":b[-1],
            "first_offset_ms":round(1000*(b[0]-a[0]),3),
            "last_offset_ms":round(1000*(b[-1]-a[-1]),3),
            "offset_drift_ms":round(1000*((b[-1]-a[-1])-(b[0]-a[0])),3)}
    return result


if __name__=="__main__":
    with tempfile.TemporaryDirectory(prefix="montara-b06-") as temp:
        print(json.dumps(run(Path(temp)),indent=2))
