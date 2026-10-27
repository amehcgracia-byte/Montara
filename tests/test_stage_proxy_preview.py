"""Stage opt-in proxy preparation routes are local-only and never change source records."""
import time
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from local_media.preview_http import register_local_proxy_preview


def make_client(tmp_path):
    root = tmp_path / "MontaraData"
    root.mkdir()
    media = root / "Uploads" / "camera.mp4"
    media.parent.mkdir()
    media.write_bytes(b"camera")
    app = Flask(__name__)
    app.testing = True
    register_local_proxy_preview(app, root)
    return app.test_client(), media


def test_stage_proxy_preparation_is_opt_in_and_async(tmp_path):
    client, media = make_client(tmp_path)
    assert client.get("/montara/local-preview/availability").json == {"enabled": True}
    with patch("local_media.proxies.prepare", return_value={"source_id": "a" * 24}):
        response = client.post("/montara/local-preview/prepare", json={"path": str(media)})
        assert response.status_code == 202
        job_id = response.json["id"]
        for _ in range(100):
            result = client.get(f"/montara/local-preview/job/{job_id}")
            if result.json["status"] != "preparing":
                break
            time.sleep(.01)
        assert result.json == {"status": "ready", "source_id": "a" * 24}


def test_stage_proxy_rejects_unregistered_paths_and_nonlocal_clients(tmp_path):
    client, media = make_client(tmp_path)
    outside = tmp_path / "secret.mp4"
    outside.write_bytes(b"secret")
    assert client.post("/montara/local-preview/prepare", json={"path": str(outside)}).status_code == 400
    assert client.post("/montara/local-preview/prepare", json={"path": str(media)},
                       environ_overrides={"REMOTE_ADDR": "198.51.100.10"}).status_code == 403
    assert client.get("/montara/local-preview/availability",
                      environ_overrides={"REMOTE_ADDR": "198.51.100.10"}).status_code == 403
