"""Small smoke checks for the real FFmpeg B02 experiment."""
import importlib.util
import shutil
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "experiments/media_optimization/benchmark_b02.py"
spec = importlib.util.spec_from_file_location("montara_b02", SCRIPT)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg not installed")
def test_b02_creates_reusable_proxy(tmp_path):
    report = bench.benchmark(tmp_path)
    assert report["source_bytes"] > 0
    assert report["proxy_bytes"] > 0
    assert report["proxy_bytes"] < report["source_bytes"]
    assert len(report["individual_seek_times_s"]) == len(bench.TIMES)
    assert report["source_sparse_pass_s"] >= 0
    assert report["proxy_subsequent_pass_s"] >= 0
