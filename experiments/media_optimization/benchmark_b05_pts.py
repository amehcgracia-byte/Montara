"""B05: measure frame timestamps, not just duration, across Montara proxy settings."""
import json
import subprocess
import tempfile
from pathlib import Path


def call(argv):
    result = subprocess.run(argv, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-1000:])
    return result.stdout


def frame_pts(path):
    output = call(["ffprobe", "-v", "error", "-select_streams", "v:0",
                   "-show_entries", "frame=best_effort_timestamp_time",
                   "-of", "json", str(path)])
    return [float(f["best_effort_timestamp_time"])
            for f in json.loads(output)["frames"] if "best_effort_timestamp_time" in f]


def measure(root, kind):
    source, proxy = root / f"{kind}.mp4", root / f"{kind}-proxy.mp4"
    input_args = ["ffmpeg", "-loglevel", "error", "-y"]
    if kind == "vfr":
        input_args += ["-f", "lavfi", "-i", "testsrc2=size=640x360:rate=15:duration=2",
                       "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=2",
                       "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                       "-map", "[v]", "-fps_mode", "vfr"]
    else:
        input_args += ["-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=4"]
        if kind == "shifted":
            input_args += ["-vf", "setpts=PTS+3/TB"]
    call(input_args + ["-c:v", "libx264", "-preset", "ultrafast", str(source)])
    call(["ffmpeg", "-v", "error", "-nostdin", "-y", "-copyts", "-start_at_zero",
          "-i", str(source), "-map", "0:v:0", "-map", "0:a:0?",
          "-vf", "scale=w='min(960,iw)':h=-2", "-fps_mode", "passthrough",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
          "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
          "-movflags", "+faststart", str(proxy)])
    original, result = frame_pts(source), frame_pts(proxy)
    assert len(original) == len(result) and original
    offset = original[0] - result[0]
    return dict(frames=len(original), source_first_pts=original[0],
                proxy_first_pts=result[0], origin_offset_s=round(offset, 6),
                max_absolute_pts_error_s=round(max(abs(a-b) for a,b in zip(original,result)), 6),
                max_error_after_origin_mapping_s=round(
                    max(abs(a-(b+offset)) for a,b in zip(original,result)), 6))


def benchmark(root):
    return {name: measure(root,name) for name in ("cfr", "vfr", "shifted")}


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="montara-b05-") as folder:
        print(json.dumps(benchmark(Path(folder)), indent=2))
