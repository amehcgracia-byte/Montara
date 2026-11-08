"""Real HTTPS Chromium acceptance of Google OIDC *simulated provider*, two owners.

No Google credentials or external Google access. The browser navigates through
the same redirect/callback path, with Playwright intercepting only the fixed
Google authorization URL and a fake signed ID token on the backend.
"""
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_google_flow_contract import SignedFakeGoogle, CLIENT
from urano.google_flow import OIDCSettings
from urano.google_lab_app import create_google_lab_app
from urano.engine_bindings import EngineProjectRegistry
from urano.google_owner import GoogleOwnerStore
from urano.project_catalog import ProjectCatalog


class BrowserGoogle(SignedFakeGoogle):
    def exchange(self, code, verifier, settings):
        self.calls += 1
        assert code == self.code
        assert self.expected_challenge == __import__("base64").urlsafe_b64encode(
            __import__("hashlib").sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        return self.token(self.nonce)


def available_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="montara-u15c-lab-") as temporary:
        root = Path(temporary)
        cert, key = root / "cert.pem", root / "key.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048",
                        "-nodes", "-keyout", str(key), "-out", str(cert),
                        "-days", "1", "-subj", "/CN=localhost"],
                       check=True, capture_output=True)
        port = available_port()
        origin = f"https://127.0.0.1:{port}"
        provider = BrowserGoogle()
        settings = OIDCSettings(CLIENT, "lab-fake-only", origin + "/urano/v1/google/callback",
                                frozenset({"alpha@example.test", "beta@example.test"}))
        engine_root = root / "engine-test-data"
        projects_root = engine_root / "Projects"
        projects_root.mkdir(parents=True)
        for folder in ("test-stage-A.zuckervid", "test-stage-B.zuckervid"):
            location = projects_root / folder
            location.mkdir()
            (location / "project.json").write_text('{"test_only":true}', encoding="utf-8")
        app = create_google_lab_app(root, settings=settings, provider=provider,
                                    engine_data_root=engine_root)
        catalog = ProjectCatalog(root / "projects.sqlite3")
        registry = EngineProjectRegistry(root / "engine_bindings.sqlite3", engine_root, catalog)
        owners = GoogleOwnerStore(root / "owners.sqlite3")
        allowlist = settings.allowed_emails
        server = make_server("127.0.0.1", port, app, ssl_context=(str(cert), str(key)), threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        errors = []
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                context_a = browser.new_context(ignore_https_errors=True)
                context_b = browser.new_context(ignore_https_errors=True)
                a, b = context_a.new_page(), context_b.new_page()
                for page in (a, b):
                    page.on("pageerror", lambda err: errors.append(str(err)))

                def login(page, sub, email):
                    provider.sub, provider.email = sub, email
                    page.goto(origin + "/urano-google-lab/")
                    expect(page.locator("#signedOut")).to_be_visible()
                    expect(page.locator("#googleLogin")).to_have_attribute("href", "/urano/v1/google/start")
                    # BrowserContext's API client shares cookies with its real
                    # Chromium tab. Max redirects 0: absolutely no request to
                    # Google's external authorization endpoint.
                    response = page.context.request.get(
                        origin + "/urano/v1/google/start", max_redirects=0)
                    assert response.status == 302, response.status
                    authorization = urlsplit(response.headers["location"])
                    assert authorization.scheme == "https"
                    assert authorization.netloc == "accounts.google.com"
                    assert authorization.path == "/o/oauth2/v2/auth"
                    params = parse_qs(authorization.query)
                    assert params["redirect_uri"] == [settings.redirect_uri]
                    assert params["response_type"] == ["code"]
                    assert params["code_challenge_method"] == ["S256"]
                    provider.nonce = params["nonce"][0]
                    provider.expected_challenge = params["code_challenge"][0]
                    provider.code = "fake-provider-code"
                    callback = (settings.redirect_uri + "?state=" + params["state"][0]
                                + "&code=fake-provider-code")
                    page.goto(callback)
                    page.wait_for_url(origin + "/urano-google-lab/", timeout=15000)
                    expect(page.locator("#signedIn")).to_be_visible(timeout=15000)

                def create(page, title):
                    form = page.locator("#createProject")
                    form.locator("[name=title]").fill(title)
                    form.locator("button").click()
                    expect(page.locator("#projectTitle")).to_have_text(title)
                    expect(page.locator("#save")).to_be_enabled()

                login(a, "alpha-google-sub", "alpha@example.test")
                create(a, "Primer proyecto de A")
                a.locator("#notes").fill("Cortes y notas conservados solo como receta de laboratorio")
                a.locator("#save").click()
                expect(a.locator("#notice")).to_have_text("Cambios guardados.")
                create(a, "Segundo proyecto de A")
                assert a.locator(".project").count() == 2
                owner_a = owners.resolve_beta_owner(
                    __import__("urano.google_oidc", fromlist=["GoogleIdentity"]).GoogleIdentity(
                        "alpha-google-sub", "alpha@example.test"), allowed_emails=allowlist)
                project_a = next(p for p in catalog.list_for(owner_a) if p.title == "Primer proyecto de A")
                registry.bind_trusted(owner_a, project_a.id, "test-stage-A.zuckervid")
                a.locator(".project").filter(has_text="Primer proyecto de A").click()
                expect(a.locator("#engineStatus")).to_have_text(
                    "Workspace vinculado (aún sin activar ni render)")
                response = a.evaluate("""async id => {
                  const r = await fetch('/urano/v1/projects/' + id + '/engine');
                  return { status:r.status, body:await r.json() };
                }""", project_a.id)
                assert response["status"] == 200
                assert response["body"] == {"linked": True, "status":"linked_not_activated",
                                            "engine_access":False, "render_access":False}
                a.reload()
                expect(a.locator("#signedIn")).to_be_visible()
                a.locator(".project").filter(has_text="Primer proyecto de A").click()
                expect(a.locator("#notes")).to_have_value("Cortes y notas conservados solo como receta de laboratorio")
                a.screenshot(path=str(out / "01-alpha-history.png"), full_page=True)

                login(b, "beta-google-sub", "beta@example.test")
                assert b.locator(".project").count() == 0
                create(b, "Privado de B")
                assert b.locator(".project").count() == 1
                owner_b = owners.resolve_beta_owner(
                    __import__("urano.google_oidc", fromlist=["GoogleIdentity"]).GoogleIdentity(
                        "beta-google-sub", "beta@example.test"), allowed_emails=allowlist)
                project_b = next(p for p in catalog.list_for(owner_b) if p.title == "Privado de B")
                registry.bind_trusted(owner_b, project_b.id, "test-stage-B.zuckervid")
                b.locator(".project").filter(has_text="Privado de B").click()
                expect(b.locator("#engineStatus")).to_have_text(
                    "Workspace vinculado (aún sin activar ni render)")
                for foreign_page, foreign_id in ((a, project_b.id), (b, project_a.id)):
                    result = foreign_page.evaluate("""async id => {
                      const response = await fetch('/urano/v1/projects/' + id + '/engine');
                      return {status: response.status, body: await response.json()};
                    }""", foreign_id)
                    assert result["status"] == 404, result
                    assert "test-stage-" not in str(result["body"])
                assert a.locator(".project").count() == 2
                b.screenshot(path=str(out / "02-beta-isolated.png"), full_page=True)

                a.locator("#logout").click()
                expect(a.locator("#signedOut")).to_be_visible()
                a.reload()
                expect(a.locator("#signedOut")).to_be_visible()
                login(a, "alpha-google-sub", "alpha@example.test")
                assert a.locator(".project").count() == 2
                assert b.locator(".project").count() == 1
                a.screenshot(path=str(out / "03-alpha-recovered.png"), full_page=True)
                assert not errors, errors
                browser.close()

            summary = {
                "passed": True, "https_browser": True, "fake_google_only": True,
                "oauth_code_pkce_callback": True, "two_isolated_owners": True,
                "project_history_after_logout": True, "editor_connected": False,
                "engine_or_companion_connected": False, "real_google_credentials": False,
                "owner_engine_link_readonly": True, "cross_owner_engine_link_denied": True,
            }
            (out / "summary.json").write_text(json.dumps(summary, indent=2))
            print(json.dumps(summary))
        finally:
            server.shutdown()
            thread.join(timeout=5)


if __name__ == "__main__":
    main()
