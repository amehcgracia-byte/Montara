"""Truth-in-benchmark contracts for hybrid web/server/local Companion testing."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from urano_hybrid_benchmark import SCALE_LEVELS, _safe_scratch, _summarize, validate_distributed_nodes


class HybridBenchmarkContract(unittest.TestCase):
    def test_scale_levels_are_not_server_only_claims(self):
        self.assertEqual(SCALE_LEVELS, (2, 4, 8, 10, 25))

    def test_shared_runner_never_misreported_as_distributed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            client = root / "client-01"
            client.mkdir()
            (client / "render.mp4").write_bytes(b"f" * 128)
            (client / "summary.json").write_text(json.dumps({
                "native_render": True, "server_export_skipped": True,
                "original_sources": 2,
            }))
            result = _summarize(root, {"client-01": SimpleNamespace(returncode=0)},
                                {"client-01": __import__("time").monotonic()},
                                {"client-01": {"peak_rss_bytes": 1024,
                                                "cpu_seconds_observed": 3}})
            self.assertTrue(result["all_passed"])
            self.assertFalse(result["distributed_result"])
            self.assertFalse(result["server_remote"])
            self.assertTrue(result["shared_physical_cpu"])
            self.assertIsNone(result["network_bytes_to_server"])
            self.assertTrue(result["clients"][0]["companion_local_original_render"])

    def test_missing_mp4_fails_even_with_successful_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            client = root / "client-01"
            client.mkdir()
            (client / "summary.json").write_text(json.dumps({
                "native_render": True, "server_export_skipped": True,
            }))
            result = _summarize(root, {"client-01": SimpleNamespace(returncode=0)},
                                {"client-01": __import__("time").monotonic()},
                                {"client-01": {"peak_rss_bytes": 0,
                                                "cpu_seconds_observed": 0}})
            self.assertFalse(result["all_passed"])

    def test_distributed_requires_distinct_physical_hosts(self):
        correct = [{"role": "client", "physical_host_id": "mac-a"},
                   {"role": "client", "physical_host_id": "pc-b"},
                   {"role": "server", "physical_host_id": "gcp-1"}]
        self.assertTrue(validate_distributed_nodes(correct))
        for invalid in (
            correct[:2],
            [{"role": "client", "physical_host_id": "same"},
             {"role": "client", "physical_host_id": "same"},
             {"role": "server", "physical_host_id": "gcp-1"}],
            [{"role": "client", "physical_host_id": "mac-a"},
             {"role": "client", "physical_host_id": "pc-b"},
             {"role": "server", "physical_host_id": "pc-b"}],
        ):
            with self.assertRaises(ValueError):
                validate_distributed_nodes(invalid)

    def test_scratch_cannot_overwrite_existing_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "experiment"
            destination.mkdir()
            (destination / "valuable.txt").write_text("preserve")
            with self.assertRaises(ValueError):
                _safe_scratch(destination)
            self.assertEqual((destination / "valuable.txt").read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()
