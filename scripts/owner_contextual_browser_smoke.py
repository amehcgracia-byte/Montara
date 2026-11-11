"""Browser smoke test for the authentic Chema mode/Owner integration.

Run only when Playwright and a Chromium binary are available. Creates ephemeral
SQLite databases and a local temporary server; never touches production Owner.
"""
from __future__ import annotations
import os
import tempfile
import threading
from pathlib import Path

from flask import Flask, jsonify
from werkzeug.serving import make_server

from urano.owner_mode_entry import owner_mode_entry_blueprint
from urano.original_jm_owner_assets import original_editor_assets_blueprint
from urano.editor_project_bridge import editor_project_bridge_blueprint
from urano.http_projects import project_blueprint
from urano.project_catalog import ProjectCatalog
from urano.session_auth import SESSION_COOKIE, SessionStore


def main():
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory(prefix="montara-ui-") as temporary:
        root = Path(temporary)
        catalog = ProjectCatalog(root / "projects.sqlite3")
        sessions = SessionStore(root / "sessions.sqlite3")
        owner_id = "a" * 32
        project = catalog.create(owner_id, "Private Stage check", recipe={
            "montara_beta_workspace": {"version": 1, "mode": "stage"}})
        issued = sessions.issue(owner_id)
        app = Flask("isolated_montara_owner_ui")
        server = make_server("127.0.0.1", 0, app)
        origin = f"http://127.0.0.1:{server.server_port}"
        web = Path(os.environ["MONTARA_JM_WEB_ROOT"])
        app.register_blueprint(owner_mode_entry_blueprint(
            sessions=sessions, https_origin=origin, web_root=web))
        app.register_blueprint(original_editor_assets_blueprint(
            catalog, sessions, https_origin=origin, web_root=web,
            enable_browser_pilot=True))
        app.register_blueprint(editor_project_bridge_blueprint(
            catalog, sessions, https_origin=origin))
        app.register_blueprint(project_blueprint(catalog, sessions))

        @app.post("/urano/v1/session/refresh")
        def refresh():
            return jsonify(csrf=issued.csrf)

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                executable = os.environ.get("MONTARA_TEST_CHROME")
                args = ["--no-sandbox", "--disable-dev-shm-usage"]
                opts = dict(headless=True, args=args)
                if executable:
                    opts["executable_path"] = executable
                browser = playwright.chromium.launch(**opts)
                context = browser.new_context(viewport={"width": 1280, "height": 780})
                context.add_cookies([{
                    "name": SESSION_COOKIE, "value": issued.token,
                    "url": origin, "secure": False,
                }])
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)[:150]))
                entry = page.goto(origin + "/urano/v1/entry")
                print("ENTRY", entry.status)
                assert entry.status == 200
                assert page.locator("#montaraOwnerProjectsButton").inner_text() == "All projects"
                page.locator('[data-intent="video"]').click()
                print("VIDEO_SCOPE", page.locator("#montaraOwnerProjectsButton").inner_text())
                page.locator("#modeQuestionBack").click()
                print("BACK_SCOPE", page.locator("#montaraOwnerProjectsButton").inner_text())
                page.locator('[data-intent="video"]').click()
                page.locator('[data-platform="youtube"]').click()
                page.wait_for_url("**/editor/projects/**", timeout=12000)
                page.wait_for_timeout(3100)
                visible = {name: page.locator("#" + name).is_visible()
                           for name in ("home", "mode", "footage", "making")}
                print("STAGE_VISIBLE", visible)
                print("STAGE_SCOPE", page.locator("#montaraOwnerProjectsButton").inner_text())
                print("HEADER_ORDER", page.locator("header.top").locator(":scope > *").evaluate_all(
                    "(els) => els.map(el => el.id || el.className || el.tagName)"))
                page.locator("header.top .brand").click()
                page.wait_for_timeout(250)
                print("HOME_VISIBLE", {name: page.locator("#" + name).is_visible()
                    for name in ("home", "mode", "footage")})
                print("HOME_SCOPE", page.locator("#montaraOwnerProjectsButton").inner_text())
                page.locator("#montaraOwnerProjectsButton").click()
                print("PICKER_OPEN", page.locator("#montaraOwnerProjectsDialog").evaluate("(e)=>e.open"))
                print("PICKER_ITEMS", page.locator(".montara-owner-choice").count())
                print("PAGE_ERRORS", errors[:8])
                context.close()
                browser.close()
        finally:
            server.shutdown()


if __name__ == "__main__":
    main()
