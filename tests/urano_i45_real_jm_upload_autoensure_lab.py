"""I45 physical lab: original JM uploaded video triggers trusted Owner ensure.

Full original Chema Flask application + immutable real Engine + actual FFmpeg
synthetic MP4 + native JM /wizard/upload + first Stage draft adapter.

An injected ensure callback STANDS IN for the already-tested I27 broker:
this proves exact hook timing and media compatibility, NOT production systemd,
Google OAuth browser or actual Windows Companion. No live service changed.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from werkzeug.test import Client
from werkzeug.wrappers import Response


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--execute", action="store_true")
    a = p.parse_args()
    if not a.execute:
        p.error("Requires explicit --execute")
    bundle = a.bundle.resolve(strict=True)
    if (bundle.parent != Path("/opt/montara/bundles")
            or len(bundle.name) != 47
            or not bundle.name.startswith("engine-")
            or any(c not in "0123456789abcdef" for c in bundle.name[7:])):
        p.error("Invalid pinned Engine")
    checkout = Path(__file__).resolve().parents[1]
    if not (checkout / "app.py").is_file():
        p.error("Requires complete original Chema product checkout")
    sys.path[:0] = [str(checkout), str(bundle / "site"),
                    str(bundle / "app"), str(bundle / "engine")]
    from app import create_montara_app
    from core.project import new_project_document
    from urano.first_valid_upload_gate import FirstValidUploadEngineGate
    from urano.owner_first_stage_wizard import OwnerFirstStageWizard

    with tempfile.TemporaryDirectory(prefix="montara-i45-first-upload-") as tmp:
        root = Path(tmp)
        data_root = root / "worker"
        folder = data_root / "Projects" / "7b8f5fd6-02b4-4cd0-8d16-c2d6d606a505"
        folder.mkdir(parents=True)
        (folder / "project.json").write_text(
            json.dumps(new_project_document(folder.name)), encoding="utf-8")
        video = root / "synthetic-source.mp4"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=12:duration=2",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(video),
        ], check=True, stderr=subprocess.PIPE, timeout=45)
        app = create_montara_app(data_root, samples=False)
        opened = app.test_client().post("/api/v1/wizard/projects/open",
                                        json={"path": str(folder)})
        if opened.status_code != 200:
            raise RuntimeError("Original pinned JM Engine refused Owner folder")
        triggered = []

        def ensure():
            triggered.append("ensure")
            return {"ok": True, "state": "ready", "generation": 1}

        wsgi = FirstValidUploadEngineGate(
            OwnerFirstStageWizard(app, owner_project_folder=folder),
            ensure_private_worker=ensure,
        )
        client = Client(wsgi, Response)
        if client.get("/").status_code != 200 or triggered:
            raise RuntimeError("Browsing starts Engine unnecessarily")
        if client.get("/montara/uploads").status_code != 200 or triggered:
            raise RuntimeError("Upload limits started Engine unnecessarily")
        uploaded = client.post(
            "/api/v1/wizard/upload", data=video.read_bytes(),
            content_type="application/octet-stream",
            headers={"X-Zucker-Filename": "synthetic-source.mp4"})
        if uploaded.status_code != 200 or triggered != ["ensure"]:
            raise RuntimeError("Original JM upload was not correctly admitted: "+
                               str([uploaded.status_code, triggered,
                                    uploaded.get_data(as_text=True)[:150]]))
        found = (uploaded.get_json().get("videos") or [])
        if len(found) != 1 or not found[0].get("path"):
            raise RuntimeError("Original JM uploader did not classify proxy")
        private_path = found[0]["path"]
        if not Path(private_path).is_relative_to(data_root / "WizardUploads"):
            raise RuntimeError("Video bytes escaped private worker Inbox")
        start = client.post("/api/v1/wizard/projects/new", json={})
        draft = client.post("/api/v1/wizard/draft", json={
            "name": "Stage first media", "platform": "youtube",
            "project_id": None, "master": "", "audio_paths": [],
            "videos": [private_path],
        })
        if (start.status_code != 200 or draft.status_code != 200
                or draft.get_json().get("project_id") != str(folder)):
            raise RuntimeError("Original JM draft lost Owner project")
        if triggered != ["ensure"]:
            raise RuntimeError("Unexpected extra Engine activation")
        print(json.dumps({
            "original_jm_application": True,
            "actual_ffmpeg_video_uploaded": True,
            "first_real_upload_triggered_private_ensure": True,
            "browse_before_upload_no_engine_trigger": True,
            "original_jm_upload_success": True,
            "first_stage_draft_same_owner_uuid": True,
            "original_media_uploaded": False,
            "broker_ensure_callback_stubbed": True,
            "cloud_beta_deployed": False,
            "companion_windows_verified": False,
        }, sort_keys=True))


if __name__ == "__main__":
    main()
