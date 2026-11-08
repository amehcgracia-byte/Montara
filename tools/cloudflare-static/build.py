#!/usr/bin/env python3
"""Build an isolated STATIC visual benchmark of Chema's existing frontend.

Never handles secrets, pushes a deployment, or attempts to proxy API/Companion.
Cloudflare Pages Git builds can use: python3 tools/cloudflare-static/build.py
and output directory: dist
"""
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
OUT = ROOT / "dist"
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)

# Copy only assets in web/, not repo .env, Python backend or fixtures.
for item in WEB.rglob("*"):
    if not item.is_file() or item.is_symlink():
        continue
    rel = item.relative_to(WEB)
    if any(part.startswith(".") for part in rel.parts):
        continue
    if item.suffix.lower() in {".html", ".css", ".js", ".svg", ".png", ".jpg",
                               ".jpeg", ".webp", ".gif", ".woff", ".woff2", ".ico"}:
        target = OUT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)

html_path = OUT / "index.html"
html = html_path.read_text(encoding="utf8")
# The static benchmark should never contact APIs, Companion or remote sources.
# Prevent POST/GET requests, network media and form submission from the replica.
csp = ('<meta http-equiv="Content-Security-Policy" '
       'content="default-src &#39;self&#39;; script-src &#39;self&#39;; '
       'style-src &#39;self&#39; &#39;unsafe-inline&#39;; '
       'img-src &#39;self&#39; data:; font-src &#39;self&#39;; '
       'connect-src &#39;none&#39;; media-src &#39;none&#39;; '
       'form-action &#39;none&#39;; object-src &#39;none&#39;">')
if "<head>" not in html:
    raise RuntimeError("Source structure changed")
html = html.replace("<head>", "<head>\n" + csp, 1)
html = html.replace("<body>", '<body data-benchmark="static-no-backend">', 1)
html_path.write_text(html, encoding="utf8")

# Resolve all local script/style/image dependencies used by index.html.
refs = re.findall(r'(?:src|href)="([^"]+)"', html)
required = [p for p in refs if p and not p.startswith(("/", "#", "http", "data:"))
            and not p.startswith("mailto:")]
missing = [p for p in required if not (OUT / p.split("?", 1)[0]).is_file()]
if missing:
    raise RuntimeError("Missing static assets: " + ", ".join(missing))
print(f"CLOUDFLARE_STATIC_BUILD_PASS: {sum(1 for x in OUT.rglob('*') if x.is_file())} assets; no backend, upload, or localhost access")
