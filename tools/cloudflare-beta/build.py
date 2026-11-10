"""Build one static landing page for a dedicated Pages project.

No uploads, JS, login provider, dynamic routes or access to the VM. The
output must never contain the legacy single-user Montara app or secrets.
"""
from __future__ import annotations

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "deployment" / "cloudflare-beta" / "public"
TARGET = ROOT / "dist"

def build():
    if TARGET.exists():
        raise RuntimeError("Refusing to overwrite an existing dist directory")
    for file in ("index.html", "_headers"):
        if not (SOURCE / file).is_file() or (SOURCE / file).is_symlink():
            raise RuntimeError("Missing pinned landing resource")
    html = (SOURCE / "index.html").read_text(encoding="utf-8")
    assert 'Acceso con Google próximamente' in html
    assert 'disabled aria-describedby="beta-wait"' in html
    assert "montara-tau.vercel.app" not in html
    assert "/api/v1/" not in html
    assert "/urano/v1/google/start" not in html  # no broken live-login link
    TARGET.mkdir()
    for file in ("index.html", "_headers"):
        shutil.copyfile(SOURCE / file, TARGET / file)
    print("static Montara beta landing ready (no authentication or backend)")

if __name__ == "__main__":
    build()
