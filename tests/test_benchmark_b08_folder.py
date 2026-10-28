"""B08 folder inventory regression tests; no FFmpeg or large inputs."""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "experiments/media_optimization/benchmark_b08_folder.py"
spec = importlib.util.spec_from_file_location("montara_b08", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_inventory_counts_without_copying(tmp_path):
    (tmp_path / "cam1.mp4").write_bytes(b"1" * 12)
    (tmp_path / "voice.wav").write_bytes(b"2" * 5)
    (tmp_path / "notes.txt").write_text("ignore")
    result = mod.inventory(tmp_path)
    assert result["counts"] == {"video": 1, "audio": 1}
    assert result["total_source_bytes"] == 17
    assert result["copies_created"] == 0
    assert result["ignored_entries"] == 1


def test_inventory_does_not_follow_symlinks(tmp_path):
    root = tmp_path / "chosen"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.mp4").write_bytes(b"x" * 1234)
    (root / "linked").symlink_to(outside, target_is_directory=True)
    (root / "secret.mp4").symlink_to(outside / "secret.mp4")
    result = mod.inventory(root)
    assert result["total_source_bytes"] == 0


def test_inventory_enforces_file_limit(tmp_path):
    for i in range(3):
        (tmp_path / f"cam{i}.mp4").write_bytes(b"x")
    with pytest.raises(ValueError, match="file count"):
        mod.inventory(tmp_path, max_files=2)
