"use strict";
const showEditor = { selected:null, undo:[], redo:[], busy:false, project:null };
const SHOW_EFFECT_NAMES = {word:"Text",drawing:"Image",clip:"Video",background:"Background",warp:"Wave / distortion",math:"Formulas",steam:"Smoke",texture:"Texture",jingle:"Audio",cutaway:"Close-up",character:"Speaking image",overlay:"Image / character"};
function showSceneItems(scene) {
  return [
    ...showEdit.proposals.filter(p => (scene.effects || []).includes(p.id)).map(p => ({id:p.id,type:"proposal",kind:p.kind,at:p.at,duration:p.duration,params:p.params || {},raw:p})),
    ...(scene.overlays || []).map(p => ({id:p.id,type:"overlay",kind:"overlay",at:p.at,duration:p.duration,params:p,raw:p}))
  ];
}
function showItemName(item) { return item.params.text || item.params.name || item.params.subject || (item.kind === "overlay" ? (item.params.asset || "").split("/").slice(-2,-1)[0] : "") || SHOW_EFFECT_NAMES[item.kind] || "Effect"; }
function renderShowEffectRows(scene) {
  const items = showSceneItems(scene).filter(item=>item.raw.status!=="discarded");
  $("#showSceneEffects").innerHTML = items.length ? items.map(item => `<div class="show-effect-row" data-edit-row="${escapeHtml(item.id)}"><span>${escapeHtml(SHOW_EFFECT_NAMES[item.kind] || "Effect")}${item.type === "proposal" ? `<input type="checkbox" aria-label="Keep ${escapeHtml(showItemName(item))}" data-show-effect="${escapeHtml(item.id)}" ${item.raw.status !== "discarded" ? "checked" : ""} ${(item.raw.needs || []).length ? "disabled" : ""}>` : ""}</span><button type="button" class="link" data-edit-effect="${escapeHtml(item.id)}">Edit effect</button><small>${escapeHtml(showItemName(item))} · ${(item.at-scene.start).toFixed(1)}s${(item.raw.needs || []).length ? " · Needs setup" : ""}</small></div>`).join("") : '<p class="hint">Add effects from the video or the transcript.</p>';
  $("#showCleanScene").hidden = !items.length;
}
function applyShowEditorData(data,sceneId){
  const old=new Map(showEdit.proposals.map(p=>[p.id,p]));
  showEdit.scenes=data.scenes||[];showEdit.proposals=(data.proposals||[]).map(p=>{const prior=old.get(p.id)||old.get(p.params?.group);return prior?{...p,params:{...prior.params,...p.params}}:p;});
  showEdit.source=data.source;showEdit.sourceUrl=data.source_url;showEdit.resources=data.resources||[];
  if(data.timeline)showEdit.timelineCache=data.timeline;
  if(data.narrator)showEdit.narratorCache=data.narrator;
  const index=showEdit.scenes.findIndex(s=>s.id===sceneId);showEdit.selected=index>=0?index:Math.max(0,Math.min(showEdit.selected,showEdit.scenes.length-1));
}
async function refreshShowEditor(sceneId,render=true){
  cancelShowAutoPreview();const offset=showPlaybackOffset();const data=await api('/montara/show/editor');applyShowEditorData(data,sceneId);
  showPlaybackState.cache.clear();if(render){showEdit.seekAfterEdit=offset;showPlaybackState.liveEditing=true;renderShowScene();scheduleShowAutoPreview();}
}
function showHistoryButtons(){ $('#showUndoEdit').disabled=!showEditor.undo.length;$('#showRedoEdit').disabled=!showEditor.redo.length;}
function showPushUndo(entry){showEditor.undo.push({...entry,project:state.projectId});if(showEditor.undo.length>30)showEditor.undo.shift();showEditor.redo=[];showHistoryButtons();}
function inverseShowEdit(entry){
  if(entry.type==='cut')return null;
  if(entry.type==='batch')return {...entry,entries:entry.entries.map(inverseShowEdit).reverse()};
  const scene=showEdit.scenes.find(s=>s.id===entry.sceneId);
  if(entry.type==='overlay')return {...entry,overlays:structuredClone(scene?.overlays||[])};
  const raw=showEdit.proposals.find(p=>p.id===entry.id),p=raw?.params||{};const changes={};for(const key of Object.keys(entry.changes||{}))changes[key]=structuredClone(raw?.[key]??p[key]??entry.changes[key]);
  return {...entry,changes,...(entry.type==='clip'?{settings:{clip_start:p.clip_start||0,matte:p.matte||'none',audio_mode:p.audio_mode||'own',clip_audio:p.clip_audio!==false}}:{})};
}
async function saveShowOverlays(sceneId, overlays, undo = true) {
  const current = await api("/show/scenes"); const scene = current.scenes.find(s => s.id === sceneId);
  if(!scene) throw new Error("This part no longer exists.");
  const before = structuredClone(scene.overlays || []);
  await api(`/show/scenes/${encodeURIComponent(sceneId)}/overlays`, {overlays});
  if(undo) showPushUndo({type:"overlay",sceneId,overlays:before});
}
async function changeShowProposal(item, changes, sceneId, undo=true) {
  const before = {};
  const defaultPosition=typeof liveShape === "function"?liveShape(item):{left:21,top:42};
  const defaults={rotate:0,stretch:1,stretch_x:1,opacity:1,crop:[0,0,0,0],person_scale:1,person_offset:[0,0],image_center:[defaultPosition.left/100,defaultPosition.top/100]};
  for(const key of Object.keys(changes)) before[key] = key in item.raw ? item.raw[key] : item.params[key] ?? defaults[key] ?? changes[key];
  if(item.kind==='jingle' && ('volume' in changes || 'under_voice' in changes)){
    await showPatch(`/show/audio/tracks/${encodeURIComponent(item.id)}`,{project_id:state.projectId,volume:Number(changes.volume ?? item.params.volume ?? .28),mode:'mix',under_voice:changes.under_voice === undefined ? item.params.under_voice!==false : String(changes.under_voice)==='true'});
    const timing={...changes};delete timing.volume;delete timing.under_voice;
    if(Object.keys(timing).length)await showPatch(`/show/review/${encodeURIComponent(item.id)}`,timing);
  }else await showPatch(`/show/review/${encodeURIComponent(item.id)}`,changes);
  if(undo) showPushUndo({type:"proposal",id:item.id,changes:before,sceneId});
}
async function changeShowClip(item,changes,settings,sceneId) {
  const p=item.params;
  const beforeSettings={clip_start:p.clip_start || 0,matte:p.matte || "none",audio_mode:p.audio_mode || "own",clip_audio:p.clip_audio!==false};
  const before={at:item.at,duration:item.duration};
  for(const key of Object.keys(changes))if(!["at","duration"].includes(key))before[key]=p[key] ?? changes[key];
  try {await api(`/show/clips/${encodeURIComponent(item.id)}/settings`,settings);await showPatch(`/show/review/${encodeURIComponent(item.id)}`,changes);}
  catch(error){await api(`/show/clips/${encodeURIComponent(item.id)}/settings`,beforeSettings);await showPatch(`/show/review/${encodeURIComponent(item.id)}`,before);throw error;}
  showPushUndo({type:"clip",id:item.id,sceneId,settings:beforeSettings,changes:before});
}
async function clearShowSceneEffects(scene) {
  const items=showSceneItems(scene),entries=[];
  for(const item of items.filter(i=>i.type==="proposal")) {await showPatch(`/show/review/${encodeURIComponent(item.id)}`,{status:"discarded"});entries.unshift({type:"proposal",id:item.id,changes:{status:item.raw.status},sceneId:scene.id});}
  if(scene.overlays?.length){await api(`/show/scenes/${encodeURIComponent(scene.id)}/overlays`,{overlays:[]});entries.unshift({type:"overlay",sceneId:scene.id,overlays:structuredClone(scene.overlays)});}
  showPushUndo({type:"batch",sceneId:scene.id,entries});await refreshShowEditor(scene.id);
}
async function changeShowTiming(item,at,duration) {
  const scene = showEdit.scenes[showEdit.selected];
  if(!Number.isFinite(at+duration) || duration<.1 || at<scene.start || at+duration>scene.end+.001) throw new Error("Keep the effect inside this part.");
  if(item.type === "overlay") await saveShowOverlays(scene.id,scene.overlays.map(o => o.id===item.id?{...o,at,duration}:o));
  else await changeShowProposal(item,{at,duration},scene.id);
  await refreshShowEditor(scene.id);
}
async function applyShowUndo(entry) {
  if(entry.type === "cut") {const doc=await cutDocument("show");const result=await api("/montara/show/cuts",{op:"undo",project_id:doc.project_id,revision:doc.revision,operation_id:entry.operationId});applyShowEditorData(result.editor,entry.sceneId);showPlaybackState.cache.clear();selectedShowCut=null;}
  else if(entry.type === "batch") { for(const child of entry.entries) await applyShowUndo(child); }
  else if(entry.type === "proposal" && ('volume' in entry.changes || 'under_voice' in entry.changes)) {const doc=await api('/show/scenes');const raw=doc.proposals.find(p=>p.id===entry.id);if(raw)await changeShowProposal({id:raw.id,kind:raw.kind,params:raw.params,raw},entry.changes,entry.sceneId,false);}
  else if(entry.type === "clip") { await api(`/show/clips/${encodeURIComponent(entry.id)}/settings`,entry.settings); await showPatch(`/show/review/${encodeURIComponent(entry.id)}`,entry.changes); }
  else if(entry.type === "overlay") await api(`/show/scenes/${encodeURIComponent(entry.sceneId)}/overlays`,{overlays:entry.overlays});
  else await showPatch(`/show/review/${encodeURIComponent(entry.id)}`,entry.changes);
}
$('#showUndoEdit').addEventListener('click',async()=>{
  const entry=showEditor.undo.at(-1);if(!entry||showEditor.busy||cutBusy||entry.project!==state.projectId)return;
  showEditor.busy=true;cancelShowAutoPreview();const forward=inverseShowEdit(entry);
  try{await applyShowUndo(entry);showEditor.undo.pop();showEditor.redo.push({entry,forward});await refreshShowEditor(entry.sceneId);showHistoryButtons();}catch(error){$('#showPreviewStatus').textContent=error.message;}finally{showEditor.busy=false;}
});
$('#showRedoEdit').addEventListener('click',async()=>{
  const saved=showEditor.redo.at(-1);if(!saved||showEditor.busy||cutBusy)return;showEditor.busy=true;cancelShowAutoPreview();
  try{
    if(saved.entry.type==='cut'){const doc=await cutDocument('show');const result=await api('/montara/show/cuts',{project_id:doc.project_id,revision:doc.revision,...saved.entry.change});saved.entry.operationId=result.operation_id;applyShowEditorData(result.editor,saved.entry.sceneId);}
    else await applyShowUndo(saved.forward);
    showEditor.redo.pop();showEditor.undo.push(saved.entry);await refreshShowEditor(saved.entry.sceneId);showHistoryButtons();
  }catch(error){$('#showPreviewStatus').textContent=error.message;}finally{showEditor.busy=false;}
});
const showPlaybackState = {mode:"source",sceneId:null,segments:[],index:0,spans:[],cache:new Map()};
function showPlaybackOffset(){
  const video=$("#showSceneVideo"),scene=showEdit.scenes[showEdit.selected];if(!scene)return 0;
  if(showPlaybackState.mode!=="source")return showOriginalTime(video.currentTime || 0,showPlaybackState.spans);
  const segments=showPlaybackState.segments,index=showPlaybackState.index;
  if(!segments[index])return 0;
  return segments.slice(0,index).reduce((sum,[a,b])=>sum+b-a,0)+Math.max(0,Math.min(segments[index][1]-segments[index][0],video.currentTime-segments[index][0]));
}
function showPlayback(scene,forceSource=false,offset=0){
  showSmoothRequest++;$("#showLivePlay").disabled=false;
  forceSource ||= !!showPlaybackState.liveEditing;
  const video=$("#showSceneVideo"),key=state.projectId+"|"+scene.id;video.hidden=false;
  if(scene.preview?.status==="ready")showPlaybackState.cache.set(key,scene.preview);
  const ready=showPlaybackState.cache.get(key);
  showPlaybackState.sceneId=scene.id;showPlaybackState.index=0;
  if(ready && !forceSource){
    showPlaybackState.mode="rendered";showPlaybackState.spans=ready.inserted || [];
    if(video.getAttribute("src")!==ready.url){video.src=ready.url;video.addEventListener('loadedmetadata',()=>{if(showPlaybackState.mode==='rendered')video.currentTime=showPreviewTime(offset,ready.inserted||[]);},{once:true});}else video.currentTime=showPreviewTime(offset,ready.inserted||[]);
    $("#showPreviewStatus").textContent=scene.preview?.status==="ready"?"Preview ready.":"Changes saved. Preview this part to update the picture.";
  }else{
    showPlaybackState.mode="source";showPlaybackState.spans=[];showPlaybackState.segments=scene.segments?.length?scene.segments:[[scene.start,scene.end]];
    const sourceUrl=showEdit.sourceUrl || `/api/v1/show/source?path=${encodeURIComponent(showEdit.source)}`;
    const loaded=video.getAttribute("src")===sourceUrl && video.readyState>=1;
    if(video.getAttribute("src")!==sourceUrl)video.src=sourceUrl;
    const sceneId=scene.id;
    if(loaded)seekShowTimeline(offset);
    else video.addEventListener("loadedmetadata",()=>{if(showPlaybackState.sceneId===sceneId && showPlaybackState.mode==="source")seekShowTimeline(offset);},{once:true});
    $("#showPreviewStatus").textContent=document.body.dataset.showKind==='podcast'?"Camera edit ready. Play to watch; right-click a shot to change its viewpoint.":"Playing the cuts directly. Preview this part when you want to see the effects.";
  }
  video.hidden=false;updateShowCursor();
  document.dispatchEvent(new CustomEvent("montara:show-playback"));
}
$("#showSceneVideo").addEventListener("seeking",()=>{
  if(showPlaybackState.mode!=="source")return;
  const video=$("#showSceneVideo"),segments=showPlaybackState.segments,current=segments[showPlaybackState.index];
  if(current && video.currentTime>=current[0]-.01 && video.currentTime<=current[1]+.01)return;
  let index=segments.findIndex(([a,b])=>video.currentTime>=a && video.currentTime<=b);
  if(index<0){index=segments.findIndex(([a])=>a>=video.currentTime);if(index<0)index=segments.length-1;video.currentTime=segments[index][0];}
  showPlaybackState.index=index;
});
$("#showSceneVideo").addEventListener("timeupdate",()=>{
  if(showPlaybackState.mode!=="source")return;
  const video=$("#showSceneVideo"),segments=showPlaybackState.segments,segment=segments[showPlaybackState.index];
  if(!segment || video.paused)return;
  if(video.currentTime>=segment[1]-.025){
    if(showPlaybackState.index+1<segments.length){showPlaybackState.index++;video.currentTime=segments[showPlaybackState.index][0];}
    else{video.pause();video.currentTime=segment[1];}
  }
});
$("#showPreviewPart").addEventListener("click",async()=>{
  const scene=showEdit.scenes[showEdit.selected];if(!scene)return;
  clearTimeout(showEdit.previewTimer);showPlaybackState.liveEditing=false;const token=++showEdit.previewToken;
  $("#showSceneVideo").pause();$("#showPreviewPart").disabled=true;$("#showPreviewStatus").textContent="Generating this part's preview…";
  try{await prepareShowProgramPreview();if(token!==showEdit.previewToken || $('#showReview').hidden){$('#showPreviewPart').disabled=false;return;}await api(`/show/scenes/${encodeURIComponent(scene.id)}/preview`,{next:[]});await pollShowScene(scene.id,token);}
  catch(error){$("#showPreviewStatus").textContent=error.message;$("#showPreviewPart").disabled=false;}
});
function showPreviewTime(time,spans=[]) { return time+spans.reduce((sum,[at,d])=>sum+(at<=time?d:0),0); }
function seekShowTimeline(offset) {
  const scene=showEdit.scenes[showEdit.selected],video=$("#showSceneVideo"); if(!scene || video.hidden)return;
  offset=Math.max(0,Math.min(offset,scene.end-scene.start));
  if(showPlaybackState.mode==="source"){
    let remaining=offset,index=0;const segments=showPlaybackState.segments;
    while(index<segments.length-1 && remaining>=segments[index][1]-segments[index][0]){remaining-=segments[index][1]-segments[index][0];index++;}
    showPlaybackState.index=index;video.currentTime=segments[index][0]+remaining;
  }else video.currentTime=showPreviewTime(offset,showPlaybackState.spans);
}
// One programme clock shared by the ruler, source cuts and effects.
let showScrubbing=null;
function wireShowScrub(bed,length,label='Timeline'){
  const video=$('#showSceneVideo'),cursor=bed.querySelector('.show-playhead');
  if(cursor){cursor.classList.add('show-scrub-handle');cursor.setAttribute('role','slider');cursor.tabIndex=0;cursor.setAttribute('aria-label',`Playback position · ${label}`);cursor.setAttribute('aria-valuemin','0');cursor.setAttribute('aria-valuemax',length.toFixed(3));}
  const offset=e=>{const rect=bed.getBoundingClientRect();return Math.max(0,Math.min(length,(e.clientX-rect.left)/rect.width*length));};
  let drag=null;
  const move=at=>{showScrubbing=at;seekShowTimeline(at);updateShowCursor();};
  bed.addEventListener('pointerdown',e=>{
    if(e.button!==0||e.ctrlKey||e.metaKey||e.target.closest('.cut-shot,.cut-handle,[data-timeline-effect]'))return;
    e.preventDefault();e.stopPropagation();video.pause();drag={pointer:e.pointerId};bed.setPointerCapture(e.pointerId);move(offset(e));
  });
  bed.addEventListener('pointermove',e=>{if(drag)move(offset(e));});
  const release=e=>{if(!drag)return;move(offset(e));drag=null;showScrubbing=null;updateShowCursor();};
  bed.addEventListener('pointerup',release);bed.addEventListener('pointercancel',()=>{drag=null;showScrubbing=null;updateShowCursor();});
  if(cursor)cursor.onkeydown=e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();e.stopPropagation();video.pause();const at=e.key==='Home'?0:e.key==='End'?length:showPlaybackOffset()+(e.key==='ArrowRight'?1:-1)*(e.shiftKey?1:1/30);move(Math.max(0,Math.min(length,at)));showScrubbing=null;};
}
function updateShowCursor(){
  const scene=showEdit.scenes[showEdit.selected]; if(!scene)return;
  const t=Math.max(0,Math.min(scene.end-scene.start,showScrubbing ?? showPlaybackOffset()));
  $("#showEditorTimeline").style.setProperty("--playhead",`${t/(scene.end-scene.start)*100}%`);
  $("#showEditorTimeline").querySelectorAll(".show-scrub-handle").forEach(cursor=>cursor.setAttribute("aria-valuenow",t.toFixed(3)));
  const readout=$("#showTimelineTime");if(readout)readout.textContent=`${t.toFixed(1)}s / ${(scene.end-scene.start).toFixed(1)}s`;
}
function renderShowTimeline(){
  const scene=showEdit.scenes[showEdit.selected]; if(!scene)return;
  if(showEditor.project!==state.projectId){showEditor.project=state.projectId;showEditor.undo=[];showEditor.redo=[];showHistoryButtons();}
  const length=scene.end-scene.start, items=showSceneItems(scene).filter(item=>item.raw.status!=="discarded");
  let cutOffset=0;
  const cuts=(scene.segments || []).map(([a,b],index)=>{const start=cutOffset;cutOffset+=b-a;return `<span class="show-video-cut" style="left:${start/length*100}%;width:${(b-a)/length*100}%" title="Cut ${index+1} · ${(b-a).toFixed(1)} seconds">${b-a>length*.08?index+1:""}</span>`;}).join("");
  const host=$('#showEditorTimeline');host.style.setProperty('--second-step',`${100/length}%`);
  const bars=(group)=>{const ends=[];const html=group.sort((a,b)=>a.at-b.at).map(item=>{let lane=ends.findIndex(t=>t<=item.at);if(lane<0)lane=ends.length;ends[lane]=item.at+(item.duration||1);return `<button type="button" class="show-effect-bar" data-timeline-effect="${escapeHtml(item.id)}" style="left:${Math.max(0,(item.at-scene.start)/length*100)}%;width:${Math.min(100,Math.max(.1,item.duration||1)/length*100)}%;top:${lane*34+3}px" title="${escapeHtml(showItemName(item))}"><i data-trim="left"></i><b>${escapeHtml(showItemName(item))}</b><i data-trim="right"></i></button>`;}).join('');return {html,lanes:ends.length};};
  const fx=items.filter(i=>i.kind!=='jingle'),music=items.filter(i=>i.kind==='jingle');
  const track=(label,group,add=false)=>{const packed=bars(group);return `<div class="show-track"><span>${label}${add?'<button type="button" class="icon-btn" data-fx-add aria-label="Add effect">+</button>':''}</span><div class="show-track-bed" data-show-seek style="min-height:${Math.max(36,packed.lanes*34)}px">${packed.html}<i class="show-playhead"></i></div></div>`;};
  host.innerHTML=`<div class="show-timeline-heading"><h3>Timeline</h3><output id="showTimelineTime"></output></div><div class="show-timeline-ruler" aria-label="Seconds">${Array.from({length:Math.floor(length)+1},(_,i)=>`<i class="${i%5===0?'major':''}" style="left:${i/length*100}%">${i%5===0?i+'s':''}</i>`).join('')}</div><div class="show-track cut-replaced"><span>Video</span><div class="show-video-bed"></div></div>${track('FX',fx,true)}${music.length?track('Music',music):''}<button type="button" class="icon-btn add-track" id="showTrackAdd" aria-label="Add track" title="Add effect, music or video">+</button>`;
  host.querySelector('[data-fx-add]').onclick=()=>$('#showOpenEffects').click();host.querySelector('#showTrackAdd').onclick=event=>compactAddMenu(event);
  host.querySelectorAll('[data-show-seek]').forEach(bed=>wireShowScrub(bed,length,bed.parentElement.querySelector('span')?.textContent || 'Effects'));
  wireShowScrub(host.querySelector('.show-timeline-ruler'),length,'Ruler');
  host.querySelectorAll("[data-timeline-effect]").forEach(bar=>{
    const item=items.find(i=>i.id===bar.dataset.timelineEffect);let drag=null,suppressed=false;
    bar.addEventListener("pointerdown",event=>{if(event.button!==0 || showEditor.busy)return;const box=bar.parentElement.getBoundingClientRect();drag={x:event.clientX,box,at:item.at,duration:Math.max(.1,item.duration || 1),edge:event.target.dataset.trim};bar.setPointerCapture(event.pointerId);});
    bar.addEventListener("pointermove",event=>{
      if(!drag)return;const delta=(event.clientX-drag.x)/drag.box.width*length;if(Math.abs(event.clientX-drag.x)<4)return;suppressed=true;
      let at=drag.at,duration=drag.duration;
      if(drag.edge==="left"){at=Math.max(scene.start,Math.min(drag.at+drag.duration-.1,drag.at+delta));duration=drag.at+drag.duration-at;}
      else if(drag.edge==="right")duration=Math.max(.1,Math.min(scene.end-at,drag.duration+delta));
      else at=Math.max(scene.start,Math.min(scene.end-duration,drag.at+delta));
      drag.next={at:Math.round(at*100)/100,duration:Math.round(duration*100)/100};bar.style.left=`${(at-scene.start)/length*100}%`;bar.style.width=`${duration/length*100}%`;
    });
    bar.addEventListener("pointerup",async()=>{const change=drag?.next;drag=null;if(!change)return;showEditor.busy=true;try{await changeShowTiming(item,change.at,change.duration);}catch(error){$("#showEditorStatus").textContent=error.message;renderShowTimeline();}finally{showEditor.busy=false;}});
    bar.addEventListener("click",()=>{if(suppressed){suppressed=false;return;}selectShowPlacedEffect(item.id,true);});
    bar.addEventListener("contextmenu",event=>{event.preventDefault();showPlacedContextMenu(event,item);});
  });updateShowCursor();
}
document.addEventListener("montara:show-scene",renderShowTimeline);
$("#showSceneVideo").addEventListener("timeupdate",updateShowCursor);
$("#showSceneEffects").addEventListener("click",event=>{const button=event.target.closest("[data-edit-effect]");if(button)openShowInspector(button.dataset.editEffect);});
$("#showSceneEffects").addEventListener("contextmenu",event=>{const row=event.target.closest("[data-edit-row]");if(row){event.preventDefault();const scene=showEdit.scenes[showEdit.selected];const item=showSceneItems(scene).find(i=>i.id===row.dataset.editRow);if(item)showPlacedContextMenu(event,item);}});
$("#showSceneVideo").addEventListener("contextmenu",()=>{
  const scene=showEdit.scenes[showEdit.selected]; if(!scene)return;
  const at=scene.start+showPlaybackOffset(),items=showSceneItems(scene).filter(i=>i.raw.status!=="discarded");
  const active=items.filter(i=>i.raw.status!=="discarded" && i.at<=at+.05 && at<i.at+Math.max(.1,i.duration || 1));
  $("#showContextEdits").replaceChildren();
  for(const item of (active.length?active:items)){
    const button=document.createElement("button");button.type="button";button.setAttribute("role","menuitem");button.textContent=`Edit effect · ${showItemName(item)}`;button.addEventListener("click",()=>openShowInspector(item.id));$("#showContextEdits").append(button);
  }  const menu=$("#showContextMenu"),box=menu.getBoundingClientRect();
  menu.style.top=`${Math.max(8,Math.min(parseFloat(menu.style.top)||8,window.innerHeight-box.height-8))}px`;
});
function inspectorField(label,key,value,type="number",extra=""){if(type==="number")extra=extra.replace(/step="[^"]*"/g,'step="any"');return `<label>${label}<input data-inspect="${key}" type="${type}" value="${escapeHtml(String(value??""))}" ${extra}></label>`;}
function inspectorSelect(label,key,value,options){return `<label>${label}<select data-inspect="${key}">${options.map(([v,n])=>`<option value="${v}" ${String(value)===String(v)?"selected":""}>${n}</option>`).join("")}</select></label>`;}
function openShowInspector(id){
  if(showEditor.busy)return;
  $("#showContextMenu").hidden=true;
  const scene=showEdit.scenes[showEdit.selected],item=showSceneItems(scene).find(i=>i.id===id);if(!item)return;
  showEditor.selected={id,sceneId:scene.id};$("#showSceneVideo").pause();
  const p=item.params;let html=inspectorField("Start in this part (seconds)","at",(item.at-scene.start).toFixed(2),"number",`min="0" max="${scene.end-scene.start}" step="0.1" required`)+inspectorField("Duration (seconds)","duration",Math.max(.1,item.duration || 1),"number",'min="0.1" step="0.1" required');
  if(item.kind==="word") html+=inspectorField("Words","text",p.text,"text",'maxlength="120"')+inspectorField("Colour","colour",p.colour || "#fff4d6","color")+inspectorSelect("Typeface","font",p.font || "note",[["plain","Plain"],["note","Notebook"],["marker","Marker"],["impact","Impact"]]);
  if(["word","drawing"].includes(item.kind))html+=inspectorField("Size (share of frame)","size",p.size || .3,"number",'min="0.05" max="2" step="0.05"')+inspectorSelect("Position","position",p.position||"left",[["left","Left"],["center","Centre"],["right","Right"]])+inspectorSelect("Animation","effect",p.effect||"pop",[["none","None"],["pop","Pop"],["fade","Fade"],["bounce","Bounce"],["pulse","Pulse"],["shake","Shake"]]);
  if(item.kind==="overlay")html+=inspectorField("Horizontal position %","x",p.x,"number",'step="1"')+inspectorField("Vertical position %","y",p.y,"number",'step="1"')+inspectorField("Width %","width",p.width,"number",'min="1" max="300" step="1"')+inspectorField("Rotation °","rotate",p.rotate || 0,"number",'min="-180" max="180" step="1"')+inspectorField("Opacity","opacity",p.opacity ?? 1,"number",'min="0.05" max="1" step="0.05"')+inspectorSelect("Movement","action",p.action || "none",[["none","None"],["up","Move up"],["down","Move down"],["jump","Jump"],["grow","Grow"],["pulse","Pulse"],["swing","Swing"],["spin","Spin"],["talk","Talk with voice"],["look","Move eyes"]])+inspectorSelect("Voice","voice_mode",p.voice_mode || (p.voice?"own":"mine"),[["mine","Narrator"],["own","Its own voice"]]);
  if(item.kind==="warp")html+=inspectorSelect("Distortion","warp",p.warp||"wave",[["wave","Wave"],["stretch","Stretch"],["swirl","Swirl"]])+inspectorField("Strength","strength",p.strength ?? .8,"number",'min="0" max="2" step="0.1"');
  if(["steam","texture"].includes(item.kind))html+=inspectorSelect("Texture","texture",p.texture || "rainbow",[["rainbow","Rainbow"],["smoke","Smoke"],["fire","Fire"],["snow","Snow"],["rain","Rain"],["sparks","Sparks"]])+inspectorField("Scale","scale",p.scale ?? 1,"number",'min="0.1" max="3" step="0.1"');
  if(item.kind==="clip")html+=inspectorField("Start in source clip (seconds)","clip_start",p.clip_start || 0,"number",'min="0" step="0.1"')+inspectorSelect("Background","matte",p.matte || "none",[["none","Keep"],["green","Remove green screen"],["black","Remove black background"],["green-light","Remove green · rain, snow, smoke"],["person","Cut out moving person"]])+inspectorSelect("Audio","audio_mode",p.clip_audio===false?"mute":p.audio_mode || "own",[["mute","Narrator only"],["mix","Clip with narrator"],["own","Clip pauses narrator"]]);
  if(["cutaway","character"].includes(item.kind))html+=inspectorField("Zoom","zoom",p.zoom || 1,"number",'min="1" max="3" step="0.05"');
  if(item.kind==="jingle")html+=inspectorField("Start inside the music (seconds)","start",p.start ?? 0,"number",'min="0" step="0.1"')+inspectorField("Music level","volume",p.volume ?? .28,"number",'min="0" max="1" step="0.05"')+inspectorSelect("Keep narration in front","under_voice",String(p.under_voice!==false),[["true","Yes"],["false","No"]]);
  $("#showInspectorFields").innerHTML=html;$("#showInspectorTitle").textContent=`Edit effect · ${SHOW_EFFECT_NAMES[item.kind]||item.kind}`;$("#showInspectorStatus").textContent="";
  $("#showInspectorMedia").hidden=!["drawing","clip","background","overlay"].includes(item.kind);
  $("#showInspectorVideo").hidden=true;
  $("#showInspector").showModal();
}
$("#showInspectorClose").addEventListener("click",()=>{if(!showEditor.busy)$("#showInspector").close();});
$("#showInspector").addEventListener("cancel",event=>{if(showEditor.busy)event.preventDefault();});
$("#showInspector").addEventListener("close",()=>$("#showInspectorVideo").pause());
$("#showInspectorForm").addEventListener("submit",async event=>{
  event.preventDefault();if(showEditor.busy)return;
  const selected=showEditor.selected,scene=showEdit.scenes.find(s=>s.id===selected.sceneId),item=showSceneItems(scene).find(i=>i.id===selected.id);if(!item)return;
  const changes={};$("#showInspectorFields").querySelectorAll("[data-inspect]").forEach(input=>{changes[input.dataset.inspect]=input.type==="number"?Number(input.value):input.value;});
  changes.at+=scene.start;
  if(!Number.isFinite(changes.at+changes.duration)||changes.at<scene.start||changes.duration<.1||changes.at+changes.duration>scene.end+.001){$("#showInspectorStatus").textContent="Keep the effect inside this part.";return;}
  showEditor.busy=true;const submit=event.currentTarget.querySelector('[type="submit"]');submit.disabled=true;
  try{
    if(item.type==="overlay")await saveShowOverlays(scene.id,scene.overlays.map(o=>o.id===item.id?{...o,...changes}:o));
    else if(item.kind === "clip") {
      const start=changes.clip_start,matte=changes.matte,mode=changes.audio_mode;delete changes.clip_start;delete changes.matte;
      await changeShowClip(item,changes,{clip_start:start,matte,audio_mode:mode==="mute"?"mix":mode,clip_audio:mode!=="mute"},scene.id);
    } else await changeShowProposal(item,changes,scene.id);
    if(event.submitter?.dataset.previewEffect){
      $("#showInspectorStatus").textContent="Generating this effect's preview…";
      const route=item.type==="overlay"?`/show/scenes/${encodeURIComponent(scene.id)}/stickers/${encodeURIComponent(item.id)}/preview`:`/show/review/${encodeURIComponent(item.id)}/preview`;
      const preview=await api(route,{});$("#showInspectorVideo").src=preview.url;$("#showInspectorVideo").hidden=false;
      await refreshShowEditor(scene.id,false);renderShowEffectRows(showEdit.scenes[showEdit.selected]);renderShowTimeline();
      $("#showInspectorStatus").textContent="Effect preview ready. Changes saved.";
    }else{$("#showInspector").close();await refreshShowEditor(scene.id);}
  }catch(error){$("#showInspectorStatus").textContent=error.message;}finally{showEditor.busy=false;submit.disabled=false;}
});
$("#showInspectorDelete").addEventListener("click",async()=>{
  if(showEditor.busy)return;const {id,sceneId}=showEditor.selected,scene=showEdit.scenes.find(s=>s.id===sceneId),item=showSceneItems(scene).find(i=>i.id===id);if(!item)return;
  showEditor.busy=true;
  try{if(item.type==="overlay")await saveShowOverlays(sceneId,scene.overlays.filter(o=>o.id!==id));else await changeShowProposal(item,{status:"discarded"},sceneId);$("#showInspector").close();await refreshShowEditor(sceneId);}
  catch(error){$("#showInspectorStatus").textContent=error.message;}finally{showEditor.busy=false;}
});
$("#showInspectorMedia").addEventListener("click",async()=>{
  const {id,sceneId}=showEditor.selected,scene=showEdit.scenes.find(s=>s.id===sceneId),item=showSceneItems(scene).find(i=>i.id===id);if(!item)return;
  $("#showInspector").close();openShowEffectTools("media",false);
  try{
    await refreshShowLibrary();let asset;
    if(item.kind==="clip"){const data=await api("/show/video-library");asset=data.items.find(a=>a.path===item.params.clip);if(asset)asset={...asset,mediaType:"video"};}
    else {const data=await api("/show/library");asset=data.items.find(a=>a.path===(item.type==="overlay"?item.params.asset:item.params.picture));if(asset)asset={...asset,mediaType:"image"};}
    if(!asset)throw new Error("Choose a replacement from your library.");
    chooseShowAsset(asset);showMedia.editing={...item,sceneId};
    $("#showEffectAt").value=(item.at-scene.start).toFixed(2);$("#showEffectDuration").value=Math.max(.1,item.duration || 1);
    if(item.type==="overlay"){$("#showAssetSize").value=String([.3,.5,.8].reduce((a,b)=>Math.abs(a-item.params.width/100)<Math.abs(b-item.params.width/100)?a:b));}
    if(item.kind==="clip"){$("#showClipStart").value=item.params.clip_start || 0;$("#showClipMatte").value=item.params.matte || "none";$("#showClipSound").checked=item.params.clip_audio!==false;}
    $("#showMediaStatus").textContent="Editing the existing effect. Save to replace it in place.";
    if(asset.character){await prepareShowFaceEdit(asset);}
  }catch(error){$("#showMediaStatus").textContent=error.message;}
});
if(showEdit.scenes.length && !$("#showReview").hidden){renderShowEffectRows(showEdit.scenes[showEdit.selected]);renderShowTimeline();}

// Decode each cut once, rather than seeking the original file during playback.
let showSmoothRequest=0;
async function playShowContinuously(){
  const video=$("#showSceneVideo"),scene=showEdit.scenes[showEdit.selected];
  if(!scene || showPlaybackState.mode!=="source")return;
  const program=showModeReview.kind==='podcast'?showModeReview.podcast:showModeReview.kind==='storytelling'?showModeReview.story:null;
  if(program?.dirty){video.pause();$("#showPreviewStatus").textContent='Cuts changed. Press Preview this part to update the camera/montage first.';return;}
  const offset=showPlaybackOffset(),token=++showSmoothRequest,sceneId=scene.id;
  video.pause();$("#showLivePlay").disabled=true;
  $("#showPreviewStatus").textContent='Preparing smooth playback…';
  try{
    let result=await api(`/montara/show/playback/${encodeURIComponent(sceneId)}`,{});
    while(true){
      if(token!==showSmoothRequest || $('#showReview').hidden || showEdit.scenes[showEdit.selected]?.id!==sceneId)return;
      if(result.status==='failed')throw new Error(result.message);
      if(result.status==='ready')break;
      await new Promise(resolve=>setTimeout(resolve,500));
      result=await api(result.poll);
    }
    showPlaybackState.mode='clean';showPlaybackState.spans=[];
    video.src=result.url;
    video.addEventListener('loadedmetadata',()=>{
      if(token!==showSmoothRequest || $('#showReview').hidden || showEdit.scenes[showEdit.selected]?.id!==sceneId)return;
      video.currentTime=offset;video.play().catch(()=>{});
    },{once:true});
    $("#showPreviewStatus").textContent=document.body.dataset.showKind==='podcast'?'Smooth playback · Preview after changing camera shots.':'Smooth playback · Preview this part for the finished effects.';
  }catch(error){$("#showPreviewStatus").textContent=error.message;}
  finally{if(token===showSmoothRequest)$("#showLivePlay").disabled=false;}
}
// Source playback starts immediately; automatic previews run after edits, never on Play.
