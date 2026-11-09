"""Optional first browser surface for a verified owner's existing project catalog.

This is NOT the global Montara editor. Never exposes legacy single-user Engine,
filesystem paths, Google mocks, or an unverified owner identifier.
"""
from __future__ import annotations

from pathlib import Path
from flask import Blueprint, Response, jsonify, request
from urano.session_auth import SESSION_COOKIE, SessionStore
from urano.project_catalog import ProjectCatalog, ProjectNotFound

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
<body><header><strong>MONTARA</strong><button id="logout" type="button">Cerrar sesión</button></header>
<main><h1>Mis proyectos</h1><p>Tu espacio privado. Cada proyecto pertenece a tu cuenta.</p>
<form id="create"><input id="title" maxlength="120" required aria-label="Nombre del proyecto" placeholder="Nombre del proyecto">
<button class="primary" type="submit">Crear proyecto</button></form>
<p id="status" role="alert" aria-live="polite"></p><ul id="projects" aria-label="Tus proyectos"></ul>
<p><small>Motor privado Stage en integración. Esta pantalla nunca abre el motor global.</small></p>
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
      if (window.MONTARA_PRIVATE_RUNTIME) {
        const link = document.createElement('a'); link.href = '/urano/v1/workspace/' + encodeURIComponent(project.id);
        link.textContent = 'Abrir espacio de trabajo privado';
        link.style.cssText = 'display:inline-block;color:#d8e9ff;margin-top:12px';
        li.append(link);
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
    await api('projects',{method:'POST',headers:{'Content-Type':'application/json','X-Urano-CSRF':await csrf()},
      body:JSON.stringify({title:title.value})});
    title.value = ''; await load();
  } catch (e) {status.textContent = e.message;} finally {button.disabled = false;}
});
document.querySelector('#logout').addEventListener('click', async () => {
  try {
    await api('logout',{method:'POST',headers:{'X-Urano-CSRF':await csrf()}});
    location.replace('/urano/v1/google/start');
  } catch (e) {status.textContent = e.message;}
});
load();"""


WORKSPACE_PAGE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Montara · Espacio privado</title>
<style>
:root{font-family:system-ui,-apple-system,sans-serif;color-scheme:dark;background:#101621;color:#eef3fa}
body{max-width:820px;margin:55px auto;padding:0 24px}a{color:#bfdcff}h1{font-size:clamp(25px,5vw,40px)}
button{font:inherit;cursor:pointer;background:#e5eaf0;color:#121822;border:0;border-radius:10px;padding:12px 16px;margin:6px 8px 6px 0}
button:disabled{opacity:.5;cursor:not-allowed}p,small{color:#b0bfd0}#status[role=alert]{color:#ffd49a}section{margin-top:30px;border-top:1px solid #344054;padding-top:18px}form{display:flex;flex-wrap:wrap;align-items:end;gap:12px}label{display:grid;gap:6px}input{width:145px;padding:9px;color:#eef3fa;background:#1a2635;border:1px solid #64748b;border-radius:8px;font:inherit}ol{line-height:1.9}
</style></head><body><a href="/urano/v1/dashboard">← Mis proyectos</a>
<h1 id="name">Espacio de trabajo privado</h1>
<p>Stage y Engine aislados para este proyecto. El editor visual y la exportación local se conectarán después.</p>
<p id="status" role="alert" aria-live="polite">Comprobando...</p>
<button id="activate" type="button">Activar Engine privado</button>
<button id="ingest" type="button" disabled>Iniciar Stage</button>
<button id="refresh" type="button">Actualizar estado</button>
<section aria-label="Cortes del proyecto"><h2>Plan de cortes privado</h2>
<p>Prepara un corte básico por cámara. Los originales permanecen en tu ordenador; esto aún no es el editor visual definitivo.</p>
<form id="edit-cuts">
<label>Cámara (0–15) <input id="slot" type="number" min="0" max="15" step="1" value="0" required></label>
<label>Desde (segundos) <input id="start" type="number" min="0" step=".001" value="0" required></label>
<label>Hasta (segundos) <input id="end" type="number" min=".001" step=".001" value="5" required></label>
<button type="submit">Guardar corte</button></form>
<p id="edits-status" role="status" aria-live="polite"></p>
<ol id="cuts" aria-label="Cortes guardados"></ol>
<h3>Originales en este ordenador</h3>
<p>Selecciona los mismos vídeos originales utilizados en el proyecto, en el orden de cámaras. Solo se consultará a Companion en tu ordenador.</p>
<input id="local-originals" type="file" accept="video/*,.mov,.mp4,.mkv,.mts,.m4v,.avi,.webm" multiple>
<button id="verify-originals" type="button">Verificar originales en Companion</button>
<button id="prepare-private-proxies" type="button" disabled>Preparar proxies para Stage privado (sin certificar)</button>
<p id="proxy-inbox-status" role="status" aria-live="polite"></p>
<p id="originals-status" role="status" aria-live="polite"></p>
<button id="handoff" type="button">Comprobar descriptor para Companion</button>
<p id="handoff-status" role="status" aria-live="polite"></p>
<h3>Exportación local de prueba</h3>
<p>Solo para cortes básicos. La exportación se bloqueará si Stage no ha registrado de forma fiable la identidad de cada proxy y su vídeo original.</p>
<label>Audio maestro WAV <input id="master-audio" type="file" accept=".wav,audio/wav,audio/x-wav" /></label>
<button id="export-local" type="button">Exportar MP4 en Companion</button>
<p id="export-status" role="status" aria-live="polite"></p>
<a id="export-download" hidden>Descargar MP4 local</a>
</section>
<script defer src="/urano/v1/companion-client.js"></script>
<script defer src="/urano/v1/workspace.js"></script></body></html>"""

