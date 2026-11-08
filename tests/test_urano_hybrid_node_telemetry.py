"""U17B: passive local/server telemetry and strict no-false-benchmark reporting."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from urano_hybrid_node_meter import build_report, sample_process_tree, save_report
from urano_hybrid_merge_reports import combine_reports


def fake_node(name, role, *, run_id="trial-one", level=2, cpu=10.0):
    result = {
        "method": "psutil-pid-tree-sampled",
        "observation_seconds": 2.5,
        "samples": 5,
        "cpu_seconds_observed_lower_bound": cpu,
        "rss_bytes_sampled_peak": 1200000,
        "root_exited_during_observation": False,
    }
    return build_report(run_id=run_id, physical_host_label=name,
                        role=role, scenario_clients=level, results=result)


class HybridMeterContracts(unittest.TestCase):
    def test_actual_process_tree_observed_and_does_not_execute_actions(self):
        report = sample_process_tree(os.getpid(), duration=0.25, interval=0.1)
        self.assertGreaterEqual(report["samples"], 2)
        self.assertGreater(report["rss_bytes_sampled_peak"], 0)
        self.assertGreaterEqual(report["cpu_seconds_observed_lower_bound"], 0)
        self.assertGreater(report["observation_seconds"], 0)
        self.assertLess(report["observation_seconds"], 2)

    def test_meter_refuses_bad_roles_labels_and_user_data(self):
        sample = sample_process_tree(os.getpid(), duration=0.11, interval=0.1)
        with self.assertRaises(ValueError):
            build_report(run_id="trial", physical_host_label="my mac /Users/alice/private",
                         role="client_companion", results=sample)
        with self.assertRaises(ValueError):
            build_report(run_id="trial", physical_host_label="client-a",
                         role="not a role", results=sample)
        with self.assertRaises(ValueError):
            build_report(run_id="trial", physical_host_label="client-a",
                         role="server", results=sample, scenario_clients=3)

    def test_report_contains_no_paths_command_lines_or_original_media(self):
        report = fake_node("mac-a", "client_companion")
        s = json.dumps(report)
        self.assertNotIn("cmdline", s)
        self.assertNotIn("file_path", s)
        self.assertNotIn("original_file", s)
        self.assertIsNone(report["transport"]["original_upload_bytes"])
        self.assertFalse(report["remote_server_verified"])

    def test_safe_exclusive_output_cannot_overwrite_previous_run(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "meter.json"
            report = fake_node("mac-a", "client_companion")
            save_report(path, report)
            with self.assertRaises(FileExistsError):
                save_report(path, report)
            self.assertEqual(json.loads(path.read_text())["host_label"], "mac-a")
            symlink = Path(d) / "link"
            symlink.symlink_to(path)
            with self.assertRaises(ValueError):
                save_report(symlink, report)

    def test_two_clients_one_remote_server_combine_but_never_claim_pass(self):
        reports = [
            fake_node("mac-a", "client_companion"),
            fake_node("win-b", "client_companion"),
            fake_node("gcp-c", "server"),
            fake_node("mac-a", "client_browser"),
        ]
        merged = combine_reports(reports, verified_hosts=True)
        self.assertTrue(merged["self_declared_topology_consistent"])
        self.assertTrue(merged["operator_physically_confirmed_distinct_hosts"])
        self.assertFalse(merged["physical_machine_distinctness_cryptographically_attested"])
        self.assertFalse(merged["distributed_performance_verified"])
        self.assertIsNone(merged["all_clients_completed_export"])
        self.assertIsNone(merged["network_bytes_to_server"])
        self.assertEqual(len(merged["meters"]), 4)

    def test_reject_duplicate_hosts_missing_server_mismatched_run(self):
        a = fake_node("mac-a", "client_companion")
        b = fake_node("win-b", "client_companion")
        s = fake_node("gcp-c", "server")
        for bad in (
            [a,b],
            [a,a,s],
            [a, fake_node("mac-a", "client_companion"),s],
            [a,b,fake_node("win-b", "server")],
            [a,b,fake_node("gcp-c", "server",run_id="different")],
            [a,b,fake_node("gcp-c", "server",level=4)],
        ):
            with self.subTest(bad=len(bad)):
                with self.assertRaises(ValueError):
                    combine_reports(bad)

    def test_reject_invented_cpu_missing_samples_and_stale_schema(self):
        original = [
            fake_node("mac-a", "client_companion"),
            fake_node("win-b", "client_companion"),
            fake_node("gcp-c", "server"),
        ]
        for edit in (
            lambda x: x["sample"].update(cpu_seconds_observed_lower_bound=-2),
            lambda x: x["sample"].update(cpu_seconds_observed_lower_bound=float("nan")),
            lambda x: x["sample"].update(samples=0),
            lambda x: x.update(schema="old-schema"),
            lambda x: x.update(no_media_or_secrets_collected=False),
        ):
            reports = json.loads(json.dumps(original))
            edit(reports[0])
            with self.assertRaises(ValueError):
                combine_reports(reports)


if __name__ == "__main__":
    unittest.main()
