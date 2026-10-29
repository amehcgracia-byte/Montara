"""Replay SAT-07's first FFmpeg command; no import or modification of Zucker.

Three repetitions per arm, with exact decoded pixels AND frame timestamps.
Historical command provenance is stored separately in first_command.json.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]


def run(args):
    p = subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=300)
    if p.returncode:
        raise RuntimeError(f"FFmpeg command failed ({p.returncode}): {p.stderr[-4000:]}")
    return p


def probe(path, frames=False):
    args = ["ffprobe", "-v", "error", "-select_streams", "v:0"]
    if frames:
        args += ["-show_frames", "-show_entries",
                 "frame=pts,best_effort_timestamp_time,pkt_duration_time,pict_type,key_frame"]
    else:
        args += ["-show_streams", "-show_format"]
    return json.loads(run(args + ["-of", "json", path]).stdout)


def hashes(path):
    data = run(["ffmpeg", "-v", "error", "-i", path, "-map", "0:v:0",
                "-an", "-c:v", "rawvideo", "-threads:v", "1", "-pix_fmt", "yuv420p",
                "-fps_mode", "passthrough", "-f", "framehash", "-hash", "sha256", "-"]).stdout
    return parse_hashes(data)


def parse_hashes(data):
    return [line.split(",")[-1].strip() for line in data.splitlines()
            if line.strip() and not line.startswith("#")]


def compare(left, right):
    a, b = left["frame_hashes"], right["frame_hashes"]
    differing = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    return {"frames_a": len(a), "frames_b": len(b), "different": differing,
            "exact": sum(x == y for x, y in zip(a, b)),
            "pixels_equal": len(a) == len(b) == 60 and not differing,
            "timestamps_equal": left.get("timestamps") == right.get("timestamps")}


def build_command(base, source, destination, arm):
    cmd = list(base)
    cmd[0] = "ffmpeg"
    cmd[cmd.index("-i") + 1] = str(source)
    cmd[-1] = str(destination)
    if arm == "encoder_one":
        cmd[-1:-1] = ["-threads:v", "1"]  # OUTPUT scope: encoder, not decoder/filter.
    elif arm == "without_vbv":
        for option in ("-maxrate", "-bufsize"):
            i = cmd.index(option)
            del cmd[i:i + 2]
    elif arm == "filtered_framehash":
        # Keep EXACT input and filtergraph; replace lossy encoding and MP4 sink.
        cmd = cmd[:cmd.index("-pix_fmt")] + [
            "-an", "-r", "30.000", "-fps_mode", "cfr", "-frames:v", "60",
            "-c:v", "rawvideo", "-threads:v", "1", "-pix_fmt", "yuv420p",
            "-f", "framehash", "-hash", "sha256", str(destination)]
    elif arm != "original":
        raise ValueError(arm)
    return cmd


def main():
    spec = json.loads(Path(__file__).with_name("first_command.json").read_text())
    source = ROOT / "tests/fixtures/much-to-me/cam-fixed.mp4"
    out = Path(os.environ.get("SATURNO_REPLAY_OUT", "/tmp/saturno08-replay"))
    out.mkdir(parents=True, exist_ok=True)
    result = {"status": "RUNNING", "scope": "SAT-07 first-command replay, not full Zucker",
              "provenance": spec["provenance"], "repetitions": 3,
              "ffmpeg_version": run(["ffmpeg", "-version"]).stdout,
              "cpu_count": os.cpu_count(), "platform": platform.platform(), "arms": {}}
    try:
        source_bytes = source.read_bytes()
        result["source"] = {"bytes": len(source_bytes),
                            "sha256": hashlib.sha256(source_bytes).hexdigest(),
                            "git_blob_sha": hashlib.sha1(b"blob " + str(len(source_bytes)).encode()
                                                        + b"\0" + source_bytes).hexdigest(),
                            "probe": probe(source),
                            "frames": probe(source, frames=True)["frames"]}
        assert result["source"]["git_blob_sha"] == spec["source_blob_sha"], "Source fixture changed"
        for arm in ("original", "encoder_one", "without_vbv", "filtered_framehash"):
            records = []
            for repeat in range(3):
                destination = out / f"{arm}-{repeat}.{'txt' if arm == 'filtered_framehash' else 'mp4'}"
                cmd = build_command(spec["command"], source, destination, arm)
                started = time.perf_counter()
                run(cmd)
                entry = {"command": cmd, "elapsed_sec": time.perf_counter() - started,
                         "bytes": destination.stat().st_size,
                         "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}
                if arm == "filtered_framehash":
                    raw = destination.read_text()
                    entry["frame_hashes"] = parse_hashes(raw)
                    entry["timestamps"] = [line.rsplit(",", 1)[0] for line in raw.splitlines()
                                           if line.strip() and not line.startswith("#")]
                else:
                    entry["frame_hashes"] = hashes(destination)
                    entry["timestamps"] = [f.get("pts") for f in probe(destination, True)["frames"]]
                records.append(entry)
            pairs = [compare(records[0], records[i]) for i in (1, 2)]
            result["arms"][arm] = {"runs": records, "comparisons_to_first": pairs,
                                    "stable": all(p["pixels_equal"] and p["timestamps_equal"] for p in pairs)}
            print(json.dumps({"arm": arm, "comparisons": pairs}), flush=True)
        result["status"] = "DIAGNOSTIC_COMPLETE"
        # Successful collection is separate from architecture/identity gates.
        result["native_encoder_one_candidate"] = result["arms"]["encoder_one"]["stable"]
        result["architecture_approved"] = False
    except Exception as exc:
        result.update(status="INFRASTRUCTURE_OR_DIAGNOSTIC_ERROR", error=repr(exc))
    finally:
        target = out / "REPORT.json"
        target.write_text(json.dumps(result, indent=2))
        print("SATURNO08_REPORT_BEGIN", flush=True)
        print(json.dumps(result), flush=True)
        print("SATURNO08_REPORT_END", flush=True)
    return 0 if result["status"] == "DIAGNOSTIC_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
