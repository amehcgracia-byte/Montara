"""End-to-end check of Montara on a clean machine (Linux CI or a laptop).

Starts the real server, drives the real interface in Chromium and runs the real
engine: nothing is mocked. Produces screenshots and the exported videos.

    python tests/e2e_journey.py --output /tmp/montara-e2e [--mode stage|pulse]
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
MODES = {"stage": "youtube", "pulse": "reel"}


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def fixtures(folder: Path) -> Path:
    """Two synthetic cameras that both carry the master audio, so sync is real."""
    folder.mkdir(parents=True, exist_ok=True)
    master = folder / "master.wav"
    if not master.exists():
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             "anoisesrc=color=pink:seed=1234:amplitude=0.2:duration=20", "-ar", "48000", str(master)])
    for name, effect in [("camera-a.mp4", "null"), ("camera-b.mp4", "hue=h=90")]:
        if not (folder / name).exists():
            run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=20",
                 "-i", str(master), "-vf", effect, "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-shortest", str(folder / name)])
    return folder


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def journey(page, url: str, mode: str, media: Path, out: Path) -> dict:
    shots = out / mode
    shots.mkdir(parents=True, exist_ok=True)
    page.goto(url)
    page.screenshot(path=str(shots / "01-home.png"))
    page.locator("#newVideo").click()
    page.locator(f'.mode[data-platform="{MODES[mode]}"]').click()
    page.locator("#videoName").fill(f"E2E {mode}")
    page.locator("#fileInput").set_input_files([str(media / "camera-a.mp4"), str(media / "camera-b.mp4"), str(media / "master.wav")])
    page.wait_for_function("!document.querySelector('#makeIt').disabled", timeout=120_000)
    page.screenshot(path=str(shots / "02-footage.png"))
    page.locator("#makeIt").click()
    page.locator("#making").wait_for(state="visible")
    page.wait_for_timeout(4000)
    page.screenshot(path=str(shots / "03-making.png"))
    page.wait_for_selector("#result:not([hidden]), #failed:not([hidden])", timeout=900_000)
    if page.locator("#failed").is_visible():
        page.screenshot(path=str(shots / "99-failed.png"))
        return {"mode": mode, "passed": False, "error": page.locator("#errorText").inner_text()}
    page.wait_for_timeout(1500)
    page.screenshot(path=str(shots / "04-result.png"))
    with urlopen(url + "/api/v1/wizard/status", timeout=15) as response:
        status = json.load(response)
    path = Path(status["result"]["path"])
    probe = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
    run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"])  # decode the whole file
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    has_audio = any(s["codec_type"] == "audio" for s in probe["streams"])
    (shots / "render.mp4").write_bytes(path.read_bytes())
    return {"mode": mode, "passed": has_audio and float(probe["format"]["duration"]) > 0,
            "duration": float(probe["format"]["duration"]), "size": f"{video['width']}x{video['height']}",
            "cuts": status["result"].get("cut_count")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=list(MODES))
    args = parser.parse_args()
    out = args.output.resolve()
    media = fixtures(out / "fixtures")
    reports = []
    from playwright.sync_api import sync_playwright
    for mode in ([args.mode] if args.mode else list(MODES)):
        port = free_port()
        url = f"http://127.0.0.1:{port}"
        log = (out / f"server-{mode}.log").open("w")
        server = subprocess.Popen([sys.executable, str(ROOT / "app.py"), "--port", str(port), "--data", str(out / f"data-{mode}")],
                                  stdout=log, stderr=subprocess.STDOUT, env={**os.environ, "PYTHONUNBUFFERED": "1"})
        try:
            for _ in range(120):
                try:
                    urlopen(url + "/api/v1/wizard/status", timeout=2)
                    break
                except Exception:
                    time.sleep(1)
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 960})
                try:
                    reports.append(journey(page, url, mode, media, out))
                except Exception as exc:  # keep the evidence
                    page.screenshot(path=str(out / f"{mode}-exception.png"))
                    reports.append({"mode": mode, "passed": False, "error": repr(exc)})
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=30)
    (out / "summary.json").write_text(json.dumps(reports, indent=2))
    print(json.dumps(reports, indent=2))
    return 0 if reports and all(r["passed"] for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
