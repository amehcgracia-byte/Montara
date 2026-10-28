"""Lightweight integrity checks for a persisted proxy fingerprint."""
from local_media.proxies import proxy_signature


def test_signature_detects_truncation_and_tail_change(tmp_path):
    target = tmp_path / "proxy.mp4"
    target.write_bytes(b"A" * 200000)
    saved = proxy_signature(target)
    target.write_bytes(b"A" * 199999)
    assert proxy_signature(target) != saved
    target.write_bytes(b"A" * 200000)
    with target.open("r+b") as stream:
        stream.seek(-4, 2)
        stream.write(b"CHNG")
    assert proxy_signature(target) != saved


def test_signature_detects_header_change(tmp_path):
    target = tmp_path / "proxy.mp4"
    target.write_bytes(b"A" * 200000)
    saved = proxy_signature(target)
    with target.open("r+b") as stream:
        stream.write(b"CHNG")
    assert proxy_signature(target) != saved


def test_signature_is_repeatable(tmp_path):
    target = tmp_path / "proxy.mp4"
    target.write_bytes(b"MP4" * 100000)
    assert proxy_signature(target) == proxy_signature(target)