WORKSPACE_SCRIPT = """'use strict';
const projectId = decodeURIComponent(location.pathname.split('/').pop());
const status = document.querySelector('#status');
const activate = document.querySelector('#activate');
const ingest = document.querySelector('#ingest');
const refresh = document.querySelector('#refresh');
async function api(path, options={}) {
  const response = await fetch('/urano/v1/' + path, {credentials:'same-origin',cache:'no-store',...options});
  const body = await response.json().catch(() => ({}));
  if(!response.ok) throw Error(body.error || 'Operación no disponible');
  return body;
}
async function csrf() {
  const {csrf} = await api('session/refresh',{method:'POST',headers:{Origin:location.origin}});
  return csrf;
}
async function update() {
  try {
    const project = await api('projects/' + encodeURIComponent(projectId));
    document.querySelector('#name').textContent = project.project.title;
    const state = await api('runtime/projects/' + encodeURIComponent(projectId) + '/state');
    status.textContent = 'Este proyecto: ' + state.state;
    ingest.disabled = !state.can_start_ingest;
  } catch(e) {status.textContent=e.message;ingest.disabled=true;}
}
async function run(path) {
  activate.disabled=true;ingest.disabled=true;refresh.disabled=true;
  try {
    await api(path,{method:'POST',headers:{'X-Urano-CSRF':await csrf(),Origin:location.origin}});
    await update();
  } catch(e){status.textContent=e.message;}
  finally {activate.disabled=false;refresh.disabled=false;}
}
activate.addEventListener('click',()=>run('runtime/projects/'+encodeURIComponent(projectId)+'/activate'));
ingest.addEventListener('click',()=>run('runtime/projects/'+encodeURIComponent(projectId)+'/ingest'));
refresh.addEventListener('click',async ()=>{
  try {
    const x=await api('runtime/projects/'+encodeURIComponent(projectId)+'/ingest');
    status.textContent='Stage: '+x.status;
  } catch(e) {await update();}
});
let revision = null;
let cuts = [];
let verifiedOriginals = null;
const exportButton = document.querySelector('#export-local');
const editStatus = document.querySelector('#edits-status');
function drawCuts() {
  const container = document.querySelector('#cuts');
  container.replaceChildren();
  cuts.forEach((cut, index) => {
    const li = document.createElement('li');
    li.textContent = 'Corte '+(index+1)+': cámara '+cut.source_slot+
      ' · '+(cut.start_ms/1000)+'–'+(cut.end_ms/1000)+' s';
    container.append(li);
  });
}
async function loadEdits() {
  const response = await api('projects/'+encodeURIComponent(projectId));
  revision = response.project.revision;
  const saved = response.project.recipe?.urano_edits_v1?.cuts;
  cuts = Array.isArray(saved) ? saved : [];
  drawCuts();
  editStatus.textContent = cuts.length ? 'Plan guardado · revisión '+revision : 'Todavía no hay cortes guardados.';
}
document.querySelector('#edit-cuts').addEventListener('submit',async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('button');
  button.disabled = true;
  try {
    if (revision === null) throw Error('El proyecto no está listo');
    const slot = Number(document.querySelector('#slot').value);
    const start_ms = Math.round(Number(document.querySelector('#start').value)*1000);
    const end_ms = Math.round(Number(document.querySelector('#end').value)*1000);
    if (!Number.isInteger(slot) || slot<0 || slot>15 ||
        !Number.isSafeInteger(start_ms) || !Number.isSafeInteger(end_ms) ||
        start_ms<0 || end_ms<=start_ms) throw Error('Comprueba los tiempos y la cámara');
    const response = await api('runtime/projects/'+encodeURIComponent(projectId)+'/edits',{
      method:'PUT', headers:{'Content-Type':'application/json','X-Urano-CSRF':await csrf(),'Origin':location.origin},
      body:JSON.stringify({expected_revision:revision,cuts:[...cuts,{source_slot:slot,start_ms,end_ms}]})
    });
    revision = response.revision;
    cuts = response.cuts;
    verifiedOriginals = null;
    drawCuts(); editStatus.textContent='Corte guardado · revisión '+revision;
    document.querySelector('#originals-status').textContent='Los cortes cambiaron. Vuelve a verificar los originales.';
  } catch(e) {
    editStatus.textContent=e.message; await loadEdits().catch(()=>{});
  } finally {button.disabled=false;}
});
document.querySelector('#handoff').addEventListener('click', async () => {
  const target = document.querySelector('#handoff-status');
  try {
    const result = await api('runtime/projects/'+encodeURIComponent(projectId)+'/companion-handoff');
    if (result.plan.render_ready !== false || result.plan.local_source_resolution_verified !== false)
      throw Error('Estado de seguridad inesperado');
    target.textContent='Descriptor validado: '+result.plan.cuts.length+
      ' cortes. Companion debe reconocer los originales locales antes de exportar.';
  } catch(e){target.textContent=e.message;}
});
document.querySelector('#verify-originals').addEventListener('click',async event => {
  verifiedOriginals = null;
  const button=event.currentTarget;
  const target=document.querySelector('#originals-status');
  const files=[...document.querySelector('#local-originals').files];
  if(!files.length){target.textContent='Selecciona al menos un original';return;}
  button.disabled=true;
  try {
    if(typeof montaraCompanion==='undefined') throw Error('Companion no está disponible');
    const used = [...new Set(cuts.map(c=>c.source_slot))].sort((a,b)=>a-b);
    if (!used.length) throw Error('Guarda primero un plan de cortes');
    if (used.length !== files.length) throw Error('Selecciona exactamente un original por cámara usada ('+used.join(', ')+')');
    const mapping = [];
    for(let i=0;i<files.length;i++){
      const result=await montaraCompanion.verifyLocalOriginal(files[i]);
      if(!result.located) throw Error('Companion no encuentra el original de cámara '+used[i]+': '+files[i].name);
      mapping.push({source:used[i],original:result.identity});
    }
    // The browser is NOT allowed to attest proxy provenance. Trust only
    // read-only, owner-bound identities recorded during trusted Stage ingest.
    const cert=await api('runtime/projects/'+encodeURIComponent(projectId)+'/verified-sources');
    if(cert.project_revision!==revision || !/^[a-f0-9]{64}$/.test(cert.stage_revision || ''))
      throw Error('El manifiesto de Stage no corresponde a esta revisión');
    if(!Array.isArray(cert.sources) || cert.sources.length!==mapping.length)
      throw Error('Los originales no coinciden con las fuentes certificadas de Stage');
    for(let i=0;i<mapping.length;i++){
      const trusted=cert.sources[i];
      const local=mapping[i];
      if(trusted.source_slot!==local.source ||
        trusted.original.name!==local.original.name ||
        trusted.original.size!==local.original.size ||
        trusted.original.fingerprint!==local.original.fingerprint)
        throw Error('La cámara '+local.source+' no corresponde al original certificado por Stage');
    }
    verifiedOriginals = {revision, stage_revision:cert.stage_revision, mapping};
    target.textContent='Companion y Stage coinciden en '+mapping.length+' original(es) certificados.';
  }catch(e){target.textContent=e.message;}
  finally{button.disabled=false;}
});
async function runLocalExport() {
  const target = document.querySelector('#export-status');
  const download = document.querySelector('#export-download');
  download.hidden = true;download.removeAttribute('href');
  exportButton.disabled = true;
  try {
    if (!verifiedOriginals || verifiedOriginals.revision !== revision)
      throw Error('Verifica los originales de este plan antes de exportar');
    const cert=await api('runtime/projects/'+encodeURIComponent(projectId)+'/verified-sources');
    const sourceMatches = Array.isArray(cert.sources) &&
      cert.sources.length === verifiedOriginals.mapping.length &&
      verifiedOriginals.mapping.every((item,i)=>{
        const trusted=cert.sources[i];
        return trusted?.source_slot===item.source &&
          trusted.original?.name===item.original.name &&
          trusted.original?.size===item.original.size &&
          trusted.original?.fingerprint===item.original.fingerprint;
      });
    if(cert.project_revision !== verifiedOriginals.revision ||
       cert.stage_revision !== verifiedOriginals.stage_revision || !sourceMatches)
      throw Error('La procedencia de Stage ha cambiado. Vuelve a verificar los originales');
    const audio = document.querySelector('#master-audio').files?.[0];
    if (!audio || !/\\.wav$/i.test(audio.name) || audio.size<=0 || audio.size>1024*1024*1024)
      throw Error('Selecciona un archivo WAV maestro de hasta 1 GB');
    const result = await api('runtime/projects/'+encodeURIComponent(projectId)+'/companion-handoff');
    const plan = result.plan;
    if (plan.project_revision !== revision || plan.render_ready !== false ||
        plan.local_source_resolution_verified !== false || !Array.isArray(plan.cuts) ||
        JSON.stringify(plan.cuts) !== JSON.stringify(cuts))
      throw Error('El plan ha cambiado o no es seguro. Recarga los cortes');
    const used = [...new Set(cuts.map(c=>c.source_slot))].sort((a,b)=>a-b);
    if (JSON.stringify(used)!==JSON.stringify(verifiedOriginals.mapping.map(x=>x.source)))
      throw Error('Cámaras sin originales verificados');
    if (!await montaraCompanion.detect() || !montaraCompanion.info?.local_video)
      throw Error('Instala o actualiza Companion con renderizador local');
    // The folder picker and master transfer stay on this person's computer.
    const folder = await montaraCompanion.projectFolder('Montara beta local', []);
    if (!folder?.id) throw Error('Selecciona una carpeta local en Companion');
    const masterName='montara-render-audio-'+crypto.randomUUID().replaceAll('-','')+'.audio';
    target.textContent='Guardando audio maestro únicamente en Companion…';
    await montaraCompanion.saveInProject(folder.id,masterName,audio);
    const payload={plan,project:folder.id,master:masterName,
      originals:verifiedOriginals.mapping,name:'Montara beta local',branding:'none'};
    target.textContent='Renderizando MP4 en este ordenador…';
    const id = await montaraCompanion.startHandoffVideo(payload);
    for(let n=0;n<600;n++){
      const state=await montaraCompanion.videoStatus(id);
      if(state.status==='ready'){
        const url=montaraCompanion.videoUrl(id,true);
        download.href=url;
        download.textContent='Descargar MP4 terminado en Companion';
        download.hidden=false;
        target.textContent='MP4 generado localmente. Verifica el resultado antes de utilizarlo.';
        return;
      }
      if(state.status==='failed' || state.status==='cancelled')
        throw Error(state.error || 'El render local no terminó');
      await new Promise(resolve=>setTimeout(resolve,1000));
    }
    throw Error('No se ha confirmado la finalización del render. Revisa Companion.');
  }catch(e){target.textContent=e.message;}
  finally{exportButton.disabled=false;}
}
exportButton.addEventListener('click',runLocalExport);
document.querySelector('#local-originals').addEventListener('change',()=>{verifiedOriginals=null;});
const proxyButton=document.querySelector('#prepare-private-proxies');
proxyButton.disabled = !window.MONTARA_PROXY_INBOX;
proxyButton.addEventListener('click',async()=>{
  const target=document.querySelector('#proxy-inbox-status');
  const files=[...document.querySelector('#local-originals').files];
  const slots=[...new Set(cuts.map(c=>c.source_slot))].sort((a,b)=>a-b);
  proxyButton.disabled=true;
  try {
    if(!window.MONTARA_PROXY_INBOX) throw Error('La entrada privada de Stage no está activada');
    if(!files.length || files.length!==slots.length)
      throw Error('Selecciona un vídeo original por cada cámara del plan');
    if(!await montaraCompanion.detect()) throw Error('Companion no está disponible');
    for(let i=0;i<files.length;i++){
      if(!montaraCompanion.isVideo(files[i])) throw Error('Solo se admiten vídeos originales');
      target.textContent='Preparando proxy de cámara '+slots[i]+' en Companion…';
      const small=await montaraCompanion.smallVersion(files[i],()=>{},()=>false);
      if(!small?.file || !small?.provenance_receipt)
        throw Error('Companion no pudo crear un proxy verificable');
      await montaraCompanion.stagePrivateProxy(projectId,slots[i],small,await csrf());
    }
    target.textContent='Proxies recibidos en el proyecto privado. Pendientes de validación por Stage; aún no certificados.';
  }catch(e){target.textContent=e.message;}
  finally{proxyButton.disabled=!window.MONTARA_PROXY_INBOX;}
});
update();
loadEdits().catch(e=>{editStatus.textContent=e.message;});"""

