"""End-to-end check of Montara on a clean machine (Linux CI or a laptop).

Starts the real server, drives the real interface in Chromium and runs the real
engine: nothing is mocked. Produces screenshots and the exported videos.

    python tests/e2e_journey.py --output /tmp/montara-e2e [--mode stage|push]
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
MODES = {"stage": "youtube", "push": "reel", "mix": "youtube"}


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


BRANDING = {"stage": "montara", "push": "none", "mix": "montara"}


def journey(page, url: str, mode: str, media: Path, out: Path) -> dict:
    started = time.monotonic()
    shots = out / mode
    shots.mkdir(parents=True, exist_ok=True)
    page.goto(url)
    page.screenshot(path=str(shots / "01-home.png"), full_page=True)
    # The current splash automatically leads to How; there is no visible New video step.
    page.locator("#mode").wait_for(state="visible", timeout=30_000)
    page.locator(f'.mode[data-platform="{MODES[mode]}"]').click()
    page.locator("#videoName").fill(f"E2E {mode}")
    files = media_files(media)
    rows = "document.querySelectorAll('#videoFiles li, #audioFiles li').length"
    if mode == "mix" and media == REAL:
        # Default Stage sample: three cameras + the song as 9 separate tracks -> the mixer makes the master.
        page.wait_for_function(f"{rows} === 12", timeout=30_000)
    elif mode == "stage" and media == REAL:
        # Same cameras with the finished master (the "Use the finished master instead" link).
        page.wait_for_function(f"{rows} === 12", timeout=30_000)
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
    page.wait_for_selector("#frames:not([hidden]), #result:not([hidden]), #failed:not([hidden])", timeout=1_800_000)
    swapped = False
    if page.locator("#frames").is_visible():
        page.wait_for_function("!document.querySelector('#framesHint').textContent.includes('Preparing')", timeout=300_000)
        page.screenshot(path=str(shots / "05-frames.png"), full_page=True)
        first = page.locator(".frame .swap:not([disabled])").first
        if first.count():
            before = page.locator(".frame .thumb img").first.get_attribute("src")
            first.click()
            page.wait_for_timeout(1000)
            page.wait_for_function("!document.querySelector('.frame.busy')", timeout=180_000)
            swapped = page.locator(".frame .thumb img").first.get_attribute("src") != before
            page.screenshot(path=str(shots / "06-frames-swapped.png"), full_page=True)
        page.locator("#renderFrames").click()
        page.wait_for_selector("#captions:not([hidden]), #result:not([hidden]), #failed:not([hidden])", timeout=1_800_000)
    captioned = False
    if page.locator("#captions").is_visible():
        # Push: title + two typed captions, spread over the reel, burned by the engine.
        # (headless Chromium cannot decode H.264: the player stays empty here, captions still work)
        page.locator("#capTitle").fill("Much to me")
        page.locator("#capText").fill("Much to me\nEvery night we play")
        page.locator('#capStyles [data-style="hard_shadow"]').click()
        # Shape the second caption on its own: orange, Impact, pulse, moved up on the video.
        page.locator('.capbar[data-i="1"]').click()
        page.locator('#capColors [data-color="#FF4F2E"]').click()
        page.locator('#capFonts [data-font="Impact"]').click()
        page.locator('#capEffects [data-effect="pulse"]').click()
        box = page.locator(".capline.sel").bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.down()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] - 200, steps=5)
        page.mouse.up()
        page.wait_for_timeout(500)
        page.screenshot(path=str(shots / "06b-captions.png"), full_page=True)
        page.locator("#capApply").click()
        captioned = True
        page.wait_for_selector("#result:not([hidden]), #failed:not([hidden])", timeout=1_800_000)
    if page.locator("#failed").is_visible():
        page.screenshot(path=str(shots / "99-failed.png"))
        return {"mode": mode, "passed": False, "error": page.locator("#errorText").inner_text()}
    page.wait_for_timeout(1500)
    page.screenshot(path=str(shots / "07-result.png"))
    # HTTP also exercises a real container/private host; never read its disk paths.
    response = page.request.get(url + "/api/v1/wizard/status")
    assert response.ok
    status = response.json()
    server_name = Path(status["result"]["path"]).name
    exported = page.request.get(url + "/api/v1/wizard/result", timeout=180_000)
    assert exported.ok
    path = shots / 'render.mp4'
    path.write_bytes(exported.body())
    journey_seconds = time.monotonic() - started
    probe = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
    run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"])  # decode the whole file
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    has_audio = any(s["codec_type"] == "audio" for s in probe["streams"])
    if mode == "push":
        assert not captioned or "caption" in server_name, f"captions were not burned: {server_name}"
    duration = float(probe["format"]["duration"])
    for second in (2.0, duration / 2, max(0.0, duration - 2.0)):  # intro, body, outro: look at them
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{second:.2f}", "-i", str(path), "-frames:v", "1",
             str(shots / f"frame-{int(second):03d}s.png")])
    result = status["result"]
    project_response = page.request.get(url + '/api/v1/project')
    assert project_response.ok
    project = project_response.json()
    if mode == "mix":
        mixed = ((project.get("inputs") or {}).get("master") or {}).get("path")
    cameras = [f.name for f in files if f.suffix == ".mp4"]
    used = result.get("camera_usage") or {}
    # Stage must use every camera (the sync found all of them); Push may pick.
    # (the engine may rename a camera to a cached proxy, so count cameras, not names)
    all_used = mode == "push" or (len([k for k, n in used.items() if n]) >= len(cameras) and not result.get("excluded_clips"))
    return {"mode": mode, "media": media.name, "branding": BRANDING[mode], "passed": has_audio and duration > 0 and all_used and (mode != "mix" or bool(mixed and "Mixer" in mixed)),
            "duration": duration, "captioned": captioned, "size": f"{video['width']}x{video['height']}", "frames_swapped": swapped, "mixed_master": Path(mixed).name if mixed else None,
            "measured_browser_journey_seconds_including_ui_waits_and_download": round(journey_seconds, 3),
            "measured_engine_stage_seconds": {name: value['elapsed_seconds'] for name, value in project.get('stages', {}).items() if isinstance(value, dict) and value.get('elapsed_seconds') is not None},
            "cuts": result.get("cut_count"), "camera_usage": used, "excluded": result.get("excluded_clips")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=list(MODES))
    parser.add_argument("--synthetic", action="store_true", help="use generated test patterns instead of the real jam excerpt")
    parser.add_argument('--base-url', help='DESTRUCTIVE TEST: use an isolated existing host; creates/edits its current project. Never use a user/production instance.')
    parser.add_argument('--stdout-screenshots', action='store_true', help='Small bounded review evidence when CI artifact storage is unavailable.')
    args = parser.parse_args()
    if args.base_url:
        from urllib.parse import urlsplit
        parsed = urlsplit(args.base_url)
        if parsed.scheme not in {'http', 'https'} or parsed.username or parsed.password or parsed.query or parsed.fragment:
            parser.error('Use an HTTP(S) base URL without credentials or query parameters.')
        args.base_url = args.base_url.rstrip('/')
        if not args.mode:
            parser.error('--base-url requires one --mode for an isolated test instance.')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    media = fixtures(out / "fixtures") if args.synthetic or not REAL.exists() else REAL
    reports = []
    from playwright.sync_api import sync_playwright
    for mode in ([args.mode] if args.mode else list(MODES)):
        port = free_port()
        url = args.base_url or f"http://127.0.0.1:{port}"
        log = (out / f"server-{mode}.log").open("w")
        server = None if args.base_url else subprocess.Popen([sys.executable, str(ROOT / "app.py"), "--port", str(port), "--data", str(out / f"data-{mode}")],
                                  stdout=log, stderr=subprocess.STDOUT, env={**os.environ, "PYTHONUNBUFFERED": "1"})
        try:
            if args.base_url:
                # Context-scoped Basic auth; credentials never appear in a URL/report.
                credentials = {'username': 'montara', 'password': os.environ['MONTARA_PREVIEW_PASSWORD']}
            else:
                credentials = None
            for _ in range(120):
                try:
                    if args.base_url:
                        break  # Browser context authenticates the actual readiness request below.
                    with urlopen(url + "/api/v1/wizard/status", timeout=2):
                        pass
                    break
                except Exception:
                    time.sleep(1)
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 960}, http_credentials=credentials)
                try:
                    if args.base_url:
                        response = page.request.get(url + '/api/v1/wizard/status', timeout=120_000)
                        assert response.ok, f'Private host not ready: HTTP {response.status}'
                    reports.append(journey(page, url, mode, media, out))
                except Exception as exc:  # keep the evidence
                    page.screenshot(path=str(out / f"{mode}-exception.png"))
                    reports.append({"mode": mode, "passed": False, "error": repr(exc)})
                browser.close()
        finally:
            if server:
                server.terminate()
                server.wait(timeout=30)
            log.close()
    (out / "summary.json").write_text(json.dumps(reports, indent=2))
    print(json.dumps(reports, indent=2))
    if args.stdout_screenshots:
        import base64
        from io import BytesIO
        from PIL import Image
        for mode in ([args.mode] if args.mode else list(MODES)):
            for name in ('03-cameras.png', '05-frames.png', '07-result.png'):
                source = out / mode / name
                if source.is_file():
                    buffer = BytesIO()
                    picture = Image.open(source).convert('RGB')
                    picture.thumbnail((1200, 1000))
                    picture.save(buffer, format='WEBP', quality=75)
                    print('MONTARA_CHECK_SCREENSHOT ' + mode + '-' + source.stem + '.webp ' + base64.b64encode(buffer.getvalue()).decode())
    return 0 if reports and all(r["passed"] for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
