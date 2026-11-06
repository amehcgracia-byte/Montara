"""U13E1: real media ingest inside one Docker Engine, no host upload or web UI.

This is a narrow integration gate using synthetic video/audio and the actual
Engine Flask endpoints. NOT an export or Companion benchmark.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path


def ffmpeg(*arguments: str) -> None:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        *arguments], capture_output=True, text=True, timeout=100)
    if r.returncode:
        raise AssertionError("Synthetic FFmpeg media generation failed: " + r.stderr[-800:])


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python /app/tests/urano_engine_ingest_in_container.py /workspace")
    root = Path(sys.argv[1]).resolve()
    if root != Path("/workspace") or not (root / "Projects").is_dir():
        raise AssertionError("Isolated test workspace required")
    project_dir = root / "Projects" / "MediaIngest"
    project_dir.mkdir()
    media = project_dir / "inputs"
    media.mkdir(exist_ok=True)
    master = media / "master.wav"
    camera = media / "camera-a.mp4"

    # Reuse the established media pattern from tests/e2e_journey.py:
    # a deterministic noise master and a camera carrying that same soundtrack.
    ffmpeg("-f", "lavfi", "-i", "anoisesrc=color=pink:seed=1234:amplitude=.2:duration=20",
           "-ar", "48000", str(master))
    ffmpeg("-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24:duration=20",
           "-i", str(master), "-c:v", "libx264", "-preset", "ultrafast",
           "-threads", "2", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-shortest", str(camera))
    from core.project import new_project_document
    (project_dir / "project.json").write_text(
        json.dumps(new_project_document("URANO synthetic ingest")))
    from server.api import create_app
    client = create_app(project_path=str(project_dir), dev=False).test_client()
    reg_video = client.post("/api/v1/inputs/videos", json={"paths": [str(camera)]})
    reg_master = client.post("/api/v1/inputs/master", json={"master": str(master)})
    assert reg_video.status_code == 200, ("Video registration", reg_video.status_code, reg_video.get_json())
    assert reg_master.status_code == 200, ("Master registration", reg_master.status_code, reg_master.get_json())
    submitted = client.post("/api/v1/stages/ingest/run")
    assert submitted.status_code == 202, ("Ingest submission", submitted.status_code, submitted.get_json())

    deadline = time.monotonic() + 180
    seen = []
    while time.monotonic() < deadline:
        snapshot = client.get("/api/v1/project").get_json()
        status = snapshot.get("stages", {}).get("ingest", {}).get("status")
        if not seen or seen[-1] != status:
            seen.append(status)
        if status == "done":
            break
        if status in ("failed", "blocked"):
            raise AssertionError("Real Engine ingest rejected synthetic media: " +
                                 repr(snapshot["stages"]["ingest"].get("error")))
        time.sleep(.25)
    else:
        raise AssertionError("Real Engine ingest timed out: " + repr(seen))
    state = snapshot["stages"]["ingest"]
    assert state.get("outputs"), "Engine marked ingest done without any outputs"
    for path in state["outputs"].values():
        assert Path(path).is_file(), "Ingest output not found inside isolated workspace"
        assert Path(path).resolve().is_relative_to(project_dir.resolve()), "Output escaped project workspace"
    assert camera.stat().st_size > 1000 and master.stat().st_size > 1000
    print(json.dumps({"passed": True, "engine_stage": "ingest",
                      "media_sources": 2, "stage_states": seen,
                      "output_count": len(state["outputs"]), "export_tested": False,
                      "companion_tested": False}))


if __name__ == "__main__":
    main()
