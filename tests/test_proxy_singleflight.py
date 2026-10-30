"""Single-flight: the same source requested twice must transcode only once."""
import concurrent.futures
import os
import subprocess
import threading
from unittest.mock import patch

import pytest

from local_media import proxies


@pytest.mark.skipif(os.name != "posix", reason="Current implementation uses fcntl")
def test_two_threads_generate_only_one_proxy(tmp_path):
    source = tmp_path / "camera.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc2=size=320x180:rate=15:duration=1",
                    "-c:v", "libx264", "-preset", "ultrafast", str(source)],
                   check=True)
    cache = tmp_path / "cache"
    real_run = proxies.subprocess.run
    n_transcodes = 0
    counter_lock = threading.Lock()

    def spy(argv, *args, **kwargs):
        nonlocal n_transcodes
        if argv and argv[0] == "ffmpeg":
            with counter_lock:
                n_transcodes += 1
        return real_run(argv, *args, **kwargs)

    with patch.object(proxies.subprocess, "run", side_effect=spy):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(proxies.prepare, source, cache) for _ in range(2)]
            records = [f.result(timeout=60) for f in futures]
    assert records[0]["source_id"] == records[1]["source_id"]
    assert n_transcodes == 1, "The same source was transcoded more than once"
    assert records[0]["proxy_signature"] == records[1]["proxy_signature"]


@pytest.mark.skipif(os.name != "posix", reason="Current implementation uses fcntl")
def test_warm_hit_does_not_acquire_lock(tmp_path):
    from test_proxy_cache_fastpath import seed
    src, cache, _, _, expected = seed(tmp_path)
    with patch.object(proxies, "_source_lock", side_effect=AssertionError("Unexpected lock")):
        assert proxies.prepare(src, cache) == expected


def test_non_posix_cold_generation_remains_available(tmp_path):
    from types import SimpleNamespace
    source = tmp_path / "camera.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc2=size=320x180:rate=15:duration=1",
                    "-c:v", "libx264", "-preset", "ultrafast", str(source)], check=True)
    # Simulate only the platform selection, not a Windows runtime certification.
    with patch.object(proxies, "os", SimpleNamespace(name="nt")):
        result = proxies.prepare(source, tmp_path / "cache")
    assert result["public"]["duration"] == pytest.approx(1, abs=.1)
