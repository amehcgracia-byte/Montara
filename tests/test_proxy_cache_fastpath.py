"""Regression: cached Montara proxies skip probing but reject stale manifests."""
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from local_media import proxies


def seed(tmp_path):
    src = tmp_path / "camera.mp4"
    src.write_bytes(b"synthetic placeholder")
    fp = proxies.stamp(src)
    import hashlib
    key = hashlib.sha256(json.dumps([str(src.resolve()), fp, False, "proxy019"]).encode()).hexdigest()[:24]
    cache = tmp_path / "cache"
    cache.mkdir()
    proxy = cache / (key + ".mp4")
    proxy.write_bytes(b"cached-mp4-placeholder")
    record = {
        "source_id": key,
        "original": str(src.resolve()),
        "original_stamp": fp,
        "proxy": str(proxy),
        "public": {"projection": "flat", "duration": 1.0},
    }
    manifest = cache / (key + ".local.json")
    manifest.write_text(json.dumps(record))
    return src, cache, proxy, manifest, record


def test_warm_cache_avoids_ffprobe(tmp_path):
    src, cache, _, _, expected = seed(tmp_path)
    with patch.object(proxies, "probe", side_effect=AssertionError("unexpected ffprobe")):
        assert proxies.prepare(src, cache) == expected


def test_changed_original_is_not_a_cache_hit(tmp_path):
    src, cache, _, _, _ = seed(tmp_path)
    current = src.stat()
    os.utime(src, ns=(current.st_atime_ns, current.st_mtime_ns + 1_000_000))
    with patch.object(proxies, "probe", side_effect=RuntimeError("cache miss")):
        with pytest.raises(RuntimeError, match="cache miss"):
            proxies.prepare(src, cache)


def test_missing_or_empty_proxy_is_not_a_cache_hit(tmp_path):
    src, cache, proxy, _, _ = seed(tmp_path)
    for action in ("empty", "missing"):
        if action == "empty":
            proxy.write_bytes(b"")
        else:
            proxy.unlink()
        with patch.object(proxies, "probe", side_effect=RuntimeError("cache miss")):
            with pytest.raises(RuntimeError, match="cache miss"):
                proxies.prepare(src, cache)


def test_corrupt_or_mismatched_manifest_is_not_a_cache_hit(tmp_path):
    src, cache, _, manifest, record = seed(tmp_path)
    for payload in ("{", json.dumps({**record, "original": "/unexpected/source"})):
        manifest.write_text(payload)
        with patch.object(proxies, "probe", side_effect=RuntimeError("cache miss")):
            with pytest.raises(RuntimeError, match="cache miss"):
                proxies.prepare(src, cache)
