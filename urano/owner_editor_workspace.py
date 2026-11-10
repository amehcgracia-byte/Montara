"""I28 private project workspace. Real recipe editing, no classic Engine proxy."""
from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

from urano.project_catalog import ProjectCatalog, ProjectNotFound
from urano.session_auth import SESSION_COOKIE, SessionStore

# Static assets are separate from private source; no script templating/user HTML.
PAGE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Montara · Estudio</title>
<link rel="stylesheet" href="/urano/v1/workspace.css"></head>
<body>
<header class="topbar"><a href="/urano/v1/dashboard" class="brand"><span class="logo-mark">M</span> MONTARA</a><span id="project-title" class="project-header">Cargando proyecto…</span><span class="envtag">BETA PRIVADA</span></header>
<nav class="steps" aria-label="Etapas"><span class="active">1 · Preparación</span><span>2 · Materiales</span><span>3 · Montaje</span><span>4 · Exportación</span></nav>
<main>
<aside class="sidebar"><div class="crumb">ESTUDIO · PROYECTO PRIVADO</div><h1>Tu proyecto,<br>tu montaje.</h1>
<p>Prepara el recorrido de edición. Las decisiones se guardan en tu cuenta de Montara.</p>
<section class="panel"><h2>Tipo de proyecto</h2>
<div role="radiogroup" class="mode-grid" aria-label="Modalidad">
<label><input type="radio" name="mode" value="stage"><strong>Stage</strong><small>Multicámara musical</small></label>
<label><input type="radio" name="mode" value="push"><strong>Push</strong><small>Vídeos cortos</small></label>
<label><input type="radio" name="mode" value="show"><strong>Show</strong><small>Historias y entrevistas</small></label>
</div></section>
<section class="panel"><h2>Formato de salida</h2><select id="format" aria-label="Formato">
<option value="landscape">Horizontal · 16:9</option><option value="portrait">Vertical · 9:16</option>
<option value="square">Cuadrado · 1:1</option></select></section>
<section class="panel"><h2>Notas de edición</h2><textarea id="notes" maxlength="5000" rows="6" placeholder="Describe el vídeo que quieres crear…"></textarea></section>
<button id="save" class="primary" type="button">Guardar cambios</button>
<p id="save-status" aria-live="polite" role="status" class="status">Sin cambios.</p>
<a class="back" href="/urano/v1/dashboard">← Volver a mis proyectos</a>
</aside>
<section class="studio" aria-label="Zona de edición">
<div class="stage-head"><div><div class="crumb">VISTA DE TRABAJO</div><h2>Montaje</h2></div><span id="engine-state" class="pill">Engine detenido</span></div>
<div class="viewer"><div class="empty-screen"><span class="play-mark">▶</span><strong>Aquí aparecerá tu vídeo</strong><small>La reproducción se activará cuando conectemos tus archivos mediante Companion.</small></div></div>
<div class="transport"><span>00:00 / 00:00</span><span>Vista previa pendiente de medios</span></div>
<div class="timeline"><div class="timeline-header"><h3>Guion de montaje</h3><button id="add-scene" class="outline" type="button">+ Añadir bloque</button></div>
<p class="muted">Organiza las ideas y el orden del vídeo. Aún no son clips multimedia.</p>
<ol id="scenes" aria-label="Bloques de montaje"></ol>
</div>
<div class="engine-controls"><div><strong>Engine aislado</strong><p>Puedes iniciar o cerrar el motor de este proyecto. El material original todavía no está conectado.</p></div>
<div class="actions"><button id="start-engine" class="outline" type="button">Abrir Engine</button><button id="stop-engine" class="outline" type="button">Cerrar Engine</button></div>
</div>
</section>
</main><script src="/urano/v1/workspace.js" defer></script>
</body></html>"""

CSS = r"""
:root{font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif;background:#0b0d12;color:#f5f5f6;color-scheme:dark}
*{box-sizing:border-box}body{margin:0}button,input,select,textarea{font:inherit}button{cursor:pointer}
a{color:inherit;text-decoration:none}.topbar{height:72px;border-bottom:1px solid #2b3038;display:flex;align-items:center;padding:0 32px;gap:28px;background:#11151b}
.brand{font-weight:800;letter-spacing:.13em;white-space:nowrap}.logo-mark{display:inline-grid;place-items:center;background:#f55334;color:#101016;width:30px;height:30px;border-radius:8px;margin-right:5px}
.project-header{flex:1;color:#a7acb8;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.envtag{font-size:11px;color:#ffa795;border:1px solid #824b3f;padding:8px 10px;border-radius:18px}
.steps{height:52px;display:flex;gap:35px;padding:0 32px;align-items:center;border-bottom:1px solid #252932;color:#777f8f;font-size:13px;overflow-x:auto;white-space:nowrap}
.steps .active{color:#ff755a}main{display:grid;grid-template-columns:minmax(310px,355px) minmax(0,1fr);min-height:calc(100vh - 124px)}
.sidebar{padding:32px 25px;border-right:1px solid #252932;background:#10141b}.crumb{font-size:11px;font-weight:700;letter-spacing:.16em;color:#ff8e73}.sidebar h1{font-size:32px;letter-spacing:-.04em;margin:12px 0}.sidebar>p{font-size:13px;color:#a1a7b1;line-height:1.6}
.panel{border-top:1px solid #303640;padding:22px 0}.panel h2{font-size:14px;margin:0 0 14px}.mode-grid{display:grid;gap:8px}
.mode-grid label{display:grid;grid-template-columns:18px 1fr;column-gap:10px;background:#1b222b;border:1px solid #35404c;border-radius:9px;padding:12px;cursor:pointer}
.mode-grid label:has(input:checked){border-color:#ff745c;background:#32231f}.mode-grid input{grid-row:span 2;accent-color:#ff6248}
.mode-grid strong{font-size:14px}.mode-grid small{font-size:12px;color:#a8b0bb}
select,textarea,.scene-input{width:100%;background:#1d2530;color:#fff;border:1px solid #46505e;border-radius:8px;padding:11px;outline-offset:2px}
textarea{resize:vertical;min-height:95px}button.primary{background:#f75f42;color:#15171d;border:0;border-radius:9px;padding:13px;width:100%;font-weight:750}
.status{font-size:12px;min-height:20px}.back{color:#b4b9c4;font-size:12px;display:inline-block;margin-top:16px}
.studio{padding:32px;min-width:0}.stage-head{display:flex;justify-content:space-between;align-items:center;gap:15px}.stage-head h2{font-size:28px;margin:8px 0 20px}.pill{border:1px solid #58616d;border-radius:99px;padding:8px 12px;font-size:12px;color:#b9c3cc}
.viewer{width:100%;aspect-ratio:16/9;background:#06080b;border:1px solid #343b47;border-radius:15px;display:grid;place-items:center;overflow:hidden;max-height:54vh}
.empty-screen{text-align:center;padding:25px;display:grid;gap:11px;justify-items:center}.empty-screen strong{font-size:19px}.empty-screen small{color:#8993a0;max-width:360px;line-height:1.5}
.play-mark{width:56px;height:56px;display:grid;place-items:center;border:1px solid #555b69;color:#f36a4b;border-radius:50%;margin-bottom:10px}
.transport{display:flex;justify-content:space-between;color:#8c95a2;font-size:12px;border-bottom:1px solid #343944;padding:14px 3px}
.timeline{padding-top:18px}.timeline-header{display:flex;justify-content:space-between;align-items:center;gap:12px}
.timeline h3{font-size:16px}.outline{border:1px solid #596575;color:#f0f0f0;background:#1e2530;border-radius:8px;padding:9px 13px}
.muted{color:#8f9ba8;font-size:13px}.timeline ol{list-style:none;display:grid;gap:8px;padding:0}
.scene-row{display:flex;gap:8px;align-items:center;padding:8px 10px;background:#1d2631;border:1px solid #3b4654;border-radius:9px}
.scene-row .scene-number{color:#f38368;font-size:12px;min-width:22px}.scene-row input{flex:1;min-width:0}
.scene-row button{background:transparent;color:#bbc3ce;border:0;font-size:16px;padding:5px 9px}
.engine-controls{margin-top:26px;padding:20px;border:1px solid #3c4450;border-radius:12px;display:flex;gap:15px;align-items:center;justify-content:space-between}
.engine-controls p{font-size:12px;color:#9ea6b2;line-height:1.5;margin-bottom:0}.actions{display:flex;gap:9px;flex-wrap:wrap}
button:disabled{opacity:.5;cursor:not-allowed}
@media(max-width:820px){main{grid-template-columns:1fr}.sidebar{border-right:0;border-bottom:1px solid #252932}.studio{padding:20px}.topbar{padding:0 16px;gap:12px}.envtag{display:none}.steps{padding:0 17px;gap:18px}.engine-controls{display:block}.actions{margin-top:16px}}
"""

JS = r"""'use strict';
const status = document.getElementById('save-status');
const engineState = document.getElementById('engine-state');
const save = document.getElementById('save');
const scenes = document.getElementById('scenes');
const title = document.getElementById('project-title');
const modeButtons = [...document.querySelectorAll('input[name=mode]')];
const params = new URLSearchParams(location.search);
const projectId = params.get('project');
if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(projectId||'')) {
  location.replace('/urano/v1/dashboard');
}
let project=null, original={}, blocks=[];
const api = async (path, options={}) => {
  const r=await fetch('/urano/v1/'+path,{credentials:'same-origin',cache:'no-store',...options});
  const result=await r.json().catch(()=>({}));
  if (!r.ok) throw Error(result.error||'Error de comunicación');
  return result;
};
async function csrf(){
  const result=await api('session/refresh',{method:'POST',headers:{Origin:location.origin}});
  return result.csrf;
}
function getMode(){return modeButtons.find(x=>x.checked)?.value||'stage';}
function drawBlocks(){
  scenes.replaceChildren();
  blocks.forEach((b,i)=>{
    const li=document.createElement('li');li.className='scene-row';
    const number=document.createElement('span');number.className='scene-number';number.textContent=String(i+1).padStart(2,'0');
    const input=document.createElement('input');input.className='scene-input';input.maxLength=180;input.value=b;
    input.setAttribute('aria-label','Bloque '+(i+1));
    input.addEventListener('input',()=>{blocks[i]=input.value;status.textContent='Cambios sin guardar';});
    const rm=document.createElement('button');rm.type='button';rm.textContent='×';rm.title='Eliminar bloque';
    rm.setAttribute('aria-label','Eliminar bloque '+(i+1));
    rm.addEventListener('click',()=>{blocks.splice(i,1);drawBlocks();status.textContent='Cambios sin guardar';});
    li.append(number,input,rm);scenes.append(li);
  });
}
async function load(){
  try {
    const data=await api('projects/'+encodeURIComponent(projectId));
    project=data.project;
    original=structuredClone(project.recipe||{});
    const work=original.montara_beta_workspace||{};
    title.textContent=project.title;
    (modeButtons.find(x=>x.value===(work.mode||'stage'))||modeButtons[0]).checked=true;
    document.getElementById('format').value=work.format||'landscape';
    document.getElementById('notes').value=work.notes||'';
    blocks=Array.isArray(work.blocks)?work.blocks.filter(x=>typeof x==='string').slice(0,30):[];
    drawBlocks();
    status.textContent='Proyecto cargado · revisión '+project.revision;
  } catch(e){status.textContent=e.message;save.disabled=true;}
}
save.addEventListener('click',async()=>{
  if (!project)return;
  save.disabled=true;status.textContent='Guardando configuración…';
  try {
    const recipe={...original,montara_beta_workspace:{
      version:1,mode:getMode(),format:document.getElementById('format').value,
      notes:document.getElementById('notes').value,blocks:blocks.slice(0,30)
    }};
    const reply=await api('projects/'+encodeURIComponent(projectId)+'/recipe',{
      method:'PUT',headers:{'Content-Type':'application/json','X-Urano-CSRF':await csrf()},
      body:JSON.stringify({recipe,expected_revision:project.revision})
    });
    project=reply.project;original=structuredClone(project.recipe||{});
    status.textContent='Guardado en Montara · revisión '+project.revision;
  } catch(e){status.textContent=e.message+' · Recarga para recuperar los últimos cambios';}
  finally{save.disabled=false;}
});
document.getElementById('add-scene').addEventListener('click',()=>{
  if(blocks.length>=30){status.textContent='Máximo 30 bloques';return;}
  blocks.push('Nuevo bloque');drawBlocks();status.textContent='Cambios sin guardar';
});
const format=document.getElementById('format');
[format,document.getElementById('notes'),...modeButtons].forEach(el=>el.addEventListener('change',()=>{
  status.textContent='Cambios sin guardar';
}));
async function engine(op){
  const button=document.getElementById(op==='open'?'start-engine':'stop-engine');
  button.disabled=true;engineState.textContent=op==='open'?'Abriendo Engine…':'Cerrando Engine…';
  try{
    const result=await api('projects/'+encodeURIComponent(projectId)+'/'+op,{
      method:'POST',headers:{Origin:location.origin,'X-Urano-CSRF':await csrf()}
    });
    engineState.textContent=op==='open'?'Engine activo · gen. '+result.generation:'Engine detenido';
  }catch(e){engineState.textContent='Engine: '+e.message;}
  finally{button.disabled=false;}
}
document.getElementById('start-engine').addEventListener('click',()=>engine('open'));
document.getElementById('stop-engine').addEventListener('click',()=>engine('close'));
load();
"""


def workspace_blueprint(catalog: ProjectCatalog, sessions: SessionStore,
                        *, https_origin: str) -> Blueprint:
    bp = Blueprint("urano_i28_owner_workspace",__name__,url_prefix="/urano/v1")

    @bp.before_request
    def authenticate():
        if request.host_url.rstrip("/")!=https_origin:
            return jsonify(error="Trusted HTTPS origin required"),403
        if sessions.verify(request.cookies.get(SESSION_COOKIE)) is None:
            return jsonify(error="Authentication required"),401

    def response(content, mime):
        out=Response(content,content_type=mime)
        out.headers["Cache-Control"]="no-store"
        out.headers["X-Content-Type-Options"]="nosniff"
        return out

    @bp.get("/workspace")
    def workspace():
        owner=sessions.verify(request.cookies.get(SESSION_COOKIE)).owner_id
        project_id=request.args.get("project","")
        try:
            catalog.get(owner,project_id)
        except (ValueError,ProjectNotFound):
            return jsonify(error="Project not found"),404
        out=response(PAGE,"text/html; charset=utf-8")
        out.headers["Content-Security-Policy"]=(
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        out.headers["X-Frame-Options"]="DENY"
        return out

    @bp.get("/workspace.css")
    def css():
        return response(CSS,"text/css; charset=utf-8")

    @bp.get("/workspace.js")
    def javascript():
        return response(JS,"application/javascript; charset=utf-8")

    return bp

