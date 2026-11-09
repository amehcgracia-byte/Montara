"""Real browser, HTTP, saved plan and FFmpeg, with a synthetic project."""
import io
import json
import os
from pathlib import Path
import subprocess
from threading import Thread
import zipfile

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from app import _prepare_environment, create_montara_app


def test_stage_save_keeps_other_previews_and_offers_companion_recovery(tmp_path):
    data = tmp_path / "data"
    _prepare_environment(data)
    from core.project import atomic_write_json, create_project, file_record
    from core.shot_continuity import continuous_views
    from server.inbox import load_global_config, save_global_config

    camera = tmp_path / "camera.small.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
        "testsrc2=s=320x180:r=24:d=4", "-c:v", "libx264", "-threads", "1", str(camera),
    ], check=True)
    project = create_project("Stage review", str(data / "Stage Review.zuckervid"))
    project.data["inputs"]["videos"] = [file_record(str(camera))]
    project.data["settings"]["wizard"] = {"platform": "youtube"}
    project.data["stages"]["edit"]["status"] = "done"
    project.save()
    initial = continuous_views([
        {
            "clip_path": str(camera), "source_path": str(camera), "clip_start_sec": i,
            "master_start_sec": i, "duration_sec": 1,
            "motion": {"type": "ken_burns", "target_x": .5, "target_y": .5},
        }
        for i in range(3)
    ])
    plan = project.artifacts_dir / "edit_plan.json"
    atomic_write_json(plan, {"platform": "youtube", "segments": initial})
    save_global_config({**load_global_config(), "last_project_path": str(project.folder)})

    app = create_montara_app(data, samples=False)
    # The fixture skips ingest and sync. Reconciliation may mark that
    # synthetic input stale, so declare the already-created plan ready.
    active = app.config["ZUCKER_STATE"].project
    active.data["stages"]["edit"]["status"] = "done"
    active.save()
    assert app.test_client().get("/api/v1/wizard/status").json["status"] == "waiting_review"
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as pw:
            executable = os.environ.get("MONTARA_TEST_CHROMIUM")
            browser = pw.chromium.launch(executable_path=executable)
            page = browser.new_page(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")
            # Deliberately simulate blocked loopback for the recovery screen.
            page.route("http://127.0.0.1:47820/**", lambda route: route.abort())
            url = f"http://127.0.0.1:{server.server_port}"
            page.goto(url + "/?resume=frames")
            page.on("pageerror", lambda error: print(f"Browser error: {error}"))
            page.locator("#frames").wait_for()
            page.wait_for_function(
                "document.querySelectorAll('#frameGrid .frame:not(.busy)').length === 3",
                timeout=45000,
            )
            first = page.locator('#frameGrid [data-index="0"]')
            middle = page.locator('#frameGrid [data-index="1"]')
            page.evaluate("window.firstShotImage = document.querySelector('#frameGrid [data-index=\"0\"] img')")
            first_image = first.locator("img").get_attribute("src")
            first_preview = first.locator(".thumb").get_attribute("data-preview")
            middle_preview = middle.locator(".thumb").get_attribute("data-preview")
            middle.get_by_role("button", name="Edit").click()
            dialog = page.get_by_role("dialog")
            dialog.get_by_role("checkbox", name="Movimiento").uncheck()
            with page.expect_response(lambda r: r.request.method == "PATCH" and r.url.endswith("/api/v1/edit/shot")) as saved:
                dialog.get_by_role("button", name="Save shot").click()
            assert saved.value.ok
            page.wait_for_function(
                """old => {
                    const shot = document.querySelector('#frameGrid [data-index="1"]');
                    return !shot.classList.contains('busy') && shot.querySelector('.thumb').dataset.preview !== old;
                }""",
                arg=middle_preview, timeout=45000,
            )
            assert first.locator("img").get_attribute("src") == first_image
            assert first.locator(".thumb").get_attribute("data-preview") == first_preview
            assert first.locator("img").evaluate("(img) => img === window.firstShotImage")
            current = json.loads(plan.read_text())["segments"]
            assert current[0] == initial[0] and current[2] == initial[2]
            assert current[1]["motion_enabled"] is False
            middle.get_by_role("button", name="Edit").click()
            assert not dialog.get_by_role("checkbox", name="Movimiento").is_checked()
            dialog.get_by_role("button", name="Cancel").click()
            screenshot_dir = os.environ.get("MONTARA_TEST_SCREENSHOTS")
            if screenshot_dir:
                page.screenshot(path=str(Path(screenshot_dir) / "stage-shot-saved.png"))
            page.locator("#renderFrames").click()
            page.locator("#companionRecovery").wait_for()
            assert "could not reach Companion" in page.locator("#errorText").inner_text()
            assert page.get_by_role("button", name="Check Companion and retry").is_visible()
            archive = page.request.get(url + page.locator("#companionRecoveryDownload").get_attribute("href"))
            assert archive.ok
            with zipfile.ZipFile(io.BytesIO(archive.body())) as bundle:
                folder = "Montara Companion/"
                assert len(bundle.read(folder + "SOURCE_COMMIT").strip()) == 40
                assert len(bundle.read(folder + "EDITOR_COMMIT").strip()) == 40
                assert bundle.getinfo(folder + "Install Montara Companion.command").external_attr >> 16 & 0o111
            if screenshot_dir:
                page.screenshot(path=str(Path(screenshot_dir) / "companion-recovery.png"))
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
