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
REAL = ROOT / "tests" / "fixtures" / "much-to-me"
MODES = {"stage": "youtube", "pulse": "reel", "mix": "youtube"}


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


def media_files(media: Path) -> list[Path]:
    if (media / "cam-fixed.mp4").exists():  # real jam excerpt (Sony + fixed phone + 360 + master)
        return [media / "cam-sony.mp4", media / "cam-fixed.mp4", media / "cam-360.mp4", media / "master.mp3"]
    return [media / "camera-a.mp4", media / "camera-b.mp4", media / "master.wav"]


BRANDING = {"stage": "montara", "pulse": "none", "mix": "montara"}


def journey(page, url: str, mode: str, media: Path, out: Path) -> dict:
    shots = out / mode
    shots.mkdir(parents=True, exist_ok=True)
    page.goto(url)
    page.screenshot(path=str(shots / "01-home.png"), full_page=True)
    page.locator("#newVideo").click()
    page.locator(f'.mode[data-platform="{MODES[mode]}"]').click()
    page.locator("#videoName").fill(f"E2E {mode}")
    files = media_files(media)
    rows = "document.querySelectorAll('#videoFiles li, #audioFiles li').length"
    if mode == "mix" and media == REAL:
        # Default Stage sample: three cameras + the song as 14 separate tracks -> the mixer makes the master.
        page.wait_for_function(f"{rows} === 17", timeout=30_000)
    elif mode == "stage" and media == REAL:
        # Same cameras with the finished master (the "Use the finished master instead" link).
        page.wait_for_function(f"{rows} === 17", timeout=30_000)
        page.locator("#switchSample").click()
        page.wait_for_function(f"{rows} === {len(files)}", timeout=30_000)
    else:
        page.locator("[data-drop=video] input").set_input_files([str(f) for f in files])
    page.locator(f'input[name=branding][value="{BRANDING[mode]}"]').check()
    page.wait_for_function("!document.querySelector('#continueFootage').disabled", timeout=120_000)
    page.wait_for_timeout(300)
    page.screenshot(path=str(shots / "02-footage.png"), full_page=True)
    page.locator("#continueFootage").click()
    page.wait_for_selector("#cameras:not([hidden]), #making:not([hidden])", timeout=120_000)
    if page.locator("#cameras").is_visible():
        page.wait_for_timeout(3000)  # 360 frame + preview
        page.screenshot(path=str(shots / "03-cameras.png"), full_page=True)
        page.locator("#continueCameras").click()
    mixed = None
    if mode == "mix":
        page.locator("#mix").wait_for(state="visible")
        page.wait_for_function("!document.querySelector('#useMix').disabled", timeout=300_000)
        page.screenshot(path=str(shots / "03b-mix-auto.png"), full_page=True)
        # Pull the first active fader down 6 dB, as a person would.
        page.evaluate("""() => { const s = [...document.querySelectorAll('.strip:not(.off) input')][0];
            s.value = -6; s.dispatchEvent(new Event('input', {bubbles: true})); }""")
        page.locator("#playMix").click()
        page.wait_for_timeout(1500)
        page.locator("#playMix").click()
        page.screenshot(path=str(shots / "03c-mix-moved.png"), full_page=True)
        page.locator("#useMix").click()
    page.locator("#making").wait_for(state="visible", timeout=300_000)
    page.wait_for_timeout(4000)
    page.screenshot(path=str(shots / "04-making.png"))
    page.wait_for_selector("#frames:not([hidden]), #result:not([hidden]), #failed:not([hidden])", timeout=900_000)
    swapped = False
    if page.locator("#frames").is_visible():
        page.wait_for_function("!document.querySelector('#framesHint').textContent.includes('Preparing')", timeout=300_000)
        page.screenshot(path=str(shots / "05-frames.png"), full_page=True)
        first = page.locator(".frame .swap:not([disabled])").first
        if first.count():
            before = first.locator("xpath=../div/img").get_attribute("src")
            first.click()
            page.wait_for_timeout(1000)
            page.wait_for_function("!document.querySelector('.frame.busy')", timeout=180_000)
            swapped = first.locator("xpath=../div/img").get_attribute("src") != before
            page.screenshot(path=str(shots / "06-frames-swapped.png"), full_page=True)
        page.locator("#renderFrames").click()
        page.wait_for_selector("#result:not([hidden]), #failed:not([hidden])", timeout=900_000)
    if page.locator("#failed").is_visible():
        page.screenshot(path=str(shots / "99-failed.png"))
        return {"mode": mode, "passed": False, "error": page.locator("#errorText").inner_text()}
    page.wait_for_timeout(1500)
    page.screenshot(path=str(shots / "07-result.png"))
    with urlopen(url + "/api/v1/wizard/status", timeout=15) as response:
        status = json.load(response)
    path = Path(status["result"]["path"])
    probe = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
    run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"])  # decode the whole file
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    has_audio = any(s["codec_type"] == "audio" for s in probe["streams"])
    (shots / "render.mp4").write_bytes(path.read_bytes())
    duration = float(probe["format"]["duration"])
    for second in (2.0, duration / 2, max(0.0, duration - 2.0)):  # intro, body, outro: look at them
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{second:.2f}", "-i", str(path), "-frames:v", "1",
             str(shots / f"frame-{int(second):03d}s.png")])
    result = status["result"]
    if mode == "mix":
        project = json.loads((Path(status["project_path"]) / "project.json").read_text())
        mixed = ((project.get("inputs") or {}).get("master") or {}).get("path")
    cameras = [f.name for f in files if f.suffix == ".mp4"]
    used = result.get("camera_usage") or {}
    # Stage must use every camera (the sync found all of them); Pulse may pick.
    # (the engine may rename a camera to a cached proxy, so count cameras, not names)
    all_used = mode == "pulse" or (len([k for k, n in used.items() if n]) >= len(cameras) and not result.get("excluded_clips"))
    return {"mode": mode, "media": media.name, "branding": BRANDING[mode], "passed": has_audio and duration > 0 and all_used and (mode != "mix" or bool(mixed and "Mixer" in mixed)),
            "duration": duration, "size": f"{video['width']}x{video['height']}", "frames_swapped": swapped, "mixed_master": mixed,
            "cuts": result.get("cut_count"), "camera_usage": used, "excluded": result.get("excluded_clips")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=list(MODES))
    parser.add_argument("--synthetic", action="store_true", help="use generated test patterns instead of the real jam excerpt")
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    media = fixtures(out / "fixtures") if args.synthetic or not REAL.exists() else REAL
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
