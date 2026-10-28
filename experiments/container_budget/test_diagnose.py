"""Deterministic fixture tests; do not require Docker or invoke a renderer."""
import importlib.util
from pathlib import Path


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("container_diagnose", HERE / "diagnose.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_host_is_larger_than_container(tmp_path):
    cgroup = tmp_path / "cgroup"
    cgroup.mkdir()
    (cgroup / "cpu.max").write_text("200000 100000\n")
    (cgroup / "memory.max").write_text(str(8 * 1024**3) + "\n")
    (cgroup / "memory.current").write_text(str(2 * 1024**3) + "\n")
    (cgroup / "memory.peak").write_text(str(3 * 1024**3) + "\n")
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemAvailable: 100000000 kB\n")
    observed = mod.collect(cgroup, meminfo, logical_cpus=32,
                           physical_memory=128 * 1024**3)
    assert observed["resource_mismatch_possible"]
    assert observed["effective_ceilings_estimate"]["cpu_cores"] == 2.0
    assert observed["effective_ceilings_estimate"]["ram_bytes"] == 8 * 1024**3
    assert observed["effective_ceilings_estimate"]["memory_available_bytes"] == 6 * 1024**3
    assert observed["engine_host_based_overlap_guard_estimate"] is True


def test_unknown_cgroup_is_not_reported_as_zero(tmp_path):
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemAvailable: 100 kB\n")
    report = mod.collect(tmp_path, meminfo, logical_cpus=2,
                         physical_memory=4 * 1024**3)
    assert report["cgroup_v2"]["cpu_quota_cores"] is None
    assert report["cgroup_v2"]["memory_max_bytes"] is None
    assert report["engine_host_based_overlap_guard_estimate"] is False
    assert report["resource_mismatch_possible"] is False


def test_unlimited_cgroup_is_not_misread_as_limit(tmp_path):
    (tmp_path / "cpu.max").write_text("max 100000")
    (tmp_path / "memory.max").write_text("max")
    (tmp_path / "memory.current").write_text("1000")
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemAvailable: 500000 kB\n")
    report = mod.collect(tmp_path, meminfo, logical_cpus=4,
                         physical_memory=8 * 1024**3)
    assert report["cgroup_v2"]["memory_max_bytes"] is None
    assert report["cgroup_v2"]["cpu_quota_cores"] is None
    assert report["effective_ceilings_estimate"]["ram_bytes"] == 8 * 1024**3
