"""URANO hybrid (web / server / local Companion) concurrent E2E bench.

Two modes must NOT be conflated:
- shared-runner: two isolated browser+server+Companion stacks on ONE CI machine,
  useful for integration/CPU contention, NOT a distributed deployment result.
- distributed: report validation only; agents on separate physical hosts
  produce signed/attested results later. We do NOT invent remote benchmarks.

No originals are uploaded or copied to reports. Outputs remain local scratch.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

MAX_CLIENTS_SHARED = 2
SCALE_LEVELS = (2, 4, 8, 10, 25)


def _safe_scratch(path: Path) -> Path:
    raw = path.expanduser()
    if raw.is_symlink():
        raise ValueError("Refusing symlinked scratch directory")
    root = raw.resolve()
    if root == Path("/") or root == Path.home().resolve():
        raise ValueError("Refusing unsafe scratch root")
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise ValueError("Use an empty dedicated scratch directory")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _rooted_process_roles(pid: int):
    """Snapshot observed CPU/RSS per component, including child FFmpeg processes.

    A descendant belongs to local Companion or server if an ancestor launched
    that component. FFmpeg fixture generation by the E2E driver is 'other',
    never incorrectly charged to the server or local export.
    """
    if psutil is None:
        return {}
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
    except (psutil.Error, OSError):
        return {}
    found = {}
    for child in children:
        try:
            commands = []
            node = child
            while node.pid != pid:
                commands.append(" ".join(node.cmdline()).lower())
                node = node.parent()
                if node is None:
                    break
            if any("companion.py" in c for c in commands):
                role = "local_companion"
            elif any("app.py" in c and "--port" in c for c in commands):
                role = "server"
            elif any("chromium" in c or "chrome" in c or "playwright" in c
                     for c in commands):
                role = "browser"
            else:
                role = "fixture_or_controller"
            found[child.pid] = {
                "role": role, "cpu_seconds": sum(child.cpu_times()[:2]),
                "rss_bytes": child.memory_info().rss
            }
        except (psutil.Error, OSError):
            continue
    return found


def _monitor(processes, period=0.5):
    """Sampling only: not cgroup meters and not resource billing counters."""
    roles = ("local_companion", "server", "browser", "fixture_or_controller")
    metrics = {key: {
        "peak_rss_bytes": 0,
        "cpu_seconds_observed": 0.0,
        "cpu_seconds_by_role_observed": {role: 0.0 for role in roles},
        "peak_rss_by_role_bytes_observed": {role: 0 for role in roles},
        "completed_monotonic": None,
    } for key in processes}
    snapshots = {key: {} for key in processes}
    while any(p.poll() is None for p in processes.values()):
        for key, process in processes.items():
            if process.poll() is not None:
                if metrics[key]["completed_monotonic"] is None:
                    metrics[key]["completed_monotonic"] = time.monotonic()
                continue
            children = _rooted_process_roles(process.pid)
            rss = sum(value["rss_bytes"] for value in children.values())
            metrics[key]["peak_rss_bytes"] = max(metrics[key]["peak_rss_bytes"], rss)
            grouped_rss = {role: 0 for role in roles}
            for pid, value in children.items():
                role = value["role"]
                grouped_rss[role] += value["rss_bytes"]
                old = snapshots[key].get(pid, 0.0)
                delta = max(0.0, value["cpu_seconds"] - old)
                metrics[key]["cpu_seconds_observed"] += delta
                metrics[key]["cpu_seconds_by_role_observed"][role] += delta
            for role, value in grouped_rss.items():
                metrics[key]["peak_rss_by_role_bytes_observed"][role] = max(
                    metrics[key]["peak_rss_by_role_bytes_observed"][role], value)
            snapshots[key] = {pid: val["cpu_seconds"] for pid, val in children.items()}
        time.sleep(period)
    for key in metrics:
        if metrics[key]["completed_monotonic"] is None:
            metrics[key]["completed_monotonic"] = time.monotonic()
    return metrics


def _summarize(root: Path, processes, starts, observations):
    per_client = []
    for name, proc in processes.items():
        folder = root / name
        summary_file = folder / "summary.json"
        summary = {}
        if summary_file.is_file():
            summary = json.loads(summary_file.read_text())
        video_file = folder / "render.mp4"
        success = proc.returncode == 0 and summary.get("passed") is True
        # e2e_native_stage's summary currently has no 'passed' field; this
        # test's success criterion is an actual original-quality MP4 + metadata.
        success = (proc.returncode == 0 and summary.get("native_render") is True
                   and summary.get("server_export_skipped") is True
                   and video_file.is_file() and video_file.stat().st_size > 0)
        per_client.append({
            "client_id": name,
            "success": success,
            "returncode": proc.returncode,
            "wall_seconds": round((observations[name].get("completed_monotonic")
                                   or time.monotonic()) - starts[name], 3),
            "native_mp4_bytes": video_file.stat().st_size if video_file.is_file() else None,
            "companion_local_original_render": summary.get("native_render") is True,
            "server_export_skipped": summary.get("server_export_skipped") is True,
            "original_sources": summary.get("original_sources"),
            "observed_cpu_seconds_process_tree": round(observations[name]["cpu_seconds_observed"], 3),
            "sampled_peak_rss_bytes": observations[name]["peak_rss_bytes"],
            "observed_cpu_seconds_by_role": observations[name].get("cpu_seconds_by_role_observed"),
            "sampled_peak_rss_by_role_bytes": observations[name].get("peak_rss_by_role_bytes_observed"),
        })
    nsuccess = sum(p["success"] for p in per_client)
    times = [p["wall_seconds"] for p in per_client]
    return {
        "schema": "urano-hybrid-bench-v1",
        "topology": "shared-runner-integration-only",
        "shared_physical_cpu": True,
        "distributed_result": False,
        "server_remote": False,
        "companion_runs_on_separate_client_machines": False,
        "level": len(per_client),
        "scale_levels_planned": list(SCALE_LEVELS),
        "completed": nsuccess,
        "failed": len(per_client) - nsuccess,
        "all_passed": nsuccess == len(per_client),
        "max_client_wall_seconds": round(max(times), 3) if times else None,
        "p50_client_wall_seconds": round(statistics.median(times), 3) if times else None,
        "network_bytes_to_server": None,
        "network_bytes_to_companion": None,
        "hardware": {"cpu_count_logical": os.cpu_count(), "os": platform.system()},
        "clients": per_client,
        "limitations": [
            "All client browser/server/Companion processes run on one physical runner.",
            "Local synthetic footage is NOT customer original media.",
            "CPU measurements are sampled process-tree observations, not per-machine telemetry.",
            "No physical Mac, remote server, WAN latency, bandwidth, token quotas or authenticated workers.",
            "Do not extrapolate 2 clients on CI to 25 distributed customers."
        ],
    }


def run_shared_runner(out: Path, *, clients: int) -> dict:
    if clients != 2:
        raise ValueError("Shared-runner heavy E2E is capped at 2; never run 4/8/10/25 on a CI runner")
    if psutil is None:
        raise RuntimeError("psutil required for observed CPU/RSS metrics")
    root = _safe_scratch(out)
    test = Path(__file__).resolve().parent / "e2e_native_stage.py"
    processes = {}
    logs = []
    started = {}
    try:
        for i in range(clients):
            name = f"client-{i+1:02d}"
            folder = root / name
            # E2E creates its own isolated server + Companion + browser and
            # synthetic source originals within its own dedicated workspace.
            path = root / f"{name}.log"
            handle = path.open("w")
            logs.append(handle)
            env = {**os.environ, "PYTHONUNBUFFERED": "1"}
            process = subprocess.Popen(
                [sys.executable, str(test), "--output", str(folder)],
                env=env, stdout=handle, stderr=subprocess.STDOUT)
            processes[name] = process
            started[name] = time.monotonic()
        observations = _monitor(processes)
        for proc in processes.values():
            proc.wait(timeout=15)
        result = _summarize(root, processes, started, observations)
        (root / "hybrid-report.json").write_text(json.dumps(result, indent=2))
        print(json.dumps({
            "all_passed": result["all_passed"], "completed": result["completed"],
            "level": result["level"], "topology": result["topology"],
            "distributed_result": False, "max_client_wall_seconds": result["max_client_wall_seconds"]
        }), flush=True)
        return result
    finally:
        for proc in processes.values():
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
        for handle in logs:
            handle.close()


def validate_distributed_nodes(nodes: list[dict]) -> bool:
    """Reject faux-distributed claims for two clients on a single physical box."""
    if len(nodes) < 2:
        raise ValueError("At least two clients needed")
    client_hosts = set()
    server_hosts = set()
    for node in nodes:
        if not isinstance(node, dict) or node.get("role") not in {"client", "server"}:
            raise ValueError("Invalid benchmark node")
        identifier = node.get("physical_host_id")
        if not isinstance(identifier, str) or not identifier.strip() or len(identifier) > 128:
            raise ValueError("Explicit physical host attestation required")
        if node["role"] == "client":
            client_hosts.add(identifier)
        else:
            server_hosts.add(identifier)
    if len(client_hosts) < 2 or not server_hosts or server_hosts.intersection(client_hosts):
        raise ValueError("Distributed topology requires distinct physical client and server machines")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--clients", type=int, choices=SCALE_LEVELS, default=2)
    parser.add_argument("--mode", choices=("shared-runner", "validate-distributed"), default="shared-runner")
    parser.add_argument("--nodes", type=Path, help="JSON node evidence for validate-distributed")
    args = parser.parse_args()
    if args.mode == "validate-distributed":
        if args.nodes is None:
            parser.error("--nodes required")
        validate_distributed_nodes(json.loads(args.nodes.read_text()))
        print("Topology accepted: physical client and server machines are distinct")
        return
    result = run_shared_runner(args.output, clients=args.clients)
    if not result["all_passed"]:
        raise SystemExit("Hybrid CI 2-client integration failed; check client logs")


if __name__ == "__main__":
    main()
