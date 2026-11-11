"""Authenticated Montara mode entry assembled from the pinned Chema editor assets.

No parallel editor, no worker startup, no implicit project creation.
The original mode section and header are reused from the immutable JM web bundle.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, Response, abort, jsonify, request

from urano.session_auth import SESSION_COOKIE, SessionStore


SCRIPT = r"""'use strict';
const message = document.querySelector('#ownerMessage');
const modeSection = document.querySelector('#mode');
const homeSection = document.querySelector('#home');
const originalChemaHome = homeSection.innerHTML;
let homeTimer = null;
function showHome() {
  clearTimeout(homeTimer);
  modeSection.hidden = true;
  // Chema's CSS intro is attached to the SVG/letter elements. Recreate
  // those SAME original elements to restart its exact animation every time,
  // instead of resuming their already-finished timeline.
  homeSection.hidden = true;
  homeSection.innerHTML = originalChemaHome;
  homeSection.hidden = false;
  document.body.classList.add('is-intro');
  window.MontaraProjectPicker?.setScope('all');
  homeTimer = setTimeout(() => choices('root'),
    matchMedia('(prefers-reduced-motion: reduce)').matches ? 650 : 2450);
}
function notice(value) { message.textContent = value || ''; }
async function api(path, options={}) {
  const res = await fetch('/urano/v1/' + path, {credentials:'same-origin', cache:'no-store', ...options});
  const body = await res.json().catch(()=>({}));
  if (!res.ok) throw Error(body.error || 'La solicitud no está disponible');
  return body;
}
async function csrf() {
  return window.MontaraOwnerCsrf.get();
}
function openEditor(id, newlyCreated=false) {
  if (!/^[0-9a-f-]{36}$/i.test(id)) throw Error('Invalid project ID');
  try {sessionStorage.setItem('montara-owner-selected-stage',id);} catch {}
  location.assign('/urano/v1/editor/projects/' + encodeURIComponent(id) + '/' +
                  (newlyCreated ? '?start=stage' : '?resume=footage'));
}
function choices(kind) {
  clearTimeout(homeTimer);
  homeSection.hidden = true;
  modeSection.hidden = false;
  document.body.classList.remove('is-intro');
  window.MontaraProjectPicker?.setScope(kind === 'root' ? 'all' : kind);
  document.querySelector('#intentChoices').hidden = kind !== 'root';
  document.querySelector('#videoChoices').hidden = kind !== 'video';
  document.querySelector('#musicChoices').hidden = kind !== 'music';
  document.querySelector('#modeQuestionBack').hidden = kind === 'root';
  document.querySelector('#modeQuestion').textContent =
    kind === 'video' ? 'What kind of video?' :
    kind === 'music' ? 'What does your music need?' : 'What would you like to make?';
}
async function stage() {
  // Enter Stage directly when an existing private Stage is available.
  // Do not create an unwanted empty project or switch a running Engine here.
  notice('');
  try {
    const result = await api('editor/projects?mode=stage');
    if (result.projects?.length) {
      // Remember an explicitly chosen Owner project, but only if the server's
      // authenticated Stage catalog still contains it. Never trust local
      // storage as an authorization source.
      let selected=null;
      try {selected=sessionStorage.getItem('montara-owner-selected-stage');}catch {}
      const current=result.projects.find(p=>p.id===selected) || result.projects[0];
      openEditor(current.id, true);
      return;
    }
    notice('');
    window.MontaraProjectPicker.open('stage');
  } catch (error) {
    notice(error.message || 'Stage is temporarily unavailable.');
  }
}
document.querySelectorAll('[data-intent]').forEach(button => {
  button.addEventListener('click', () => choices(button.dataset.intent));
});
document.querySelector('#modeQuestionBack').addEventListener('click', ()=>choices('root'));
document.querySelector('header.top .brand').addEventListener('click', event => {
  event.preventDefault(); showHome(); notice('');
});
homeSection.addEventListener('click', () => choices('root'));
document.querySelectorAll('[data-platform]').forEach(button => {
  button.addEventListener('click', () => {
    if (button.dataset.platform === 'youtube') stage();
    else notice('Push and Show are not connected to the private beta yet.');
  });
});
document.querySelectorAll('[data-audio-task]').forEach(button => {
  button.addEventListener('click', () => notice('Music editing is not connected to the private beta yet.'));
});
document.querySelector('#ownerLogout').addEventListener('click', async () => {
  try {
    await api('logout', {method:'POST', headers:{'X-Urano-CSRF':await csrf(), Origin:location.origin}});
    location.replace('/urano/v1/login');
  } catch (error) { notice(error.message); }
});
showHome();
"""


def owner_mode_entry_blueprint(*, sessions: SessionStore, https_origin: str,
                               web_root: Path) -> Blueprint:
    root = Path(web_root).resolve(strict=True)
    original = (root / "index.html").read_text(encoding="utf-8")
    header_start = '<header class="top">'
    header_end = '</header>'
    home_start = '<section class="screen" id="home">'
    mode_start = '<section class="screen" id="mode" hidden>'
    mode_end = '</section>'
    if (original.count(header_start) != 1 or original.count(mode_start) != 1
            or original.count(home_start) != 1):
        raise ValueError("Pinned Chema mode/header anchors changed")
    header = original.split(header_start, 1)[1].split(header_end, 1)[0]
    mode = original.split(mode_start, 1)[1].split(mode_end, 1)[0]
    home = original.split(home_start, 1)[1].split('</section>', 1)[0]
    expected_logo = 'src="mark.svg"'
    if header.count(expected_logo) != 1:
        raise ValueError("Pinned Chema logo changed")
    header = header.replace(expected_logo, 'src="/urano/v1/entry/assets/mark.svg"')
    new_project = '<button class="btn primary" id="newVideo" data-go="mode">New project</button>'
    if header.count(new_project) != 1:
        raise ValueError("Pinned Chema header action changed")
    header = header.replace(new_project,
        '<button class="btn ghost small" id="ownerLogout" type="button">Sign out</button>')
    # Project button is inserted by the shared picker, not duplicated here.

    page = ('''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Montara · Stage, Push, Show</title>
<link rel="icon" href="/urano/v1/entry/assets/mark.svg" type="image/svg+xml">
<link rel="stylesheet" href="/urano/v1/entry/assets/montara.css">
<link rel="stylesheet" href="/urano/v1/entry/assets/push-pack.css">
<link rel="stylesheet" href="/urano/v1/entry/picker.css">
</head><body><header class="top">''' + header + '''</header>
<main><section class="screen" id="home">''' + home + '''</section>
<section class="screen" id="mode" hidden>''' + mode + '''</section>
<p class="hint" role="status" id="ownerMessage" aria-live="polite"></p></main>
<script src="/urano/v1/entry/picker.js"></script>
<script src="/urano/v1/entry.js"></script></body></html>''')

    bp = Blueprint("urano_owner_mode_entry", __name__)
    def allowed():
        if request.host_url.rstrip("/") != https_origin:
            abort(403)
        if sessions.verify(request.cookies.get(SESSION_COOKIE)) is None:
            abort(401)

    @bp.get("/urano/v1/entry")
    def entry():
        allowed()
        response = Response(page, content_type="text/html; charset=utf-8")
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "img-src 'self'; connect-src 'self'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'self'")
        return response

    @bp.get("/urano/v1/entry.js")
    def entry_js():
        allowed()
        return Response(SCRIPT, content_type="application/javascript; charset=utf-8")

    @bp.get("/urano/v1/entry/picker.js")
    @bp.get("/urano/v1/entry/picker.css")
    def picker_asset():
        allowed()
        name = "owner_project_picker.js" if request.path.endswith(".js") else "owner_project_picker.css"
        source = Path(__file__).with_name(name)
        response = Response(source.read_bytes(),
            mimetype="application/javascript" if name.endswith(".js") else "text/css")
        response.headers["Cache-Control"] = "private, no-store"
        return response

    @bp.get("/urano/v1/entry/assets/<filename>")
    def entry_asset(filename: str):
        allowed()
        if filename not in {"montara.css", "push-pack.css", "mark.svg"}:
            abort(404)
        path = root / filename
        if path.is_symlink() or not path.is_file():
            abort(404)
        from flask import send_from_directory
        response = send_from_directory(root, filename)
        response.headers["Cache-Control"] = "private, no-store"
        return response
    return bp