def owner_dashboard_blueprint(sessions: SessionStore, *, https_origin: str,
                              catalog: ProjectCatalog | None = None,
                              runtime_available: bool = False,
                              proxy_inbox_available: bool = False) -> Blueprint:
    bp = Blueprint("urano_owner_dashboard", __name__, url_prefix="/urano/v1")
    @bp.before_request
    def protect():
        if request.host_url.rstrip("/") != https_origin:
            return jsonify(error="Trusted HTTPS origin required"), 403
        if sessions.verify(request.cookies.get(SESSION_COOKIE)) is None:
            return jsonify(error="Authentication required"), 401

    @bp.get("/dashboard")
    def dashboard():
        response = Response(PAGE, content_type="text/html; charset=utf-8")
        response.headers["Content-Security-Policy"] = "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @bp.get("/dashboard.js")
    def dashboard_js():
        response = Response("window.MONTARA_PRIVATE_RUNTIME = " + ("true" if runtime_available else "false") + ";\n" + SCRIPT,
                            content_type="application/javascript; charset=utf-8")
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    if runtime_available:
        if catalog is None:
            raise ValueError("Workspace requires existing owner project catalog")

        @bp.get("/workspace/<project_id>")
        def workspace(project_id: str):
            identity = sessions.verify(request.cookies.get(SESSION_COOKIE))
            try:
                project = catalog.get(identity.owner_id, project_id)
            except (ProjectNotFound, ValueError):
                return jsonify(error="Project not found"), 404
            response = Response(WORKSPACE_PAGE, content_type="text/html; charset=utf-8")
            response.headers["Content-Security-Policy"] = "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self' http://127.0.0.1:47820; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response

        @bp.get("/companion-client.js")
        def companion_client():
            # Read the one existing client implementation. Do not fork it into a
            # separate editor: this endpoint only serves the authenticated page.
            client_path = Path(__file__).resolve().parents[1] / "web" / "companion.js"
            response = Response(client_path.read_text(encoding="utf-8"),
                                content_type="application/javascript; charset=utf-8")
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response

        @bp.get("/workspace.js")
        def workspace_js():
            response = Response("window.MONTARA_PROXY_INBOX = " + ("true" if proxy_inbox_available else "false") + ";\n" + WORKSPACE_SCRIPT,
                                content_type="application/javascript; charset=utf-8")
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response
    return bp
