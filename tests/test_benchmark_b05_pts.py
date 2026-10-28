"""PTS alignment contract with a real FFmpeg-generated media fixture."""
import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "experiments/media_optimization/benchmark_b05_pts.py"
spec = importlib.util.spec_from_file_location("montara_b05", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


@pytest.mark.parametrize("case,expected_offset,expected_frames", [
    ("cfr", 0.0, 120), ("vfr", 0.0, 90), ("shifted", 3.0, 120)
])
def test_proxy_pts_offset_must_be_explicit(tmp_path, case, expected_offset, expected_frames):
    result = mod.measure(tmp_path, case)
    assert result["frames"] == expected_frames
    assert result["origin_offset_s"] == pytest.approx(expected_offset, abs=0.002)
    assert result["max_error_after_origin_mapping_s"] < 0.002
