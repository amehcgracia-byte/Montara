"""Preview API only returns validated cached source IDs from the local host."""
import hashlib
import json
from pathlib import Path

from flask import Flask

from local_media.preview_http import register_local_proxy_preview
from local_media.proxies import proxy_signature, stamp


def setup(tmp_path):
    root = tmp_path / "workspace"
    cache = root / "LocalProxyCache"
    cache.mkdir(parents=True)
    source = tmp_path / "camera.mp4"
    source.write_bytes(b"original-source")
    source_id = "a" * 24
    proxy = cache / (source_id + ".mp4")
    proxy.write_bytes(b"fake-video-bytes")
    record = {
        "source_id": source_id,
        "original": str(source.resolve()),
        "original_stamp": stamp(source),
        "proxy": str(proxy),
        "proxy_signature": proxy_signature(proxy),
        "public": {"source_id": source_id, "duration": 3, "width": 640},
    }
    (cache / (source_id + ".local.json")).write_text(json.dumps(record))
    app = Flask(__name__)
    app.testing = True
    register_local_proxy_preview(app, root)
    return app, source, proxy, source_id


def test_preview_serves_only_registered_proxy(tmp_path):
    app, _, proxy, key = setup(tmp_path)
    client = app.test_client()
    metadata = client.get(f"/montara/local-preview/{key}/metadata")
    assert metadata.status_code == 200
    assert "original" not in metadata.json
    streamed = client.get(f"/montara/local-preview/{key}/video")
    assert streamed.status_code == 200
    assert streamed.data == proxy.read_bytes()
    assert streamed.headers["Cache-Control"] == "private, no-store"
    page = client.get(f"/montara/local-preview/{key}/view")
    assert page.status_code == 200
    assert f"/montara/local-preview/{key}/video" in page.get_data(as_text=True)
    assert client.get("/montara/local-preview/../../etc/passwd/video").status_code == 404


def test_preview_rejects_damaged_proxy_and_modified_original(tmp_path):
    app, source, proxy, key = setup(tmp_path)
    client = app.test_client()
    proxy.write_bytes(b"changed")
    assert client.get(f"/montara/local-preview/{key}/video").status_code == 404
    app, source, proxy, key = setup(tmp_path)
    source.write_bytes(b"changed source bytes")
    assert app.test_client().get(f"/montara/local-preview/{key}/metadata").status_code == 404


def test_preview_rejects_nonlocal_clients(tmp_path):
    app, _, _, key = setup(tmp_path)
    client = app.test_client()
    result = client.get(f"/montara/local-preview/{key}/video",
                        environ_overrides={"REMOTE_ADDR": "192.0.2.10"})
    assert result.status_code == 403
