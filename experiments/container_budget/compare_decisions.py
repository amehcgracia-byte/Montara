"""Compare pinned ZuckerVideos worker/overlap decisions with experimental budget.

This is an analytic comparison only. Never invokes FFmpeg or product engine.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

from resource_policy import inspect, segment_workers, overlap_allowed, GIB


def legacy_workers(host_cpus: int, host_ram: int, segments: int, configured: int=2) -> int:
    if configured > 2:
        return max(1, min(configured, segments or 1, 8))
    cpu_count = max(2, host_cpus)
    workers = max(2, min(8, cpu_count // 2))
    workers = min(workers, max(2, int((host_ram / GIB) // 2)))
    return max(1, min(workers, segments or 1))


def compare(cgroup_root: Path, meminfo: Path, *, segments=233, configured=2,
            host_cpus=None, host_ram=None) -> dict:
    budget = inspect(cgroup_root, meminfo, cpus=host_cpus, ram=host_ram)
    ncpu = host_cpus or os.cpu_count() or 2
    if host_ram is None:
        host_ram = os.sysconf("SC_PAGE_SIZE")*os.sysconf("SC_PHYS_PAGES")
    available_host = None
    for line in meminfo.read_text().splitlines():
        if line.startswith("MemAvailable:"):
            available_host = int(line.split()[1])*1024
            break
    host_overlap = (host_ram>=16*GIB and available_host is not None and available_host>=2*GIB)
    return {
        "comparison_scope":"policy decision only; render speed and OOM are NOT measured",
        "segments":segments,"configured_workers":configured,
        "host": {"cpus":ncpu,"ram_bytes":host_ram},
        "effective":{"cpus":budget.effective_cpus,"ram_bytes":budget.effective_ram,
                     "available_ram_bytes":budget.available_ram},
        "legacy_workers":legacy_workers(ncpu,host_ram,segments,configured),
        "candidate_workers":segment_workers(budget,segments,configured),
        "legacy_overlap":host_overlap,
        "candidate_overlap":overlap_allowed(budget),
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--cgroup",type=Path,default=Path("/sys/fs/cgroup"))
    parser.add_argument("--meminfo",type=Path,default=Path("/proc/meminfo"))
    parser.add_argument("--segments",type=int,default=233)
    parser.add_argument("--configured-workers",type=int,default=2)
    args=parser.parse_args()
    if args.segments<0 or args.configured_workers<0:
        parser.error("counts must be non-negative")
    print(json.dumps(compare(args.cgroup,args.meminfo,segments=args.segments,
                             configured=args.configured_workers),indent=2))


if __name__=="__main__":
    main()
