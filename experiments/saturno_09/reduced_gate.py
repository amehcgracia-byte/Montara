"""Real Zucker partial-package gate, isolated Linux mount namespace for B.

Reuses the SAT-08 harness. Never edits engine/mixer. Requires sudo/unshare/mount
on a disposable CI VM; namespace failure is an infrastructure failure, not PASS.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ.get("SATURNO09_OUT", "/tmp/saturno09"))


def call(args, timeout=600, binary=False):
    p = subprocess.run(list(map(str, args)), capture_output=True,
                       text=not binary, timeout=timeout)
    if p.returncode:
        tail = p.stderr[-6000:]
        raise RuntimeError(f"returncode={p.returncode}: {tail!r}")
    return p.stdout


def digest(data):
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def media_digest(path):
    return digest(Path(path).read_bytes())


def decoded(path, kind, start=0, duration=2):
    fmt = (["-map", "0:v:0", "-an", "-pix_fmt", "yuv420p", "-f", "rawvideo"]
           if kind == "video" else
           ["-map", "0:a:0", "-vn", "-c:a", "pcm_f32le", "-f", "f32le"])
    raw = call(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(start),
                "-i", path, "-t", str(duration), *fmt, "-"], binary=True)
    return digest(raw)


def timeline(path):
    return json.loads(call(["ffprobe", "-v", "error", "-show_streams", "-show_packets",
                           "-show_entries", "stream=index,codec_type,time_base,start_time,duration,nb_frames,sample_rate,channels:packet=stream_index,pts,dts,duration",
                           "-of", "json", path]))


def worker(specfile):
    spec = json.loads(Path(specfile).read_text())
    isolation = {"requested": bool(spec.get("mask")), "masked": []}
    for folder in spec.get("mask", []):
        # Only this child mount namespace sees the empty substitute directories.
        call(["mount", "-t", "tmpfs", "-o", "size=1m,mode=0755", "tmpfs", folder])
        assert not list(Path(folder).iterdir()), f"Mask failed: {folder}"
        isolation["masked"].append(folder)
    isolation["original_paths_absent"] = {p: not Path(p).exists() for p in spec.get("originals", [])}
    if spec.get("mask"):
        assert all(isolation["original_paths_absent"].values()), "Original still accessible"
    os.environ["ZUCKER_DATA_ROOT"] = spec["runtime"]
    os.environ["SATURNO_QA_ENCODER_THREADS_ONE"] = "1"
    os.environ["SATURNO_QA_FILTER_THREADS_ONE"] = "0"
    os.environ["SATURNO_QA_NO_FADES"] = "0"
    sys.path.insert(0, str(ROOT / "experiments/saturno_05"))
    import native_ab as native
    from core.normalization import global_cache_root
    cache = global_cache_root()
    cache_initial = list(cache.rglob("*")) if cache.exists() else []
    assert not cache_initial, f"Cache was not empty: {cache}"
    traces = native.install_trace()
    target = Path(spec["folder"])
    target.mkdir(parents=True, exist_ok=True)
    result = native.measure_render(target, Path(spec["video"]), Path(spec["audio"]), spec["start"], "render")
    result.update(frame_hashes=native.decoded_frame_digests(result["file"]),
                  audio=output_audio(result["file"]),
                  timeline=timeline(result["file"]), isolation=isolation,
                  cache_root=str(cache), cache_initial_entries=len(cache_initial), traces=traces)
    (target / "result.json").write_text(json.dumps(result, indent=2))


def output_audio(path):
    return digest(call(["ffmpeg", "-nostdin", "-v", "error", "-i", path,
                        "-map", "0:a:0", "-vn", "-c:a", "pcm_f32le", "-f", "f32le", "-"], binary=True))


def compare(a, b):
    x, y = a["frame_hashes"], b["frame_hashes"]
    different = [i for i, pair in enumerate(zip(x, y)) if pair[0] != pair[1]]
    return {"a_frames": len(x), "b_frames": len(y), "exact": sum(i == j for i, j in zip(x, y)),
            "different_indices": different, "video_exact": len(x) == len(y) == 60 and not different,
            "audio_pcm_exact": a["audio"] == b["audio"] and a["audio"]["bytes"] > 0,
            "timeline_exact": a["timeline"] == b["timeline"],
            "file_exact": a["sha256"] == b["sha256"]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fixtures = ROOT / "tests/fixtures"
    source = fixtures / "much-to-me/cam-fixed.mp4"
    master = fixtures / "much-to-me/master.mp3"
    report = {"status": "NOT_RUN", "scope": "two-second flat-camera reduced-package gate",
              "full_stage": False, "encoder_override": "QA only: libx264 -threads:v 1",
              "master_packaging": "First 2.25 s decoded to pcm_f32le WAV; no original master available to B",
              "package_method": "Historical SAT-05 lossless reencode (3–7 s), not GOP-minimal stream copy"}
    try:
        for name in ("A_full", "A_repeat", "B_partial"):
            (OUT / name).mkdir()
            (OUT / ("runtime-" + name)).mkdir()
        package = OUT / "package"
        package.mkdir()
        video = package / "camera.mkv"
        audio = package / "master.wav"
        commands = [["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", "3", "-i", str(source),
                     "-t", "4", "-map", "0:v:0", "-an", "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p", str(video)],
                    ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(master),
                     "-t", "2.25", "-map", "0:a:0", "-vn", "-c:a", "pcm_f32le", str(audio)]]
        started = time.perf_counter()
        for cmd in commands:
            call(cmd)
        report.update(package_commands=commands, package_prepare_sec=time.perf_counter() - started,
                      original_video=media_digest(source), original_audio=media_digest(master),
                      packaged_video=media_digest(video), packaged_audio=media_digest(audio))
        report["pre_export"] = {"video_A": decoded(source, "video", 4),
                                "video_B": decoded(video, "video", 1),
                                "audio_A": decoded(master, "audio"), "audio_B": decoded(audio, "audio")}
        pre = report["pre_export"]
        report["pre_export_exact"] = pre["video_A"] == pre["video_B"] and pre["audio_A"] == pre["audio_B"]
        # Save exact plans and preparation evidence before costly rendering.
        specs = {}
        results = {}
        for label in ("A_full", "A_repeat", "B_partial"):
            is_b = label == "B_partial"
            spec = {"video": str(video if is_b else source), "audio": str(audio if is_b else master),
                    "start": 1 if is_b else 4, "duration": 2,
                    "folder": str(OUT / label), "runtime": str(OUT / ("runtime-" + label)),
                    "originals": [str(source), str(master)] if is_b else [],
                    "mask": [str(fixtures), str(OUT / "A_full"), str(OUT / "A_repeat"),
                             str(OUT / "runtime-A_full"), str(OUT / "runtime-A_repeat")] if is_b else []}
            specs[label] = spec
            specfile = OUT / f"{label}.json"
            specfile.write_text(json.dumps(spec, indent=2))
            cmd = [sys.executable, str(Path(__file__).resolve()), "worker", str(specfile)]
            if is_b:
                cmd = ["sudo", "-n", "unshare", "--mount", "--propagation", "private", *cmd]
            call(cmd, timeout=600)
            results[label] = json.loads((OUT / label / "result.json").read_text())
        report.update(specs=specs, results=results,
                      AA=compare(results["A_full"], results["A_repeat"]),
                      AB=compare(results["A_full"], results["B_partial"]))
        report["package_media_bytes"] = video.stat().st_size + audio.stat().st_size
        report["original_media_bytes"] = source.stat().st_size + master.stat().st_size
        report["package_fraction"] = report["package_media_bytes"] / report["original_media_bytes"]
        report["video_fraction"] = video.stat().st_size / source.stat().st_size
        checks = [report["pre_export_exact"], report["package_fraction"] < 1]
        for pair in (report["AA"], report["AB"]):
            checks.extend([pair["video_exact"], pair["audio_pcm_exact"], pair["timeline_exact"]])
        report["status"] = "PASS_REDUCED_ISOLATED_FLAT_GATE" if all(checks) else "FAIL_REDUCED_ISOLATED_FLAT_GATE"
        report["architecture_approved"] = False
    except Exception as exc:
        report.update(status="INFRASTRUCTURE_OR_EXECUTION_ERROR", error=repr(exc))
    finally:
        (OUT / "REPORT.json").write_text(json.dumps(report, indent=2))
        print("SATURNO09_REDUCED_BEGIN", flush=True)
        print(json.dumps(report), flush=True)
        print("SATURNO09_REDUCED_END", flush=True)
    return 0 if report["status"] == "PASS_REDUCED_ISOLATED_FLAT_GATE" else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        worker(sys.argv[2])
    else:
        raise SystemExit(main())
