"""Cgroup-aware CPU/RAM scheduling policy candidate (not wired to the engine)."""
from dataclasses import dataclass
from pathlib import Path
import math
import os

GIB = 1024 ** 3

def read(path):
    try: return path.read_text().strip()
    except (OSError, UnicodeError): return None

def number(value):
    try:
        n = int(value)
        return n if n >= 0 else None
    except (ValueError, TypeError): return None

@dataclass(frozen=True)
class Budget:
    effective_cpus: float
    effective_ram: int | None
    available_ram: int | None

def inspect(root=Path("/sys/fs/cgroup"), meminfo=Path("/proc/meminfo"), *, cpus=None, ram=None):
    cpus = max(1, cpus or os.cpu_count() or 1)
    if ram is None:
        try: ram = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        except (AttributeError, OSError, ValueError): pass
    quota = None
    parts = (read(root / "cpu.max") or "").split()
    if len(parts) == 2 and parts[0] != "max":
        q, period = number(parts[0]), number(parts[1])
        if q is not None and period and period > 0: quota = q / period
    limit_text = read(root / "memory.max")
    limit = None if limit_text == "max" else number(limit_text)
    current = number(read(root / "memory.current"))
    available_host = None
    try:
        for line in meminfo.read_text().splitlines():
            if line.startswith("MemAvailable:"):
                available_host = int(line.split()[1]) * 1024
                break
    except (OSError, ValueError, IndexError): pass
    totals = [x for x in (ram, limit) if x is not None]
    usable = [x for x in (available_host,
              max(0, limit-current) if limit is not None and current is not None else None) if x is not None]
    return Budget(min(float(cpus), quota) if quota is not None else float(cpus),
                  min(totals) if totals else None, min(usable) if usable else None)

def segment_workers(budget: Budget, segments: int, configured: int = 2) -> int:
    """Conservative hypothesis: benchmark before replacing actual engine policy."""
    if segments <= 0: return 1
    cpu_limit = max(1, math.floor(budget.effective_cpus / 2))
    mem_limit = max(1, budget.effective_ram // (2*GIB)) if budget.effective_ram is not None else 1
    wanted = configured if configured > 2 else cpu_limit
    return max(1, min(segments, 8, wanted, cpu_limit, mem_limit))

def overlap_allowed(budget: Budget, enabled=True) -> bool:
    return bool(enabled and budget.effective_ram is not None and
                budget.available_ram is not None and
                budget.effective_ram >= 16*GIB and budget.available_ram >= 2*GIB)
