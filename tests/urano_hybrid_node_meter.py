"""Opt-in, passive URANO measurement agent for server or local Companion.

Measure only a named existing PID and descendants. Never launch an app,
read original videos, send network traffic, or expose process commands/secrets.
A report by itself is *self-reported evidence*, NOT remote-host attestation.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import statistics
import time
from pathlib import Path

import psutil

_LABEL = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
_ROLES = ("client_companion", "client_browser", "server")
_SCHEMA = "urano-distributed-node-v1"


def _label(value: str) -> str:
    if not isinstance(value, str) or not _LABEL.fullmatch(value):
        raise ValueError("Use a non-identifying, short ASCII label")
    return value


def _snapshot(root: psutil.Process) -> dict:
    """Sum CPU across PID tree, RSS is observed simultaneous snapshot."""
    try:
        processes = [root, *root.children(recursive=True)]
    except psutil.Error:
        processes = [root]
    live = {}
    for p in processes:
        try:
            if not p.is_running() or p.status() == psutil.STATUS_ZOMBIE:
                continue
            t = p.cpu_times()
            # PID + create_time avoids aliasing after a process exits.
            identity = f"{p.pid}:{p.create_time():.6f}"
            live[identity] = {
                "cpu_seconds": t.user + t.system,
                "rss_bytes": p.memory_info().rss,
            }
        except (psutil.Error, OSError):
            continue
    return live


def sample_process_tree(pid: int, *, interval: float = 0.5,
                        duration: float = 30.0, limit_samples: int = 10000,
                        clock=time.monotonic, sleeper=time.sleep) -> dict:
    if not isinstance(pid, int) or pid < 1:
        raise ValueError("A positive existing PID is required")
    if not 0.1 <= interval <= 10 or not 0.1 <= duration <= 3600:
        raise ValueError("Invalid observation interval/duration")
    if not 1 <= limit_samples <= 10000:
        raise ValueError("Invalid sample limit")
    try:
        process = psutil.Process(pid)
        original_start = process.create_time()
    except psutil.Error as exc:
        raise ValueError("The given PID is not running") from exc

    began = clock()
    deadline = began + duration
    high_rss = 0
    cpu_observed = 0.0
    samples = 0
    previous: dict = {}
    observed_rss = []
    exited = False
    while samples < limit_samples:
        now = clock()
        if now >= deadline and samples > 0:
            break
        try:
            if not process.is_running() or process.create_time() != original_start or process.status() == psutil.STATUS_ZOMBIE:
                exited = True
                break
        except psutil.Error:
            exited = True
            break
        live = _snapshot(process)
        if not live:
            exited = True
            break
        instantaneous_rss = sum(p["rss_bytes"] for p in live.values())
        observed_rss.append(instantaneous_rss)
        high_rss = max(high_rss, instantaneous_rss)
        for identity, stats in live.items():
            earlier = previous.get(identity)
            if earlier is not None:
                cpu_observed += max(0.0, stats["cpu_seconds"] - earlier)
            # Never count a newly discovered process's lifetime CPU before
            # observation began. This makes the counter a conservative estimate.
        previous = {identity: stats["cpu_seconds"] for identity, stats in live.items()}
        samples += 1
        if clock() >= deadline:
            break
        sleeper(min(interval, max(0.0, deadline - clock())))

    elapsed = max(0.0, clock() - began)
    return {
        "observation_seconds": round(elapsed, 3),
        "samples": samples,
        "root_exited_during_observation": exited,
        "cpu_seconds_observed_lower_bound": round(cpu_observed, 3),
        "rss_bytes_sampled_peak": high_rss,
        "rss_bytes_sampled_median": int(statistics.median(observed_rss)) if observed_rss else None,
        "method": "psutil-pid-tree-sampled",
    }


def build_report(*, run_id: str, physical_host_label: str, role: str,
                 results: dict, workload: str = "unknown", project_count: int = 1,
                 scenario_clients: int = 2) -> dict:
    _label(run_id)
    _label(physical_host_label)
    if role not in _ROLES:
        raise ValueError("Choose client_companion, client_browser, or server")
    if workload not in ("synthetic", "controlled-real", "unknown"):
        raise ValueError("Invalid workload")
    if type(project_count) is not int or project_count < 0 or project_count > 25:
        raise ValueError("Invalid project count")
    if scenario_clients not in (2, 4, 8, 10, 25):
        raise ValueError("Invalid scale level")
    return {
        "schema": _SCHEMA,
        "run_id": run_id,
        "host_label": physical_host_label,
        "host_label_source": "operator-self-declared-not-verified",
        "role": role,
        "scenario_clients": scenario_clients,
        "project_count": project_count,
        "workload": workload,
        "platform": platform.system().lower(),
        "logical_cpus": os.cpu_count(),
        "sample": results,
        # Host-wide network totals would mix unrelated traffic. Only future
        # instrumented HTTP request counters may populate transport bytes.
        "transport": {
            "proxy_upload_bytes": None,
            "recipe_download_bytes": None,
            "original_upload_bytes": None,
            "latency_ms_p50": None,
        },
        "remote_server_verified": False,
        "physical_machine_distinctness_verified": False,
        "no_media_or_secrets_collected": True,
    }


def save_report(path: Path, report: dict):
    if path.is_symlink():
        raise ValueError("Refusing symlinked report path")
    parent = path.parent.resolve()
    if not parent.is_dir():
        raise ValueError("Create output directory before recording")
    # Exclusively create; a run cannot overwrite an existing result.
    with path.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2)
        output.write("\n")


def main():
    parser = argparse.ArgumentParser(description="Read-only PID tree telemetry; no remote actions")
    parser.add_argument("--pid", type=int, required=True, help="Existing Companion/browser/server process PID")
    parser.add_argument("--role", choices=_ROLES, required=True)
    parser.add_argument("--run-id", required=True, help="Same opaque trial label on participating machines")
    parser.add_argument("--host-label", required=True, help="Operator label, no hostname/IP/PII")
    parser.add_argument("--scenario-clients", type=int, choices=(2, 4, 8, 10, 25), default=2)
    parser.add_argument("--project-count", type=int, default=1)
    parser.add_argument("--workload", choices=("synthetic", "controlled-real", "unknown"), default="synthetic")
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Validate report fields before measuring so malformed output destinations
    # cannot waste CPU or cause mutation after observation.
    _label(args.run_id)
    _label(args.host_label)
    sample = sample_process_tree(args.pid, interval=args.interval, duration=args.duration)
    report = build_report(run_id=args.run_id, physical_host_label=args.host_label,
                          role=args.role, scenario_clients=args.scenario_clients,
                          project_count=args.project_count, workload=args.workload, results=sample)
    save_report(args.output, report)
    print(json.dumps({"measured": True, "role": args.role, "samples": sample["samples"],
                      "network_measured": False, "distributed_verified": False}))


if __name__ == "__main__":
    main()
