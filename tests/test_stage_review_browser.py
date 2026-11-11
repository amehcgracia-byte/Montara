"""Real browser, HTTP, saved plan and FFmpeg, with a synthetic project."""
import json
import os
from pathlib import Path
import subprocess
from threading import Thread

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

    # The download endpoint serves a version-pinned native macOS .pkg now.
    # This is a MIME/routing fixture, not a signed Apple package.
    engine_sha = subprocess.check_output(
        ["git", "-C", str(Path(__file__).resolve().parents[1] / "engine"),
         "rev-parse", "HEAD"], text=True).strip()
    installer = data / "Installers" / f"Montara-Companion-{engine_sha[:8]}.pkg"
    installer.parent.mkdir(parents=True, exist_ok=True)
    installer.write_bytes(b"xar!" + bytes(2048))

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
            dialog.get_by_role("checkbox", name="Movement").uncheck()
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
            assert not dialog.get_by_role("checkbox", name="Movement").is_checked()
            dialog.get_by_role("button", name="Cancel").click()
            # Exercise the first switch from a sphere to a flat camera,
            # where its crop controls do not exist until update() mounts them.
            import copy
            view_doc = copy.deepcopy(page.request.get(url+'/api/v1/edit/shot?index=1').json())
            view_doc.update(pose={'yaw':20,'pitch':0,'fov':90}, movement=False)
            choice = view_doc['choices'][0]
            view_doc['choices'] = [
                {**choice,'label':'360 Singer','spherical':True,'pose':{'yaw':20,'pitch':0,'fov':90},'movement':False},
                {**choice,'label':'Fixed Guitar','spherical':False,'framing':{'zoom':2,'x':.65,'y':.4},'movement':False},
                {**choice,'label':'360 Piano','spherical':True,'pose':{'yaw':100,'pitch':-8,'fov':80},'movement':True},
                {**choice,'label':'360 Drums','spherical':True,'pose':{'yaw':200,'pitch':5,'fov':100},'movement':False},
            ]
            view_doc['saved_views']=[{'name':'Guitar','source_path':choice['source_path'],
                'flat_framing':{'zoom':2,'x':.65,'y':.4},'motion_enabled':False}]
            def shot_fixture(route):
                route.fulfill(json=view_doc)
            page.route('**/api/v1/edit/shot?index=1',shot_fixture)
            middle.get_by_role('button',name='Edit').click()
            dialog=page.get_by_role('dialog')
            camera_select=dialog.locator('[name=camera]')
            camera_select.select_option('1')
            assert float(dialog.get_by_role('slider',name='Close or open the shot').input_value()) == 2
            camera_select.select_option('2')
            assert dialog.locator('[name=yaw]').input_value() == '100'
            assert dialog.get_by_role('checkbox',name='Movement',exact=True).is_checked()
            camera_select.select_option('3')
            assert dialog.locator('[name=yaw]').input_value() == '-160'
            assert not dialog.get_by_role('checkbox',name='Movement',exact=True).is_checked()
            dialog.get_by_role('button',name='Guitar',exact=True).click()
            assert float(dialog.get_by_role('slider',name='Close or open the shot').input_value()) == 2
            assert dialog.locator('[name=camera]').input_value() == '1'
            dialog.get_by_role('button',name='Cancel',exact=True).click()
            page.unroute('**/api/v1/edit/shot?index=1',shot_fixture)
            assert json.loads(plan.read_text())['segments'] == current
            screenshot_dir = os.environ.get("MONTARA_TEST_SCREENSHOTS")
            if screenshot_dir:
                page.screenshot(path=str(Path(screenshot_dir) / "stage-shot-saved.png"))
            page.locator("#renderFrames").click()
            page.locator("#companionRecovery").wait_for()
            assert "could not reach Companion" in page.locator("#errorText").inner_text()
            assert page.get_by_role("button", name="Check Companion and retry").is_visible()
            installer_download = page.request.get(
                url + page.locator("#companionRecoveryDownload").get_attribute("href"))
            assert installer_download.ok
            assert ".pkg" in installer_download.headers["content-disposition"]
            assert "application/octet-stream" in installer_download.headers["content-type"]
            assert installer_download.body().startswith(b"xar!")
            if screenshot_dir:
                page.screenshot(path=str(Path(screenshot_dir) / "companion-recovery.png"))
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
