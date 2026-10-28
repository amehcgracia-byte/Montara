"""Read-only diagnostic: compare Linux host resources to cgroup quotas.

No user media, network, subprocesses or secrets. Intended for disposable QA.
The 'legacy' values mirror ZuckerVideos engine/core/stages/export.py at pin
60a7b7e9; this tool DOES NOT execute the engine or choose worker counts for it.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def _read(root: Path, name: str) -> str | None:
    try:
        return (root / name).read_text().strip()
    except (OSError, UnicodeError):
        return None


def _nonnegative_int(value: str | None) -> int | None:
    try:
        result = int(value) if value is not None else None
        return result if result is not None and result >= 0 else None
    except (ValueError, TypeError):
        return None


def collect(root: Path = Path("/sys/fs/cgroup"),
            meminfo: Path = Path("/proc/meminfo"),
            logical_cpus: int | None = None,
            physical_memory: int | None = None) -> dict:
    cpu = (root / "cpu.max")
    raw_cpu = _read(root, "cpu.max")
    cpu_quota = None
    if raw_cpu:
        values = raw_cpu.split()
        if len(values) == 2 and values[0] != "max":
            quota, period = _nonnegative_int(values[0]), _nonnegative_int(values[1])
            if quota is not None and period is not None and period > 0:
                cpu_quota = quota / period
    limit_raw = _read(root, "memory.max")
    memory_limit = None if limit_raw == "max" else _nonnegative_int(limit_raw)
    current = _nonnegative_int(_read(root, "memory.current"))
    peak = _nonnegative_int(_read(root, "memory.peak"))
    cpus = logical_cpus if logical_cpus is not None else os.cpu_count()
    if physical_memory is None:
        try:
            physical_memory = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        except (AttributeError, OSError, ValueError):
            physical_memory = None
    available = None
    try:
        for line in meminfo.read_text().splitlines():
            if line.startswith("MemAvailable:"):
                available = int(line.split()[1]) * 1024
                break
    except (OSError, ValueError, IndexError):
        pass
    effective_cpu = min(float(cpus), cpu_quota) if cpus and cpu_quota is not None else (float(cpus) if cpus else cpu_quota)
    effective_ram = min(physical_memory, memory_limit) if physical_memory is not None and memory_limit is not None else (memory_limit if memory_limit is not None else physical_memory)
    remaining_limit = max(0, memory_limit - current) if memory_limit is not None and current is not None else None
    effective_available = min(available, remaining_limit) if available is not None and remaining_limit is not None else (remaining_limit if remaining_limit is not None else available)
    # Mirrors the host-based guard at the inspected pin, not the complete engine.
    legacy_overlap = (physical_memory is not None and available is not None
                      and physical_memory >= 16 * 1024**3 and available >= 2 * 1024**3)
    return {
        "scope": "read-only diagnostic, not Montara runtime benchmark",
        "host": {"logical_cpus": cpus, "physical_ram_bytes": physical_memory,
                 "memavailable_bytes": available},
        "cgroup_v2": {"cpu_max": raw_cpu, "cpu_quota_cores": cpu_quota,
                      "memory_max_bytes": memory_limit, "memory_current_bytes": current,
                      "memory_peak_bytes": peak},
        "effective_ceilings_estimate": {"cpu_cores": effective_cpu, "ram_bytes": effective_ram,
                                         "memory_available_bytes": effective_available},
        "engine_host_based_overlap_guard_estimate": legacy_overlap,
        "resource_mismatch_possible": bool(
            (cpu_quota is not None and cpus is not None and cpu_quota < cpus)
            or (memory_limit is not None and physical_memory is not None and memory_limit < physical_memory)),
        "limitations": [
            "Only cgroup v2; no cgroup v1, memory.high or cpuset accounting.",
            "Effective RAM estimate is a ceiling, not a safe concurrency budget.",
            "Engine worker settings and actual CPU/RAM loads are not sampled.",
            "No image, preview, render or media file is touched.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cgroup", type=Path, default=Path("/sys/fs/cgroup"))
    parser.add_argument("--meminfo", type=Path, default=Path("/proc/meminfo"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = collect(args.cgroup, args.meminfo)
    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
