"""Fail-closed static Pages build for Montara's verified Google owner portal.

Cloudflare Pages must never publish the Flask app, runtime, secrets or the old
single-user editor. This builder copies exactly two audited static assets.
"""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
import shutil

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "deployment" / "cloudflare-beta" / "public"
TARGET = ROOT / "dist"
OWNER_BASE = "https://montara-owner.memoriainvalida001.workers.dev"
ALLOWED_AUTH_URLS = frozenset((OWNER_BASE + "/login", OWNER_BASE + "/register"))


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors = []
    def handle_starttag(self, tag, attributes):
        if tag == "a":
            self.anchors.append(dict(attributes).get("href", ""))


def build():
    if TARGET.exists():
        raise RuntimeError("Refusing to overwrite an existing dist directory")
    for name in ("index.html", "_headers"):
        source = SOURCE / name
        if not source.is_file() or source.is_symlink():
            raise RuntimeError("Missing pinned landing resource")
    html = (SOURCE / "index.html").read_text(encoding="utf-8")
    headers = (SOURCE / "_headers").read_text(encoding="utf-8")
    links = _Links(); links.feed(html)
    parsed = urlsplit(OWNER_BASE)
    if parsed.scheme != "https" or parsed.path != "" or parsed.query or parsed.fragment:
        raise RuntimeError("Unsafe pinned owner URL")
    if not ALLOWED_AUTH_URLS.issubset(set(links.anchors)):
        raise RuntimeError("Visible Login and registration must point to the approved Owner routes")
    if any(link and not link.startswith("#") and link not in ALLOWED_AUTH_URLS for link in links.anchors):
        raise RuntimeError("External link points outside the verified Owner portal")
    if ("Acceso con Google próximamente" in html or "<form" in html or
            "<input" in html or "/api/v1/" in html or
            "montara-tau.vercel.app" in html or
            "Content-Security-Policy:" not in headers or
            "default-src 'none'" not in headers):
        raise RuntimeError("Unreviewed landing content or missing CSP")
    TARGET.mkdir()
    shutil.copyfile(SOURCE / "index.html", TARGET / "index.html")
    shutil.copyfile(SOURCE / "_headers", TARGET / "_headers")
    print("Montara static landing ready: login choice entry (no editor or original uploads)")


if __name__ == "__main__":
    build()
