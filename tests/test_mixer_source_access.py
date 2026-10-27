"""Remote Mixer source boundaries: isolated unit regressions, no media needed."""
import json
from pathlib import Path

import pytest

from mixer_adapter.source_access import resolve_mix_sources


def _registered(tmp_path, name="bass.wav", complete=True):
    work = tmp_path / "Uploads" / ("a" * 32)
    work.mkdir(parents=True)
    (work / name).write_bytes(b"test")
    (work / "upload.json").write_text(json.dumps({"name": name, "complete": complete}))
    return work / name


def _resolve(paths, tmp_path, remote=True):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir(exist_ok=True)
    return resolve_mix_sources(paths, tmp_path, fixtures, remote=remote)


def test_remote_registered_complete_upload_is_allowed(tmp_path):
    source = _registered(tmp_path)
    assert _resolve([str(source)], tmp_path) == [source.resolve()]


def test_remote_unregistered_private_file_is_rejected(tmp_path):
    private = tmp_path / "private.wav"
    private.write_bytes(b"private")
    with pytest.raises(ValueError, match="registered"):
        _resolve([str(private)], tmp_path)


def test_local_development_path_remains_supported(tmp_path):
    private = tmp_path / "my-music.wav"
    private.write_bytes(b"music")
    assert _resolve([str(private)], tmp_path, remote=False) == [private.resolve()]


def test_remote_unfinished_upload_is_rejected(tmp_path):
    source = _registered(tmp_path, complete=False)
    with pytest.raises(ValueError, match="completed"):
        _resolve([str(source)], tmp_path)


def test_remote_modified_upload_record_is_rejected(tmp_path):
    source = _registered(tmp_path)
    (source.parent / "upload.json").write_text(json.dumps({"name": "other.wav", "complete": True}))
    with pytest.raises(ValueError, match="record"):
        _resolve([str(source)], tmp_path)


def test_remote_symlink_escape_is_rejected(tmp_path):
    private = tmp_path / "secret.wav"
    private.write_bytes(b"secret")
    folder = tmp_path / "Uploads" / ("a" * 32)
    folder.mkdir(parents=True)
    shortcut = folder / "bass.wav"
    shortcut.symlink_to(private)
    (folder / "upload.json").write_text(json.dumps({"name": "bass.wav", "complete": True}))
    with pytest.raises(ValueError, match="registered"):
        _resolve([str(shortcut)], tmp_path)


def test_duplicate_file_names_rejected_before_linking(tmp_path):
    first = tmp_path / "first" / "bass.wav"
    second = tmp_path / "second" / "bass.wav"
    for path in (first, second):
        path.parent.mkdir()
        path.write_bytes(b"test")
    with pytest.raises(ValueError, match="Duplicate"):
        _resolve([str(first), str(second)], tmp_path, remote=False)


def test_remote_bundled_fixture_is_accepted(tmp_path):
    source = tmp_path / "fixtures" / "example.wav"
    source.parent.mkdir()
    source.write_bytes(b"music")
    assert _resolve([str(source)], tmp_path) == [source.resolve()]


def test_invalid_track_payload_is_rejected(tmp_path):
    for payload in (None, [], ["missing.wav"], [4], [""]):
        with pytest.raises(ValueError):
            _resolve(payload, tmp_path)
