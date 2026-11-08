"""Conservative offline reducer for opt-in hybrid benchmark node reports.

Reports are self-declared; no fabricated distributed/attested status. In a
future live trial, the operator must independently verify host placement,
time alignment and the exact Montara build/protocol.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from urano_hybrid_node_meter import _SCHEMA, _label

_SCALES = (2, 4, 8, 10, 25)
_ROLES = {"client_companion", "client_browser", "server"}


def _number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"Invalid nonnegative metric: {name}")
    return value


def combine_reports(reports: list[dict], *, verified_hosts: bool = False) -> dict:
    if not isinstance(reports, list) or len(reports) < 3:
        raise ValueError("Need at least two Companion reports and one server report")
    run_ids, levels = set(), set()
    unique_roles = set()
    client_hosts, server_hosts = set(), set()
    own_client_count = 0
    normalized = []
    for report in reports:
        if not isinstance(report, dict) or report.get("schema") != _SCHEMA:
            raise ValueError("Unexpected or stale meter schema")
        run_ids.add(_label(report.get("run_id")))
        host = _label(report.get("host_label"))
        role = report.get("role")
        if role not in _ROLES:
            raise ValueError("Invalid node role")
        key = (role, host)
        if key in unique_roles:
            raise ValueError("Duplicate role/host; reports could be counted twice")
        unique_roles.add(key)
        level = report.get("scenario_clients")
        if type(level) is not int or level not in _SCALES:
            raise ValueError("Invalid scale level")
        levels.add(level)
        sample = report.get("sample")
        if not isinstance(sample, dict) or sample.get("method") != "psutil-pid-tree-sampled":
            raise ValueError("Missing actual PID tree observation")
        if type(sample.get("samples")) is not int or sample["samples"] < 1:
            raise ValueError("Missing observations")
        _number(sample.get("observation_seconds"), "observation_seconds")
        _number(sample.get("cpu_seconds_observed_lower_bound"), "cpu_seconds")
        _number(sample.get("rss_bytes_sampled_peak"), "rss_bytes")
        if report.get("no_media_or_secrets_collected") is not True:
            raise ValueError("Privacy-safe recording is required")
        if role == "server":
            server_hosts.add(host)
        if role == "client_companion":
            own_client_count += 1
            client_hosts.add(host)
        normalized.append({
            "host_label": host,
            "role": role,
            "cpu_seconds_lower_bound": sample["cpu_seconds_observed_lower_bound"],
            "rss_bytes_sampled_peak": sample["rss_bytes_sampled_peak"],
            "observation_seconds": sample["observation_seconds"],
            "root_exited_during_observation": sample.get("root_exited_during_observation"),
        })
    if len(run_ids) != 1 or len(levels) != 1:
        raise ValueError("Reports must belong to the same run and scale level")
    level = next(iter(levels))
    if own_client_count != level:
        raise ValueError("Every planned client needs its own Companion report")
    if len(client_hosts) != level or len(server_hosts) != 1 or client_hosts.intersection(server_hosts):
        raise ValueError("Need distinct declared client hosts and one separate declared server")
    if len(normalized) != len(reports):
        raise ValueError("Invalid reporting cardinality")
    # A checkbox cannot cryptographically attest physical placement. Even
    # 'verified_hosts' denotes manual operator confirmation only.
    return {
        "schema": "urano-distributed-comparison-v1",
        "run_id": next(iter(run_ids)),
        "scenario_clients": level,
        "declared_client_hosts": len(client_hosts),
        "declared_server_hosts": len(server_hosts),
        "self_declared_topology_consistent": True,
        "physical_machine_distinctness_cryptographically_attested": False,
        "operator_physically_confirmed_distinct_hosts": bool(verified_hosts),
        "distributed_performance_verified": False,
        "all_clients_completed_export": None,
        "media_size_or_duration_comparable": None,
        "network_bytes_to_server": None,
        "p50_network_latency_ms": None,
        "processing_server_cost_estimate": None,
        "meters": sorted(normalized, key=lambda n: (n["role"], n["host_label"])),
        "interpretation": (
            "Passive node CPU/RSS only. Host labels are operator claims, not proof. "
            "No result claims distributed performance, completed MP4, WAN bytes, "
            "or rate scaling without independently verified end-to-end results."
        )
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, action="append", required=True,
                        help="Local JSON report; may be specified multiple times")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--operator-verified-physical-hosts", action="store_true")
    args = parser.parse_args()
    values = [json.loads(p.read_text(encoding="utf-8")) for p in args.input]
    aggregate = combine_reports(values, verified_hosts=args.operator_verified_physical_hosts)
    if args.output.is_symlink():
        raise ValueError("Refuse symlink output")
    with args.output.open("x", encoding="utf-8") as destination:
        json.dump(aggregate, destination, indent=2)
        destination.write("\n")
    print(json.dumps({"valid_declared_topology": True,
                      "distributed_performance_verified": False,
                      "network_measured": False}))


if __name__ == "__main__":
    main()
