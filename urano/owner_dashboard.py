"""Optional first browser surface for a verified owner's existing project catalog.

This is NOT the global Montara editor. Never exposes legacy single-user Engine,
filesystem paths, Google mocks, or an unverified owner identifier.
"""
from __future__ import annotations

from flask import Blueprint, Response, jsonify, request
from urano.session_auth import SESSION_COOKIE, SessionStore

PAGE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Montara · Mis proyectos</title>
<style>
:root{font-family:system-ui,-apple-system,sans-serif;color-scheme:dark;background:#101621;color:#eef3fa}
*{box-sizing:border-box}body{margin:0}header{padding:22px max(24px,calc((100vw - 960px)/2));border-bottom:1px solid #344054;display:flex;justify-content:space-between;align-items:center;gap:20px}
main{max-width:960px;margin:50px auto;padding:0 24px}h1{font-size:clamp(26px,5vw,42px);letter-spacing:-.04em}p{color:#b0bfd0}
button{cursor:pointer;color:inherit;background:#263749;border:1px solid #536780;padding:12px 17px;border-radius:10px;font:inherit}
button.primary{background:#e5eaf0;color:#121822;border-color:#e5eaf0}
form{display:flex;gap:10px;flex-wrap:wrap;margin:30px 0}
input{flex:1;min-width:220px;background:#1b2735;color:white;border:1px solid #64748b;padding:12px;border-radius:10px;font:inherit}
ul{list-style:none;padding:0;display:grid;gap:12px}li{padding:18px;border:1px solid #344054;border-radius:12px;background:#1a2635}
small{display:block;color:#a7b8ce;margin-top:7px}#status[role=alert]{color:#ffd49a}
</style></head>
<body data-engine-beta="__ENGINE_BETA__" data-original-editor="__ORIGINAL_JM__"><header><strong>MONTARA</strong><button id="logout" type="button">Cerrar sesión</button></header>
<main><h1>Mis proyectos</h1><p>Tu espacio privado. Cada proyecto pertenece a tu cuenta.</p>
<form id="create"><input id="title" maxlength="120" required aria-label="Nombre del proyecto" placeholder="Nombre del proyecto">
<button class="primary" type="submit">Crear proyecto</button></form>
<p id="status" role="alert" aria-live="polite"></p><ul id="projects" aria-label="Tus proyectos"></ul>
<p><small>Editor y render multiusuario en integración. Esta pantalla no abre el motor global.</small></p>
</main><script defer src="/urano/v1/dashboard.js"></script></body></html>"""

SCRIPT = """'use strict';
const status = document.querySelector('#status');
const list = document.querySelector('#projects');
async function api(path, options = {}) {
  const r = await fetch('/urano/v1/' + path, {credentials:'same-origin', cache:'no-store', ...options});
  const value = await r.json().catch(() => ({}));
  if (!r.ok) throw Error(value.error || 'Solicitud no disponible');
  return value;
}
async function load() {
  status.textContent = 'Cargando proyectos…';
  try {
    const {projects} = await api('projects');
    list.replaceChildren();
    for (const project of projects) {
      const li = document.createElement('li');
      const label = document.createElement('strong');
      label.textContent = project.title;
      const detail = document.createElement('small');
      detail.textContent = 'Proyecto privado · ' + project.id;
      li.append(label, detail);
      if (document.body.dataset.originalEditor === '1') {
        if (project.recipe?.montara_beta_workspace?.mode === 'stage') {
          const editorLink = document.createElement('a');
          editorLink.href = '/urano/v1/editor/projects/' + encodeURIComponent(project.id) + '/';
          editorLink.textContent = 'Abrir Stage';
          editorLink.className = 'editor-link';
          editorLink.style.cssText = 'display:inline-block;margin-top:14px;margin-right:12px;color:#ff9e80;font-weight:700';
          li.append(editorLink);
        } else {
          const note = document.createElement('small');
          note.textContent = 'Proyecto anterior conservado; no se convertirá automáticamente en Stage.';
          li.append(note);
        }
      } else if (document.body.dataset.engineBeta === '1') {
        const editorLink = document.createElement('a');
        editorLink.href = '/urano/v1/workspace?project=' + encodeURIComponent(project.id);
        editorLink.textContent = 'Entrar al estudio';
        editorLink.className = 'editor-link';
        editorLink.style.cssText = 'display:inline-block;margin-top:14px;margin-right:12px;color:#ff9e80;font-weight:700';
        li.append(editorLink);
      }
      if (document.body.dataset.engineBeta === '1' && document.body.dataset.originalEditor !== '1') {
        const open = document.createElement('button');
        open.textContent = 'Abrir Engine (beta)';
        open.type = 'button'; open.style.marginTop = '12px';
        open.addEventListener('click', async () => {
          open.disabled = true;
          status.textContent = 'Abriendo Engine aislado…';
          try {
            const result = await api('projects/' + encodeURIComponent(project.id) + '/open',
              {method:'POST',headers:{Origin:location.origin,'X-Urano-CSRF':await csrf()}});
            status.textContent = 'Engine abierto y verificado · generación ' + result.generation;
          } catch (e) { status.textContent = e.message; }
          finally { open.disabled = false; }
        });
        const close = document.createElement('button');
        close.textContent = 'Cerrar Engine';
        close.type = 'button'; close.style.marginLeft = '8px';
        close.addEventListener('click', async () => {
          close.disabled = true;
          try {
            await api('projects/' + encodeURIComponent(project.id) + '/close',
              {method:'POST',headers:{Origin:location.origin,'X-Urano-CSRF':await csrf()}});
            status.textContent = 'Engine cerrado correctamente';
          } catch (e) { status.textContent = e.message; }
          finally { close.disabled = false; }
        });
        li.append(open,close);
      }
      list.append(li);
    }
    status.textContent = projects.length ? '' : 'Todavía no tienes proyectos.';
  } catch (e) {
    status.textContent = e.message;
  }
}
async function csrf() {
  const token = await api('session/refresh', {method:'POST',headers:{Origin:location.origin}});
  return token.csrf;
}
document.querySelector('#create').addEventListener('submit', async event => {
  event.preventDefault();
  const title = document.querySelector('#title');
  const button = event.submitter; button.disabled = true;
  try {
    const pilot = document.body.dataset.originalEditor === '1';
    const created = await api(pilot ? 'editor/projects' : 'projects',{
      method:'POST',
      headers:{'Content-Type':'application/json','X-Urano-CSRF':await csrf(),Origin:location.origin},
      body:JSON.stringify(pilot ? {title:title.value,mode:'stage'} : {title:title.value}),
    });
    title.value = '';
    if (pilot) {
      location.assign('/urano/v1/editor/projects/' + encodeURIComponent(created.project.id) + '/');
      return;
    }
    await load();
  } catch (e) {status.textContent = e.message;} finally {button.disabled = false;}
});
document.querySelector('#logout').addEventListener('click', async () => {
  try {
    await api('logout',{method:'POST',headers:{'X-Urano-CSRF':await csrf()}});
    location.replace('/urano/v1/google/start');
  } catch (e) {status.textContent = e.message;}
});
load();"""


def owner_dashboard_blueprint(sessions: SessionStore, *, https_origin: str,
                              enable_engine_preview: bool = False,
                              original_jm_pilot: bool = False) -> Blueprint:
    bp = Blueprint("urano_owner_dashboard", __name__, url_prefix="/urano/v1")
    @bp.before_request
    def protect():
        if request.host_url.rstrip("/") != https_origin:
            return jsonify(error="Trusted HTTPS origin required"), 403
        if sessions.verify(request.cookies.get(SESSION_COOKIE)) is None:
            return jsonify(error="Authentication required"), 401

    @bp.get("/dashboard")
    def dashboard():
        response = Response(PAGE.replace("__ENGINE_BETA__","1" if enable_engine_preview else "0")
                            .replace("__ORIGINAL_JM__","1" if original_jm_pilot else "0"),
                            content_type="text/html; charset=utf-8")
        response.headers["Content-Security-Policy"] = "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @bp.get("/dashboard.js")
    def dashboard_js():
        response = Response(SCRIPT, content_type="application/javascript; charset=utf-8")
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    return bp
