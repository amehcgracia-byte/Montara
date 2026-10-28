"""No FFmpeg needed: exercise the private upload/proxy integration seam."""
import json
import uuid
import pytest
from uploaded_session_bridge import resolve_completed_upload, prepare_uploaded_videos


def upload(tmp_path, *, name="camera.mp4", complete=True, data=b"abc"):
    identity=uuid.uuid4().hex
    folder=tmp_path/"Uploads"/identity
    folder.mkdir(parents=True)
    (folder/name).write_bytes(data)
    (folder/"upload.json").write_text(json.dumps({"name":name,"complete":complete,"size":len(data)}))
    return identity, folder


def test_completed_video_resolves(tmp_path):
    identity, folder=upload(tmp_path)
    assert resolve_completed_upload(tmp_path,identity)==folder/"camera.mp4"


def test_unfinished_upload_rejected(tmp_path):
    identity,_=upload(tmp_path,complete=False)
    with pytest.raises(ValueError,match="not complete"):
        resolve_completed_upload(tmp_path,identity)


def test_traversal_and_wrong_extension_rejected(tmp_path):
    identity,folder=upload(tmp_path)
    meta=json.loads((folder/"upload.json").read_text())
    meta["name"]="../camera.mp4"
    (folder/"upload.json").write_text(json.dumps(meta))
    with pytest.raises(ValueError,match="supported video"):
        resolve_completed_upload(tmp_path,identity)
    identity,_=upload(tmp_path,name="audio.wav")
    with pytest.raises(ValueError,match="supported video"):
        resolve_completed_upload(tmp_path,identity)


def test_symlink_rejected(tmp_path):
    identity,folder=upload(tmp_path)
    (folder/"camera.mp4").unlink()
    destination=tmp_path/"elsewhere.mp4"; destination.write_bytes(b"abc")
    (folder/"camera.mp4").symlink_to(destination)
    with pytest.raises(ValueError,match="unavailable"):
        resolve_completed_upload(tmp_path,identity)


def test_proxy_bridge_receives_private_paths_and_returns_public_data(tmp_path, monkeypatch):
    one,_=upload(tmp_path,name="one.mp4")
    two,_=upload(tmp_path,name="two.mp4")
    captured={}
    def fake(sources,cache_dir,*,sphere):
        captured.update(sources=sources,cache=cache_dir,sphere=sphere)
        return {"version":1,"sources":[{"source_id":"opaque"} for _ in sources]}
    monkeypatch.setattr("uploaded_session_bridge.prepare_session",fake)
    result=prepare_uploaded_videos(tmp_path,[one,two],sphere=True)
    assert len(captured["sources"])==2 and captured["sphere"]
    assert result=={"version":1,"sources":[{"source_id":"opaque"},{"source_id":"opaque"}]}
    assert "original" not in json.dumps(result)


def test_duplicate_ids_and_mismatched_file_rejected(tmp_path):
    identity,folder=upload(tmp_path)
    with pytest.raises(ValueError,match="Duplicate"):
        prepare_uploaded_videos(tmp_path,[identity,identity])
    (folder/"camera.mp4").write_bytes(b"longer")
    with pytest.raises(ValueError,match="size mismatch"):
        resolve_completed_upload(tmp_path,identity)
