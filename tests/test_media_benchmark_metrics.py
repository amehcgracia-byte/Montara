"""Benchmark metric accounting: lightweight, no media dependency."""
import importlib.util
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "experiments" / "media_optimization" / "benchmark.py"
spec = importlib.util.spec_from_file_location("montara_media_benchmark", SOURCE)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


def test_matching_changes():
    result = bench.matches([2.0, 4.02, 6.0], [2.0, 4.0, 6.0])
    assert result["hits"] == 3
    assert result["precision"] == result["recall"] == 1.0


def test_false_positive_and_missed_change():
    result = bench.matches([2.0, 2.7, 6.0], [2.0, 4.0, 6.0])
    assert result["hits"] == 2
    assert result["precision"] == result["recall"] == .667


def test_empty_predictions():
    result = bench.matches([], [2.0])
    assert result["recall"] == result["precision"] == 0
