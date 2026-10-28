"""B07: minimal original-backed export smoke test for a cached proxy recipe.

Independent of the browser and Zucker Editor; tests the actual original-path
resolution contract of local_media.proxies.resolve_recipe.
"""
import json
import subprocess
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from local_media.proxies import prepare, resolve_recipe


def run(args):
    p=subprocess.run(args,capture_output=True,text=True)
    if p.returncode: raise RuntimeError(p.stderr[-1500:])
    return p.stdout


def benchmark(root):
    source=root/"original.mp4"
    cache=root/"cache"
    target=root/"edited.mp4"
    run(["ffmpeg","-v","error","-y","-f","lavfi","-i",
         "testsrc2=size=640x360:rate=24:duration=4",
         "-c:v","libx264","-preset","ultrafast",str(source)])
    prepared=prepare(source,cache)
    recipe={"clips":[{"source_id":prepared["source_id"],"start":0.5,"end":1.5},
                     {"source_id":prepared["source_id"],"start":2,"end":3}]}
    clips=resolve_recipe(recipe,cache)
    assert all(c["original"]==str(source.resolve()) for c in clips)
    # Two one-second segments must be rendered from the untouched ORIGINAL.
    run(["ffmpeg","-v","error","-y","-i",clips[0]["original"],
         "-filter_complex",
         "[0:v]trim=start=0.5:end=1.5,setpts=PTS-STARTPTS[v0];"
         "[0:v]trim=start=2:end=3,setpts=PTS-STARTPTS[v1];"
         "[v0][v1]concat=n=2:v=1:a=0[out]",
         "-map","[out]","-c:v","libx264","-preset","ultrafast",str(target)])
    duration=float(run(["ffprobe","-v","error","-show_entries","format=duration",
                        "-of","default=noprint_wrappers=1:nokey=1",str(target)]))
    assert abs(duration-2) <= (1/24 + .001)
    return {"original_used":True,"nominal_duration_s":2,"actual_duration_s":duration,
            "duration_error_frames":round(abs(duration-2)*24,3),
            "export_bytes":target.stat().st_size,
            "scope":"isolated recipe/export smoke; not web editor end-to-end"}


if __name__=="__main__":
    with tempfile.TemporaryDirectory(prefix="montara-b07-") as d:
        print(json.dumps(benchmark(Path(d)),indent=2))
