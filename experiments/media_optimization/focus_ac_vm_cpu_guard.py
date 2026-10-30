#!/usr/bin/env python3
"""FOCUS A/C shared-VM safety gate. Read-only, no ffmpeg or transcodes.

Samples /proc/stat twice for a *real interval CPU utilization estimate*, reports
1/5/15 minute load, available memory, and video process owners. Intentionally
does not launch any heavy job: READY means operator may schedule a guarded
test, not that Chema granted exclusive use of the server.
"""
import argparse
import json
import os
import subprocess
import time
from pathlib import Path

def cpu_times():
    fields=Path("/proc/stat").read_text().splitlines()[0].split()[1:]
    vals=[int(x) for x in fields]
    idle=vals[3]+(vals[4] if len(vals)>4 else 0)
    return sum(vals),idle

def sample_cpu(interval):
    t1,i1=cpu_times()
    time.sleep(interval)
    t2,i2=cpu_times()
    return 100*(1-(i2-i1)/(t2-t1)) if t2>t1 else None

def processes():
    rows=[]
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():continue
        try:
            cmd=(d/"comm").read_text().strip()
            if cmd not in {"ffmpeg","ffprobe"}:continue
            uid=(d/"status").read_text().split("Uid:")[1].splitlines()[0].split()[0]
            import pwd
            owner=pwd.getpwuid(int(uid)).pw_name
            rows.append({"pid":int(d.name),"owner":owner,"command":cmd})
        except (OSError,IndexError,KeyError):continue
    return sorted(rows,key=lambda x:x["pid"])

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--interval",type=float,default=2.0)
    p.add_argument("--output",type=Path)
    p.add_argument("--threshold",type=float,default=65.0,
                   help="Maximum CPU %% to mark low-load; conservative default 65")
    args=p.parse_args()
    if not 0.5<=args.interval<=10:p.error("interval must be 0.5..10 seconds")
    cpu=sample_cpu(args.interval)
    load=os.getloadavg()
    procs=processes()
    cores=os.cpu_count() or 1
    busy=any(x["command"]=="ffmpeg" for x in procs)
    safe=(not busy and cpu is not None and cpu<args.threshold and load[0]<cores*.75)
    report={"status":"LOW_LOAD_CANDIDATE" if safe else "BUSY_NO_HEAVY_TEST",
      "cpu_percent_sampled":round(cpu,1) if cpu is not None else None,
      "sample_seconds":args.interval,"logical_cpus":cores,
      "load_average_1_5_15":[round(x,2) for x in load],
      "video_processes":procs,"ffmpeg_active":busy,
      "decision":"Only read-only preflights allowed" if not safe else
         "Light load observed; still coordinate with shared-VM user before heavy tests",
      "caveat":"CPU utilization is a short system-wide sample, not process-by-process accounting."}
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if args.output:
        if args.output.exists():p.error("Refusing to overwrite report")
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
if __name__=="__main__":main()
