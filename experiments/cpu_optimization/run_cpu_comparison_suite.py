#!/usr/bin/env python3
"""Run a small, reproducible CPU/FFmpeg comparison suite, without engine changes.

Not a full E2E. F4 uses the historical low-resolution fixture, not real 360.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]

def invoke(cmd, log):
    print("$", " ".join(map(str,cmd)), flush=True)
    t=time.perf_counter()
    with log.open("w", encoding="utf-8") as h:
        p=subprocess.run(cmd, cwd=ROOT, stdout=h, stderr=subprocess.STDOUT, check=False)
    print(f"  exit={p.returncode}; wall={time.perf_counter()-t:.2f}s; log={log}",flush=True)
    if p.returncode:
        print(log.read_text(errors="replace")[-2000:],flush=True)
        raise SystemExit(f"Failed: {cmd[1]}")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    out=a.output.resolve()
    out.mkdir(parents=True,exist_ok=False)
    def output(command):
        try:
            return subprocess.check_output(command,text=True,stderr=subprocess.STDOUT,timeout=10).strip()
        except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired):
            return "unavailable"
    manifest={
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "git_sha":output(["git","rev-parse","HEAD"]),
        "git_status":output(["git","status","--short"]),
        "python":platform.python_version(),
        "platform":platform.platform(),
        "cpu_count_python":os.cpu_count(),
        "nproc":output(["nproc"]),
        "lscpu":output(["lscpu"]),
        "free":output(["free","-h"]),
        "ffmpeg_version":output(["ffmpeg","-version"]).splitlines()[0],
        "ffprobe_version":output(["ffprobe","-version"]).splitlines()[0],
        "loadavg":output(["cat","/proc/loadavg"]),
        "tests":[],
        "caveats":["Microbenchmark single-process is not a scaling test across core counts.",
                   "F4 source is tiny synthetic/fixture 360, not real 5.7K footage.",
                   "The old 4-vCPU E2E had unrelated CPU contention; do not compare directly.",
                   "FFprobe is an I/O/metadata probe, not a full rendering benchmark.",
                   "Only compare identical workload, OS/tool versions and uncontended environment."]
    }
    def test(name,cmd):
        t=time.perf_counter()
        invoke(cmd,out/f"{name}.log")
        manifest["tests"].append({"name":name,"elapsed_sec":round(time.perf_counter()-t,3),"status":"PASS"})
        (out/"manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    py=os.sys.executable
    test("interval_index", [py,"experiments/cpu_optimization/benchmark_interval_index.py",
            "--sizes","200,1000,3000","--repeats","5","--output",str(out/"interval_index")])
    fixture=ROOT/"tests/fixtures/real/cam-360.mp4"
    if fixture.is_file() and shutil.which("ffmpeg") and shutil.which("ffprobe"):
        test("f4_v360",[py,"experiments/media_optimization/f4_v360_benchmark.py",
              "--source",str(fixture),"--seconds","2","--repeats","2",
              "--width","640","--height","360","--threads","2","--output",str(out/"f4_v360")])
        # ffprobe batching experiment: independent of the above render
        test("cadence",[py,"experiments/export_profile/benchmark_cadence_batch.py",
              str(fixture),"--runs","3"])
    else:
        manifest["tests"].append({"name":"f4_v360_and_cadence","status":"SKIPPED","reason":"Missing fixture or FFmpeg"})
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    print("\n=== RESUMEN ===")
    s=out/"interval_index"/"summary.json"
    if s.is_file():
        for r in json.loads(s.read_text())["results"]:
            print(f"{r['case']:7s} {r['size']:4d} original={r['original_median_ms']:9.3f}ms indexed={r['indexed_median_ms']:9.3f}ms x{r['speedup_x']}")
    s=out/"f4_v360"/"summary.json"
    if s.is_file():
        d=json.loads(s.read_text())
        print(f"F4: median_lanczos={d['median_lanczos_s']:.3f}s median_linear={d['median_linear_s']:.3f}s median_saving={d['median_saving_pct']:.1f}% SSIM={d['median_ssim_all']:.6f}")
    print("Reports:",out)
    print("No complete E2E or heavy GOP selective renders were run.")

if __name__=="__main__":
    main()
