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
const projectSection = document.querySelector('#ownerProjects');
const projectList = document.querySelector('#ownerProjectList');
const title = document.querySelector('#ownerProjectTitle');
const createButton = document.querySelector('#ownerCreate');
function notice(value) { message.textContent = value || ''; }
async function api(path, options={}) {
  const res = await fetch('/urano/v1/' + path, {credentials:'same-origin', cache:'no-store', ...options});
  const body = await res.json().catch(()=>({}));
  if (!res.ok) throw Error(body.error || 'La solicitud no está disponible');
  return body;
}
async function csrf() {
  const result = await api('session/refresh', {method:'POST', headers:{Origin:location.origin}});
  return result.csrf;
}
function openEditor(id) {
  if (!/^[0-9a-f-]{36}$/i.test(id)) throw Error('Identificador de proyecto inválido');
  location.assign('/urano/v1/editor/projects/' + encodeURIComponent(id) + '/');
}
function choices(kind) {
  document.querySelector('#intentChoices').hidden = kind !== 'root';
  document.querySelector('#videoChoices').hidden = kind !== 'video';
  document.querySelector('#musicChoices').hidden = kind !== 'music';
  document.querySelector('#modeQuestionBack').hidden = kind === 'root';
  document.querySelector('#modeQuestion').textContent =
    kind === 'video' ? 'What kind of video?' :
    kind === 'music' ? 'What does your music need?' : 'What would you like to make?';
}
async function stage() {
  modeSection.hidden = true;
  projectSection.hidden = false;
  notice('Cargando tus proyectos Stage…');
  try {
    const result = await api('editor/projects?mode=stage');
    projectList.replaceChildren();
    for (const project of result.projects) {
      const row = document.createElement('li');
      const button = document.createElement('button');
      button.type='button';
      button.className='btn ghost';
      button.textContent = project.title;
      button.addEventListener('click', () => openEditor(project.id));
      row.append(button);
      projectList.append(row);
    }
    notice(result.projects.length ? '' : 'Aún no tienes proyectos Stage.');
  } catch (error) { notice(error.message); }
}
document.querySelectorAll('[data-intent]').forEach(button => {
  button.addEventListener('click', () => choices(button.dataset.intent));
});
document.querySelector('#modeQuestionBack').addEventListener('click', ()=>choices('root'));
document.querySelectorAll('[data-platform]').forEach(button => {
  button.addEventListener('click', () => {
    if (button.dataset.platform === 'youtube') stage();
    else notice('Push y Show se conectarán después de la validación integral de Stage.');
  });
});
document.querySelectorAll('[data-audio-task]').forEach(button => {
  button.addEventListener('click', () => notice('El itinerario de audio se integrará después de Stage.'));
});
document.querySelector('#ownerBack').addEventListener('click', () => {
  projectSection.hidden=true; modeSection.hidden=false; choices('video'); notice('');
});
document.querySelector('#ownerShowProjects').addEventListener('click', stage);
document.querySelector('#ownerCreateForm').addEventListener('submit', async event => {
  event.preventDefault();
  createButton.disabled=true; notice('Creando proyecto privado…');
  try {
    const result = await api('editor/projects', {
      method:'POST',
      headers:{'Content-Type':'application/json','X-Urano-CSRF':await csrf(),Origin:location.origin},
      body:JSON.stringify({title:title.value,mode:'stage'})
    });
    openEditor(result.project.id);
  } catch (error) { notice(error.message); createButton.disabled=false; }
});
document.querySelector('#ownerLogout').addEventListener('click', async () => {
  try {
    await api('logout', {method:'POST', headers:{'X-Urano-CSRF':await csrf(), Origin:location.origin}});
    location.replace('/urano/v1/login');
  } catch (error) { notice(error.message); }
});
choices('root');
"""


def owner_mode_entry_blueprint(*, sessions: SessionStore, https_origin: str,
                               web_root: Path) -> Blueprint:
    root = Path(web_root).resolve(strict=True)
    original = (root / "index.html").read_text(encoding="utf-8")
    header_start = '<header class="top">'
    header_end = '</header>'
    mode_start = '<section class="screen" id="mode" hidden>'
    mode_end = '</section>'
    if (original.count(header_start) != 1 or original.count(mode_start) != 1):
        raise ValueError("Pinned Chema mode/header anchors changed")
    header = original.split(header_start, 1)[1].split(header_end, 1)[0]
    mode = original.split(mode_start, 1)[1].split(mode_end, 1)[0]
    expected_logo = 'src="mark.svg"'
    if header.count(expected_logo) != 1:
        raise ValueError("Pinned Chema logo changed")
    header = header.replace(expected_logo, 'src="/urano/v1/entry/assets/mark.svg"')
    new_project = '<button class="btn primary" id="newVideo" data-go="mode">New project</button>'
    if header.count(new_project) != 1:
        raise ValueError("Pinned Chema header action changed")
    header = header.replace(new_project,
        '<button class="btn ghost small" id="ownerLogout" type="button">Salir</button>')
    header = header.replace('</a>', '</a><button class="btn ghost small" id="ownerShowProjects" type="button">Mis proyectos</button>', 1)

    page = ('''<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Montara · Stage, Push, Show</title>
<link rel="icon" href="/urano/v1/entry/assets/mark.svg" type="image/svg+xml">
<link rel="stylesheet" href="/urano/v1/entry/assets/montara.css">
<link rel="stylesheet" href="/urano/v1/entry/assets/push-pack.css">
</head><body><header class="top">''' + header + '''</header>
<main><section class="screen" id="mode">''' + mode + '''</section>
<section class="screen" id="ownerProjects" hidden>
<h2>Mis proyectos · Stage</h2>
<p class="hint">Abre un proyecto existente o crea uno nuevo. El Engine se activa solo cuando haga falta.</p>
<ul id="ownerProjectList"></ul>
<form id="ownerCreateForm" class="actions">
<label>Nombre del proyecto <input id="ownerProjectTitle" maxlength="120" required placeholder="Nuevo proyecto Stage"></label>
<button class="btn primary" id="ownerCreate" type="submit">Crear Stage</button>
</form>
<button class="btn ghost" id="ownerBack" type="button">Volver a modalidades</button>
</section><p class="hint" role="status" id="ownerMessage" aria-live="polite"></p></main>
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
