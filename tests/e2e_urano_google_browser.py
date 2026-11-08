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
        app = create_google_lab_app(root, settings=settings, provider=provider)
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

                def google_redirect(route):
                    params = parse_qs(urlsplit(route.request.url).query)
                    assert params["redirect_uri"][0] == settings.redirect_uri
                    assert params["response_type"][0] == "code"
                    assert params["code_challenge_method"][0] == "S256"
                    provider.nonce = params["nonce"][0]
                    provider.expected_challenge = params["code_challenge"][0]
                    provider.code = "fake-provider-code"
                    callback = settings.redirect_uri + "?state=" + params["state"][0] + "&code=fake-provider-code"
                    route.fulfill(status=302, headers={"Location": callback}, body="")

                for page in (a, b):
                    page.route("https://accounts.google.com/**", google_redirect)

                def login(page, sub, email):
                    provider.sub, provider.email = sub, email
                    page.goto(origin + "/urano-google-lab/")
                    expect(page.locator("#signedOut")).to_be_visible()
                    page.locator("#googleLogin").click()
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
                a.reload()
                expect(a.locator("#signedIn")).to_be_visible()
                a.locator(".project").filter(has_text="Primer proyecto de A").click()
                expect(a.locator("#notes")).to_have_value("Cortes y notas conservados solo como receta de laboratorio")
                a.screenshot(path=str(out / "01-alpha-history.png"), full_page=True)

                login(b, "beta-google-sub", "beta@example.test")
                assert b.locator(".project").count() == 0
                create(b, "Privado de B")
                assert b.locator(".project").count() == 1
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
            }
            (out / "summary.json").write_text(json.dumps(summary, indent=2))
            print(json.dumps(summary))
        finally:
            server.shutdown()
            thread.join(timeout=5)


if __name__ == "__main__":
    main()
