"""Deterministic tests for candidate CPU/RAM cgroup policy; no Docker required."""
from pathlib import Path
from resource_policy import Budget, GIB, inspect, overlap_allowed, segment_workers

def make(tmp_path, cpu, mem_limit, current):
    cg = tmp_path / "cg"; cg.mkdir()
    (cg / "cpu.max").write_text(cpu)
    (cg / "memory.max").write_text(mem_limit)
    (cg / "memory.current").write_text(str(current))
    mem = tmp_path / "meminfo"; mem.write_text("MemAvailable: 90000000 kB\n")
    return inspect(cg, mem, cpus=32, ram=128*GIB)

def test_limited_two_cpus_eight_gib(tmp_path):
    b = make(tmp_path, "200000 100000", str(8*GIB), 2*GIB)
    assert b == Budget(2.0, 8*GIB, 6*GIB)
    assert segment_workers(b, 233, 8) == 1
    assert not overlap_allowed(b)

def test_sixteen_gib_with_headroom(tmp_path):
    b = make(tmp_path, "800000 100000", str(16*GIB), 5*GIB)
    assert segment_workers(b, 233) == 4
    assert overlap_allowed(b)

def test_unlimited_cgroup(tmp_path):
    b = make(tmp_path, "max 100000", "max", 0)
    assert b.effective_cpus == 32
    assert b.effective_ram == 128*GIB
    assert segment_workers(b, 233, 6) == 6

def test_half_cpu_one_gib(tmp_path):
    b = make(tmp_path, "50000 100000", str(GIB), GIB//2)
    assert segment_workers(b, 10) == 1
    assert not overlap_allowed(b)
