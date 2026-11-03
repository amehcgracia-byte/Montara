#!/usr/bin/env python3
"""EX14H13B: isolated small 2-job Stage 360 throughput test on current 8-vCPU VM.

Compares two optimized B runs sequentially with two independent B workers
running concurrently. The worker runs actual ExportStage using original HEVC
360, separate project/cache roots, 60 frames, and cleans its own media.

NO production changes, no shared engine changes, no kill of unrelated jobs.
Preflight stops on memory/disk/load or if JM has a render process running.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HARNESSED = Path(__file__).with_name("ex14h11_stage_real_hevc_export_abba.py")
if not HARNESSED.is_file():
    raise SystemExit("STOP: sibling harness missing")

spec = importlib.util.spec_from_file_location("stage_original", HARNESSED)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)

MIN_FREE = 12 * (1024**3)
MIN_AVAILABLE = 8 * (1024**3)
TIMEOUT = 100.0


def available_ram_bytes():
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1])*1024
    raise RuntimeError("STOP: cannot read available memory")


def check_safety():
    free = shutil.disk_usage("/home/fer").free
    available = available_ram_bytes()
    load1, _, _ = os.getloadavg()
    if os.cpu_count() != 8 or len(os.sched_getaffinity(0)) != 8:
        raise RuntimeError("STOP: expected eight available vCPUs")
    if free < MIN_FREE:
        raise RuntimeError(f"STOP: disk free {free/1024**3:.1f} GiB < 12 GiB")
    if available < MIN_AVAILABLE:
        raise RuntimeError(f"STOP: available RAM {available/1024**3:.1f} GiB < 8 GiB")
    if load1 > 2.0:
        raise RuntimeError(f"STOP: host busy, load1={load1:.2f}")
    p = subprocess.run(["ps", "-eo", "user=,args="],capture_output=True,text=True,check=True)
    for line in p.stdout.splitlines():
        user, _, command = line.strip().partition(" ")
        # Check JM only: do not interfere with JM or run while JM is rendering.
        if user == "jm" and any(token in command.lower() for token in (
            "ffmpeg", "ffprobe", "montara-bench", "run_history.py",
            "mixer_adapter", "render-song", "uvicorn", "celery"
        )):
            raise RuntimeError("STOP: JM active task detected (no intervention)")
    return {"disk_free_gib":round(free/1024**3,2),
            "ram_available_gib":round(available/1024**3,2),
            "load1":round(load1,2)}


def validate_engine():
    if h.capture(["git","-C",str(h.ROOT),"rev-parse","--short","HEAD"]) != "0f9ec03":
        raise RuntimeError("STOP: wrong engine HEAD")
    if h.capture(["git","-C",str(h.ROOT),"status","--porcelain"]):
        raise RuntimeError("STOP: engine worktree dirty")


def worker(root):
    validate_engine()
    check_safety()
    source = h.source()
    original = (source.stat().st_size,source.stat().st_mtime_ns)
    sys.path.insert(0,str(h.ROOT))
    with tempfile.TemporaryDirectory(prefix="jupiter_job_",dir=root) as temp:
        result=h.run_one(Path(temp),source,"B",1)
    if original != (source.stat().st_size,source.stat().st_mtime_ns):
        raise RuntimeError("STOP: original media changed")
    print("EX14H13B_WORKER_RESULT "+json.dumps({
        "stage_wall_sec":result["wall_sec"],
        "segment_sec":result["segment_ffmpeg_sec"],
        "frames":result["video_frames"],
        "audio_sha":result["audio_pcm_sha256"]
    }),flush=True)


def run_group(label,count,parallel,root):
    check_safety()
    processes=[]
    log_files=[]
    started=time.perf_counter()
    try:
        for i in range(count):
            check_safety()
            path=root/f"{label}_{i}.log"
            stream=path.open("w")
            log_files.append(stream)
            process=subprocess.Popen([
                sys.executable,"-u",str(Path(__file__).resolve()),
                "--worker-root",str(root)
            ],stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            processes.append((process,path))
            if not parallel:
                wait_one(process,started)
        if parallel:
            for process,path in processes:
                wait_one(process,started)
        wall=time.perf_counter()-started
    except BaseException:
        for process,_ in processes:
            if process.poll() is None:
                try:
                    os.killpg(process.pid,signal.SIGTERM)
                except ProcessLookupError:
                    pass
        for process,_ in processes:
            if process.poll() is None:
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
        raise
    finally:
        for stream in log_files:
            stream.close()

    results=[]
    for process,path in processes:
        content=path.read_text(errors="replace")
        rows=[line.split("EX14H13B_WORKER_RESULT ",1)[1]
              for line in content.splitlines()
              if line.startswith("EX14H13B_WORKER_RESULT ")]
        if process.returncode != 0 or len(rows) != 1:
            raise RuntimeError(f"STOP: worker failed code={process.returncode} log_tail={content[-1200:]}")
        results.append(json.loads(rows[0]))
    if len({x["audio_sha"] for x in results}) != 1:
        raise RuntimeError("STOP: audio hashes mismatch")
    record={"group":label,"group_wall_sec":round(wall,3),
            "jobs":count,"parallel":parallel,
            "jobs_per_min":round(60*count/wall,3),
            "individual_stage_sec":[x["stage_wall_sec"] for x in results],
            "individual_segment_sec":[x["segment_sec"] for x in results],
            "audio_identical":True,"frames_per_job":[x["frames"] for x in results]}
    print("EX14H13B_GROUP "+json.dumps(record),flush=True)
    return record


def wait_one(p,started):
    time_left=TIMEOUT-(time.perf_counter()-started)
    if time_left <= 0:
        raise RuntimeError("STOP: group timeout")
    try:
        code=p.wait(timeout=time_left)
    except subprocess.TimeoutExpired:
        raise RuntimeError("STOP: group timeout")
    if code:
        raise RuntimeError(f"STOP: worker failed exit code {code}")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--worker-root",type=Path)
    args=parser.parse_args()
    if args.worker_root:
        worker(args.worker_root)
        return
    validate_engine()
    stats=check_safety()
    print("EX14H13B_START "+json.dumps({"preflight":stats,
          "scope":"2s 360 real ExportStage, mode B opt-in",
          "limit":"2 concurrent workers; no large load",
          "notes":"VM load and disk free may change during runs; this is a small screening"}),flush=True)
    with tempfile.TemporaryDirectory(prefix="jupiter_ex14h13b_",dir="/home/fer") as tmp:
        root=Path(tmp)
        seq=run_group("sequential",2,False,root)
        parallel=run_group("parallel",2,True,root)
        print("EX14H13B_RESULT "+json.dumps({
            "sequential_wall_sec":seq["group_wall_sec"],
            "parallel_wall_sec":parallel["group_wall_sec"],
            "throughput_gain_pct":round(100*(parallel["jobs_per_min"]/
                                              seq["jobs_per_min"]-1),2),
            "caveat":"one sequential pair and one parallel pair: not a production capacity claim"
        }),flush=True)
    print("EX14H13B_COMPLETE_ALL_TEMP_MEDIA_CLEANED",flush=True)


if __name__=="__main__":
    main()
