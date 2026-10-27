"""Known limitations from the Mars proxy experiments.

xfail cases are documented, reproducible defects; they must become passing
tests when the implementation is repaired. Real FFmpeg is required.
"""
import concurrent.futures
import json
import subprocess

import pytest

from local_media.proxies import prepare


def sample(path):
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24:duration=3",
        "-c:v", "libx264", "-preset", "ultrafast", str(path),
    ], check=True)


@pytest.mark.xfail(strict=False, reason="Timing-dependent concurrent writes share .pending.mp4")
def test_concurrent_prepare_same_source(tmp_path):
    source = tmp_path / "input.mp4"
    sample(source)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(prepare, source, tmp_path / "cache") for _ in range(2)]
        results = [j.result() for j in jobs]
    assert results[0]["source_id"] == results[1]["source_id"]


@pytest.mark.xfail(strict=True, reason="Warm-cache check verifies only nonempty proxy existence")
def test_corrupt_proxy_not_reused(tmp_path):
    source = tmp_path / "input.mp4"
    sample(source)
    record = prepare(source, tmp_path / "cache")
    from pathlib import Path
    Path(record["proxy"]).write_bytes(b"x" * 128)
    with pytest.raises((ValueError, RuntimeError, subprocess.CalledProcessError)):
        prepare(source, tmp_path / "cache")


def test_vfr_proxy_duration_smoke(tmp_path):
    source = tmp_path / "variable.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=15:duration=2",
        "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=2",
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
        "-map", "[v]", "-fps_mode", "vfr", "-c:v", "libx264",
        "-preset", "ultrafast", str(source),
    ], check=True)
    record = prepare(source, tmp_path / "cache")
    assert abs(record["public"]["duration"] - record["public"]["proxy_duration"]) < .12
