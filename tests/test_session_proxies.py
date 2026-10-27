"""Session proxy bridge never exposes original file paths in public metadata."""
from unittest.mock import patch
import pytest
from local_media.session_proxies import prepare_session


def test_session_reuses_public_proxy_records_without_paths(tmp_path):
    one, two = tmp_path / "cam1.mp4", tmp_path / "cam2.mp4"
    one.write_bytes(b"first")
    two.write_bytes(b"second")
    seen = []

    def fake_prepare(path, cache, sphere=False):
        seen.append(path)
        return {"original": str(path), "public": {"source_id": str(len(seen)), "width": 640}}

    with patch("local_media.session_proxies.prepare", side_effect=fake_prepare):
        result = prepare_session([one, two], tmp_path / "cache")
    assert len(result["sources"]) == 2
    assert [p.name for p in seen] == ["cam1.mp4", "cam2.mp4"]
    assert "original" not in str(result)


def test_session_rejects_duplicate_source(tmp_path):
    path = tmp_path / "same.mp4"
    path.write_bytes(b"test")
    with patch("local_media.session_proxies.prepare", return_value={"public": {"source_id": "one"}}):
        with pytest.raises(ValueError, match="Duplicate"):
            prepare_session([path, path], tmp_path / "cache")
