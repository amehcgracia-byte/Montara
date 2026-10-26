// Montara's small contextual media editor. Uses the existing Show API.
"use strict";
let greenCategory='mine',greenCatalog=null;
const showMedia = { asset: null, project: null, busy: false, layer: null, marks: {}, image: null, voice: null, talking: null, drag: null };
function showToolsTab(media) {
  $("#showAddEffect").hidden = media;
  $("#showMediaPanel").hidden = !media;
  $("#showSimpleTab").classList.toggle("on", !media);
  $("#showMediaTab").classList.toggle("on", media);
}
function showOriginalTime(time, spans = []) {
  let delay = 0;
  for (const [at, duration] of [...spans].sort((a, b) => a[0] - b[0])) {
    if (time < at + delay) return time - delay;
    if (time < at + delay + duration) return at;
    delay += duration;
  }
  return time - delay;
}
function openShowEffectTools(kind = "word", usePlayhead = true) {
  const scene = showEdit.scenes[showEdit.selected];
  if (!scene) return;
  $("#showSceneVideo").pause();
  showMedia.editing = null; showMedia.intent = kind === "background" ? "background" : null;
  const media = kind === "media" || kind === "background";
  if (usePlayhead) {
    const length = scene.end - scene.start;
    const at = Math.max(0, Math.min(Math.max(0, length - .1), showPlaybackOffset()));
    $("#showEffectAt").value = at.toFixed(1);
    $("#showEffectDuration").value = Math.max(.1, Math.min(2, length - at)).toFixed(1);
  }
  $("#showContextMenu").hidden = true;
  showToolsTab(media);
  if (!media) { $("#showEffectKind").value = kind; $("#showEffectTextLabel").hidden = kind !== "word"; }
  if (!$("#showEffectDialog").open) $("#showEffectDialog").showModal();
  if (media && !showMedia.busy) $("#showMediaStatus").textContent = "";
  if (media) refreshShowLibrary().catch(error => { $("#showMediaStatus").textContent = error.message; });
}
$("#showOpenEffects").addEventListener("click", () => openShowEffectTools());
$("#showCloseEffects").addEventListener("click", () => { if (!showMedia.busy) $("#showEffectDialog").close(); });
$("#showEffectDialog").addEventListener("cancel", event => { if (showMedia.busy) event.preventDefault(); });
$("#showSimpleTab").addEventListener("click", () => showToolsTab(false));
$("#showMediaTab").addEventListener("click", () => openShowEffectTools("media", false));
$("#showSceneVideo").addEventListener("contextmenu", event => {
  event.preventDefault(); $("#showSceneVideo").pause();
  const menu = $("#showContextMenu"); menu.hidden = false;
  menu.style.left = `${Math.max(8, Math.min(event.clientX, window.innerWidth - menu.offsetWidth - 8))}px`;
  menu.style.top = `${Math.max(8, Math.min(event.clientY, window.innerHeight - menu.offsetHeight - 8))}px`;
  menu.querySelector("button").focus();
});
$("#showContextMenu").addEventListener("click", event => {
  const button = event.target.closest("[data-show-context]");
  if (button) openShowEffectTools(button.dataset.showContext);
});
document.addEventListener("pointerdown", event => { if (!event.target.closest("#showContextMenu")) $("#showContextMenu").hidden = true; });
document.addEventListener("keydown", event => { if (event.key === "Escape") $("#showContextMenu").hidden = true; });
function showMediaPlacement() {
  const scene = showEdit.scenes[showEdit.selected];
  const offset = Number($("#showEffectAt").value), duration = Number($("#showEffectDuration").value);
  if (!scene || !Number.isFinite(offset + duration) || offset < 0 || duration < .1 || offset + duration > scene.end - scene.start + .001) throw new Error("Keep the effect inside this part.");
  return {scene_id: scene.id, at: scene.start + offset, duration, project_id: state.projectId};
}
async function mediaRequest(path, options) {
  const response = await fetch(`/api/v1${path}`, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error?.message || "Could not add this media.");
  return data;
}
async function uploadShowMedia(path, file) {
  const body = new FormData(); body.append("file", file); body.append("project_id", state.projectId);
  return mediaRequest(path, {method:"POST", body});
}
async function showMediaJob(message, work) {
  if (showMedia.busy) return;
  showMedia.busy = true;
  $("#showMediaRecovery").hidden = true;
  $("#showMediaStatus").textContent = message;
  $("#showMediaStatus").classList.add("media-working");
  $("#showCloseEffects").disabled = true;
  $("#showMediaPanel").setAttribute("aria-busy", "true");
  const controls = [...$("#showEffectDialog").querySelectorAll("button,input,select")];
  const disabled = controls.map(control => control.disabled);
  controls.forEach(control => { control.disabled = true; });
  const undoStart = typeof showEditor !== "undefined" ? showEditor.undo.length : 0;
  let success = false;
  try { await work(); success = true; }
  catch (error) {
    $("#showMediaStatus").textContent = error.message;
    if(error.code==='external_verification_required'){
      $("#showMediaRecovery").hidden=false;
      const link=$("#showMediaOpenSource");link.hidden=true;link.removeAttribute('href');
      try{const url=new URL($("#showMediaURL").value.trim());if(url.protocol==='https:'){link.href=url.href;link.hidden=false;}}catch{}
      if(!$("#showMediaLibrary").querySelector('button'))$("#showMediaLibrary").textContent='No clip imported. Choose a video file to continue.';
    }
  }
  finally {
    if(success && typeof showEditor !== "undefined" && showEditor.undo.length > undoStart+1){
      const entries=showEditor.undo.splice(undoStart).reverse();showPushUndo({type:"batch",sceneId:entries[0].sceneId,entries});
    }
    controls.forEach((control, i) => { control.disabled = disabled[i]; });
    $("#showMediaStatus").classList.remove("media-working");
    showMedia.busy = false; $("#showCloseEffects").disabled = false;
    $("#showMediaPanel").removeAttribute("aria-busy");
  }
}
let showLibraryRequest=0;
async function refreshShowLibrary() {
  const request=++showLibraryRequest;
  if (showMedia.project !== state.projectId) {
    showMedia.project = state.projectId; showMedia.asset = null;
    $("#showAssetEditor").hidden = true;
  }
  const catalog=await api("/montara/greenscreens");
  if(request!==showLibraryRequest)return;
  greenCatalog=catalog;
  if(greenCategory!=="mine"){renderGreenCategory();return;}
  const [pictures, videos, shelf] = await Promise.all([api("/show/library"), api("/show/video-library"),api(`/montara/show/shelf${$("#showShelfHidden").checked?"?hidden=1":""}`)]);
  if(request!==showLibraryRequest)return;
  const list = $("#showMediaLibrary"); list.replaceChildren();
  for(const item of shelf.items || []) {
    const button=document.createElement("button");button.type="button";button.className="show-library-item";
    const image=document.createElement("img");image.alt="";image.loading="lazy";image.src=item.thumbnail;
    const label=document.createElement("span");label.textContent=(item.hidden?"Restore · ":"Reusable · ")+item.name;button.append(image,label);
    button.addEventListener("click",()=>showMediaJob(item.hidden?"Restoring…":"Opening the reusable clip…",async()=>{
      if(item.hidden){await api(`/montara/show/shelf/${item.id}/visibility`,{hidden:false});await refreshShowLibrary();}
      else {const data=await api(`/montara/show/shelf/${item.id}/use`,{project_id:state.projectId});chooseShowAsset({...data.asset,mediaType:"video",shelfId:item.id});$("#showMediaStatus").textContent="Ready to reuse in this video.";}
    }));list.append(button);
  }
  for (const asset of [...(pictures.items || []).map(p => ({...p, mediaType:"image"})), ...(videos.items || []).map(v => ({...v, mediaType:"video"}))]) {
    const button = document.createElement("button"); button.type = "button"; button.className = "show-library-item";
    const img = document.createElement("img"); img.alt = ""; img.loading = "lazy";
    img.src = asset.mediaType === "image" ? asset.url : `/api/v1/show/video-library/${encodeURIComponent(asset.id)}/thumbnail`;
    const name = document.createElement("span"); name.textContent = asset.name || asset.path?.split("/").pop() || "Media";
    if(asset.saved_edit) name.textContent += ` · ${(asset.params?.clip_start || 0).toFixed(1)}s / ${asset.saved_duration.toFixed(1)}s`;
    button.append(img, name); button.addEventListener("click", () => { if (!showMedia.busy) chooseShowAsset(asset); }); list.append(button);
  }
  if (!list.children.length) list.textContent = "Your imported images and videos will appear here.";
}
function chooseShowAsset(asset) {
  showMedia.asset = asset; showMedia.layer = null; showMedia.voice = null; showMedia.talking = null;
  const sourceLink=$('#showAssetSource');sourceLink.hidden=true;sourceLink.removeAttribute('href');
  try{const url=new URL(asset.source_url);if(url.protocol==='https:'){sourceLink.href=url.href;sourceLink.hidden=false;}}catch{}
  const picture = asset.mediaType === "image";
  $("#showAssetEditor").hidden = false; $("#showAssetName").textContent = asset.name || asset.path.split("/").pop();
  $("#showAssetImage").hidden = !picture; $("#showAssetVideo").hidden = picture;
  $("#showAssetVideo").pause();
  if (picture) $("#showAssetImage").src = asset.url || `/api/v1/show/library/file?path=${encodeURIComponent(asset.path)}`;
  else $("#showAssetVideo").src = `/api/v1/show/video-library/${encodeURIComponent(asset.id)}/media`;
  $("#showVideoOptions").hidden = picture; $("#showImageOptions").hidden = !picture; $("#showCropImage").hidden = !picture;
  $("#showFaceEditor").hidden = true; $("#showPlaceFace").hidden = true; $("#showFaceVideo").hidden = true;
  $("#showClipStart").value = asset.params?.clip_start || 0; $("#showLibraryLength").value = asset.saved_duration || Math.min(2,asset.duration || 2); $("#showClipMatte").value = ["green","black","green-light"].includes(asset.matte) ? asset.matte : "none";
  $("#showClipSound").checked = asset.default_audio===true;
  if(asset.curated_id){$("#showAssetSize").value=asset.curated_category==="scenes"?"1":asset.curated_category==="quotes"?"0.5":"0.8";$("#showAssetPosition").value="center";const scene=showEdit.scenes[showEdit.selected];$("#showEffectDuration").value=Math.min(asset.saved_duration,scene.end-scene.start-Number($("#showEffectAt").value)).toFixed(2);}
  $("#showExcerptName").value = asset.name || ""; $("#showHideShelf").hidden = !asset.shelfId;
  $("#showFaceVoiceMode").value = "mine"; $("#showOtherVoice").hidden = true;
  $("#showPlaceAsset").textContent = showMedia.intent === "background" ? "Use as background" : "Save in this part";
  $$("[data-show-crop]").forEach(input => {input.value = "0";});
}
$("#showRefreshLibrary").addEventListener("click", () => showMediaJob("Loading library…", async () => {await refreshShowLibrary(); $("#showMediaStatus").textContent = "";}));
$("#showMediaFile").addEventListener("change", event => {
  const file = event.target.files[0]; event.target.value = ""; if (!file) return;
  showMediaJob("Importing your file…", async () => {
    const picture = /^image\//.test(file.type) || /\.(png|jpe?g|webp)$/i.test(file.name);
    const data = await uploadShowMedia(picture ? "/show/library/pictures" : "/show/library/media", file);
    await refreshShowLibrary(); chooseShowAsset(picture ? {...data, mediaType:"image"} : {...data.asset, mediaType:"video"});
    $("#showMediaStatus").textContent = "Ready. Choose the size and place it in your video.";
  });
});
$("#showImportLink").addEventListener("click", () => showMediaJob("Preparing the selected video excerpt…", async () => {
  showMedia.asset=null;$("#showAssetEditor").hidden=true;
  const placement = showMediaPlacement();
  const start = Number($("#showLinkStart").value), end = Number($("#showLinkEnd").value);
  if (!Number.isFinite(start + end) || start < 0 || end <= start || end-start > 30) throw new Error("Choose a video interval of up to 30 seconds.");
  const ref = await api("/show/references/video", {...placement, start, end, url:$("#showMediaURL").value.trim(), selected_text:$("#showSelectionEffect").dataset.text || ""});
  const data = await api(`/show/references/video/${encodeURIComponent(ref.id)}/download`, {duration: placement.duration});
  // Download creates an effect; keep it out of the edit until the person clicks Add.
  await showPatch(`/show/review/${encodeURIComponent(data.proposal.id)}`, {status:"discarded"});
  await refreshShowLibrary();
  const catalog = await api("/show/video-library");
  const asset = (catalog.items || []).find(item => item.path === data.proposal.params.clip);
  if (asset) chooseShowAsset({...asset, mediaType:"video"});
  $("#showMediaStatus").textContent = data.source_origin ? "Imported from the original already available. Choose where to place it." : "Imported into the library. Click Add to place it.";
}));
function showAssetCrop() {
  const crop = $$("[data-show-crop]").map(input => Number(input.value)/100);
  if (crop.some(v => !Number.isFinite(v) || v < 0 || v >= 1) || crop[0]+crop[2] >= .95 || crop[1]+crop[3] >= .95) throw new Error("Leave a visible area inside the crop.");
  return crop;
}
$("#showCropImage").addEventListener("click", () => showMediaJob("Saving a cropped copy…", async () => {
  const data = await api("/show/library/pictures/edited-copy", {path:showMedia.asset.path, crop:showAssetCrop()});
  await refreshShowLibrary(); chooseShowAsset({...data, mediaType:"image"}); $("#showMediaStatus").textContent = "Cropped copy saved. The original is kept.";
}));
$("#showCutImage").addEventListener("click", () => showMediaJob("Cutting out the subject…", async () => {
  const data = await api("/show/library/pictures/cutout", {path:showMedia.asset.path});
  await refreshShowLibrary(); chooseShowAsset({...data, mediaType:"image"}); $("#showMediaStatus").textContent = "Cutout ready. Check the edges before adding it.";
}));
$("#showHideImage").addEventListener("click", () => showMediaJob("Updating your library…", async () => {
  await api("/show/library/visibility", {path:showMedia.asset.path, retired:true});
  showMedia.asset = null; $("#showAssetEditor").hidden = true;
  await refreshShowLibrary(); $("#showMediaStatus").textContent = "Hidden from the library. Effects already in the video are kept.";
}));
async function showMediaChanged(sceneId) {
  const data = await api("/show/scenes"); showEdit.scenes = data.scenes || []; showEdit.proposals = data.proposals || [];
  const index = showEdit.scenes.findIndex(scene => scene.id === sceneId); if (index >= 0) showEdit.selected = index;
  showPlaybackState.liveEditing=true;renderShowScene(); $("#showEffectDialog").close();
}
async function placeShowVideo(asset, placement, talking = false) {
  const start = talking ? 0 : Number($("#showClipStart").value);
  if (!Number.isFinite(start) || start < 0 || start >= asset.duration) throw new Error("Choose a start inside the clip.");
  const crop = talking ? [0,0,0,0] : showAssetCrop();
  const data = await api(`/show/video-library/${encodeURIComponent(asset.id)}/place`, {...placement, duration: Math.min(placement.duration, asset.duration-start)});
  const id = data.proposal.id;
  try {
    await api(`/show/clips/${encodeURIComponent(id)}/settings`, {clip_start:start, matte:talking ? "none" : $("#showClipMatte").value, audio_mode:talking ? "own" : "mix", clip_audio:talking || $("#showClipSound").checked});
    if (!talking) await showPatch(`/show/review/${encodeURIComponent(id)}`, {crop, person_scale:Number($("#showAssetSize").value), person_offset:[$("#showAssetPosition").value === "left" ? -.3 : $("#showAssetPosition").value === "right" ? .3 : 0,0]});
    showPushUndo({type:"proposal",id,sceneId:placement.scene_id,changes:{status:"discarded"}});
  } catch (error) { await showPatch(`/show/review/${encodeURIComponent(id)}`, {status:"discarded"}); throw error; }
}
async function retireReplacedShowEffect(placement) {
  const editing = showMedia.editing;
  if (!editing) return;
  if (editing.type === "overlay") {
    const fresh = await api("/show/scenes"); const scene = fresh.scenes.find(s => s.id === placement.scene_id);
    await saveShowOverlays(scene.id, scene.overlays.filter(o => o.id !== editing.id));
  } else await changeShowProposal(editing, {status:"discarded"}, placement.scene_id);
}
async function placeShowBackground() {
  const placement = showMediaPlacement(), asset = showMedia.asset, editing = showMedia.editing;
  if (!asset || asset.mediaType !== "image") throw new Error("Choose an image for the new background.");
  if (editing?.kind === "background") await changeShowProposal(editing, {picture:asset.path, at:placement.at, duration:placement.duration, status:"approved"},placement.scene_id);
  else {
    const item = await api("/show/review/add", {kind:"background", picture:asset.path, subject:asset.name || "Your background", at:placement.at, duration:placement.duration});
    await showPatch(`/show/review/${encodeURIComponent(item.id)}`, {status:"approved"});
    showPushUndo({type:"proposal",id:item.id,sceneId:placement.scene_id,changes:{status:"discarded"}});
  }
  await showMediaChanged(placement.scene_id);
}
$("#showUseBackground").addEventListener("click", () => showMediaJob("Changing the background…", placeShowBackground));
$("#showPlaceAsset").addEventListener("click", () => showMediaJob("Saving the effect…", async () => {
  const placement = showMediaPlacement(), asset = showMedia.asset, editing = showMedia.editing;
  if (!asset) throw new Error("Choose a library item first.");
  if (showMedia.intent === "background" || editing?.kind === "background") return placeShowBackground();
  if (asset.mediaType === "video") {
    if (editing?.kind === "clip" && editing.params.clip === asset.path) {
      const start = Number($("#showClipStart").value);
      if (!Number.isFinite(start) || start < 0 || start >= asset.duration) throw new Error("Choose a start inside the video.");
      await changeShowClip(editing,{at:placement.at,duration:Math.min(placement.duration,asset.duration-start),crop:showAssetCrop(),person_scale:Number($("#showAssetSize").value),person_offset:[$("#showAssetPosition").value === "left" ? -.3 : $("#showAssetPosition").value === "right" ? .3 : 0,0]}, {clip_start:start,matte:$("#showClipMatte").value,audio_mode:"mix",clip_audio:$("#showClipSound").checked},placement.scene_id);
    } else { await placeShowVideo(asset, placement); await retireReplacedShowEffect(placement); }
  } else {
    const scene = (await api("/show/scenes")).scenes.find(s => s.id === placement.scene_id);
    const width = Number($("#showAssetSize").value)*100, position = $("#showAssetPosition").value;
    if (editing?.kind === "drawing") await changeShowProposal(editing,{picture:asset.path,size:width/100,position,at:placement.at,duration:placement.duration,status:"approved"},placement.scene_id);
    else {
      const overlay = {...(editing?.type === "overlay" ? editing.raw : {}),id:editing?.type === "overlay" ? editing.id : crypto.randomUUID(),asset:asset.path,at:placement.at,duration:placement.duration,width,x:position === "left" ? 8 : position === "right" ? 92-width : (100-width)/2,y:12,action:editing?.raw.action || "none",crop:showAssetCrop()};
      await saveShowOverlays(scene.id,[...scene.overlays.filter(o=>o.id!==overlay.id),overlay]);
      if (editing && editing.type !== "overlay") await retireReplacedShowEffect(placement);
    }
  }
  await showMediaChanged(placement.scene_id);
}));
// Eyes and mouth use rectangles on the preserved pixels, not generated faces.
function drawShowFace() {
  const canvas = $("#showFaceCanvas"), ctx = canvas.getContext("2d");
  ctx.clearRect(0,0,canvas.width,canvas.height);
  if (!showMedia.image) return;
  ctx.drawImage(showMedia.image,0,0,canvas.width,canvas.height);
  const regions = {...showMedia.marks};
  if (showMedia.dragRect) regions[$("#showFacePart").value] = showMedia.dragRect;
  for (const [name, rect] of Object.entries(regions)) {
    ctx.strokeStyle = name === "mouth" ? "#ff4f2e" : "#45c9dc"; ctx.lineWidth = 3;
    ctx.strokeRect(rect[0]*canvas.width,rect[1]*canvas.height,rect[2]*canvas.width,rect[3]*canvas.height);
  }
}
function showRect(region) {
  if (region?.rect) return region.rect;
  if (region?.polygon?.length) { const x = region.polygon.map(p=>p[0]), y = region.polygon.map(p=>p[1]); return [Math.min(...x),Math.min(...y),Math.max(...x)-Math.min(...x),Math.max(...y)-Math.min(...y)]; }
  return null;
}
async function prepareShowFaceEdit(asset) {
  if (asset.character) {
    showMedia.layer = await api(`/show/characters/edit?asset=${encodeURIComponent(asset.path)}`);
    const record = showMedia.layer.record;
    showMedia.marks = {};
    if (record.mouth) showMedia.marks.mouth = showRect(record.mouth);
    (record.eyes || []).slice(0,2).forEach((region,i)=>showMedia.marks[i?"rightEye":"leftEye"] = showRect(region));
    if (record.voice) showMedia.voice = {path:record.voice[0],duration:record.voice[1]+record.voice[2]};
  } else { showMedia.layer = await api("/show/characters/prepare-layer", {asset:asset.path, project_id:state.projectId}); showMedia.marks = {}; }
  const image = new Image(); image.src = showMedia.layer.cut.url; await image.decode(); showMedia.image = image;
  const canvas = $("#showFaceCanvas"); canvas.width = Math.min(700,image.naturalWidth); canvas.height = Math.max(1,Math.round(canvas.width*image.naturalHeight/image.naturalWidth));
  $("#showFaceEditor").hidden = false; $("#showPlaceFace").hidden = false; drawShowFace();
  $("#showFaceVoiceMode").value = showMedia.editing?.params.voice_mode === "mine" || !showMedia.editing?.params.voice ? "mine" : "own";
  $("#showOtherVoice").hidden = $("#showFaceVoiceMode").value === "mine";
  $("#showMediaStatus").textContent = "Mark eyes or a mouth. Narrator is used automatically unless you choose another voice.";
}
$("#showAnimateImage").addEventListener("click", () => showMediaJob("Preparing this image…", ()=>prepareShowFaceEdit(showMedia.asset)));
function facePoint(event) {
  const box = $("#showFaceCanvas").getBoundingClientRect();
  return [Math.max(0,Math.min(1,(event.clientX-box.left)/box.width)),Math.max(0,Math.min(1,(event.clientY-box.top)/box.height))];
}
$("#showFaceCanvas").addEventListener("pointerdown", event => {
  if (showMedia.busy) return;
  showMedia.drag = facePoint(event); showMedia.dragRect = null;
  event.currentTarget.setPointerCapture(event.pointerId); event.preventDefault();
});
$("#showFaceCanvas").addEventListener("pointermove", event => {
  if (!showMedia.drag) return;
  const end = facePoint(event), start = showMedia.drag;
  showMedia.dragRect = [Math.min(start[0],end[0]),Math.min(start[1],end[1]),Math.abs(end[0]-start[0]),Math.abs(end[1]-start[1])];
  drawShowFace();
});
$("#showFaceCanvas").addEventListener("pointercancel", () => { showMedia.drag = null; showMedia.dragRect = null; drawShowFace(); });
$("#showFaceCanvas").addEventListener("pointerup", event => {
  if (!showMedia.drag) return;
  const end = facePoint(event), start = showMedia.drag; showMedia.drag = null; showMedia.dragRect = null;
  const rect = [Math.min(start[0],end[0]),Math.min(start[1],end[1]),Math.abs(end[0]-start[0]),Math.abs(end[1]-start[1])];
  if (rect[2] < .01 || rect[3] < .01) { drawShowFace(); return; }
  showMedia.marks[$("#showFacePart").value] = rect; showMedia.talking = null; $("#showPlaceFace").hidden = false; drawShowFace();
});
$("#showVoiceStart").addEventListener("input", () => { showMedia.talking = null; $("#showPlaceFace").hidden = false; });
$("#showFaceClear").addEventListener("click", () => {showMedia.marks = {}; showMedia.talking = null; $("#showPlaceFace").hidden = false; drawShowFace();});
async function setShowVoice(file) {
  const voice = await uploadShowMedia("/show/voices",file);
  showMedia.voice = {path:voice.source,duration:voice.length}; $("#showVoiceStart").value = "0";
  $("#showFaceVoiceMode").value = "own"; $("#showOtherVoice").hidden = false;
  $("#showMediaStatus").textContent = "Voice ready. Save or preview the movement.";
}
$("#showFaceVoice").addEventListener("change", event => {
  const file = event.target.files[0]; event.target.value = ""; if (file) showMediaJob("Importing the voice…", ()=>setShowVoice(file));
});
$("#showFaceVoiceMode").addEventListener("change",()=>{$("#showOtherVoice").hidden = $("#showFaceVoiceMode").value === "mine";$("#showPlaceFace").hidden = false;});
$("#showImportVoiceLink").addEventListener("click",()=>showMediaJob("Importing the voice excerpt…",async()=>{
  const placement=showMediaPlacement(),start=Number($("#showVoiceURLStart").value);
  if(!Number.isFinite(start)||start<0)throw new Error("Choose a valid source start.");
  const ref=await api("/show/references/video",{...placement,url:$("#showVoiceURL").value.trim(),start,end:start+Math.min(30,placement.duration)});
  const data=await api(`/show/references/video/${encodeURIComponent(ref.id)}/download`,{audio_only:true,duration:placement.duration});
  await showPatch(`/show/review/${encodeURIComponent(data.proposal.id)}`,{status:"discarded"});
  showMedia.voice={path:data.proposal.params.path,duration:data.proposal.duration};$("#showVoiceStart").value="0";
  $("#showMediaStatus").textContent="Voice excerpt ready.";
}));
let showVoiceRecorder = null, showVoiceStream = null, showVoiceTimer = null;
function stopShowRecording() { if(showVoiceRecorder?.state === "recording")showVoiceRecorder.stop();showVoiceStream?.getTracks().forEach(track=>track.stop());clearTimeout(showVoiceTimer); }
$("#showRecordVoice").addEventListener("click",async()=>{
  if(showVoiceRecorder?.state === "recording"){stopShowRecording();return;}
  if(!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder){$("#showVoiceRecordStatus").textContent="Recording is unavailable in this browser. You can upload a voice file.";return;}
  try{
    const project=state.projectId;showVoiceStream=await navigator.mediaDevices.getUserMedia({audio:true});
    const mime=["audio/webm;codecs=opus","audio/mp4"].find(value=>MediaRecorder.isTypeSupported(value));
    showVoiceRecorder=new MediaRecorder(showVoiceStream,mime?{mimeType:mime}:{});const chunks=[];
    showVoiceRecorder.ondataavailable=event=>{if(event.data.size)chunks.push(event.data);};
    showVoiceRecorder.onstop=()=>{
      showVoiceStream?.getTracks().forEach(track=>track.stop());clearTimeout(showVoiceTimer);
      $("#showRecordVoice").textContent="Record with microphone";$("#showVoiceRecordStatus").textContent="";
      if(state.projectId!==project || !chunks.length)return;
      const blob=new Blob(chunks,{type:showVoiceRecorder.mimeType});
      showMediaJob("Saving the recording…",()=>setShowVoice(new File([blob],blob.type.includes("mp4")?"Recording.m4a":"Recording.webm",{type:blob.type})));
    };
    showVoiceRecorder.start();$("#showRecordVoice").textContent="Stop recording";$("#showVoiceRecordStatus").textContent="Recording… press Stop when finished.";showVoiceTimer=setTimeout(stopShowRecording,180000);
  }catch(error){showVoiceStream?.getTracks().forEach(track=>track.stop());$("#showVoiceRecordStatus").textContent="Microphone not available. Allow microphone access or upload a recording.";}
});
async function buildShowCharacterOverlay() {
  const placement=showMediaPlacement(),layer=showMedia.layer,marks=showMedia.marks;
  if(!layer)throw new Error("Prepare an image first.");
  const mouth=marks.mouth?{rect:marks.mouth}:null,eyes=[marks.leftEye,marks.rightEye].filter(Boolean).map(rect=>({rect}));
  if(!mouth&&!eyes.length)throw new Error("Mark a mouth or an eye first.");
  const own=$("#showFaceVoiceMode").value === "own";let voice=null;
  if(own){
    const start=Number($("#showVoiceStart").value);
    if(!showMedia.voice || !Number.isFinite(start)||start<0||start>=showMedia.voice.duration)throw new Error("Choose or record a voice, or switch back to Narrator.");
    voice=[showMedia.voice.path,start,Math.min(placement.duration,showMedia.voice.duration-start)];
  }
  const baseName=$("#showAssetName").textContent.replace(/ · photo character$/,"").replace(/ \(\d+\)$/,"");
  const known=new Set((await api("/show/characters")).items.map(item=>item.name));let name=baseName,index=2;while(known.has(name))name=`${baseName} (${index++})`;
  const rig=await api("/show/characters",{photo:layer.photo.photo,mask:layer.cut.mask,method:layer.cut.method,name,mouth,eyes,voice});
  const editing=showMedia.editing, width=Number($("#showAssetSize").value)*100,position=$("#showAssetPosition").value;
  return {placement,overlay:{...(editing?.type === "overlay" ? editing.raw : {}),id:editing?.type === "overlay" ? editing.id : crypto.randomUUID(),asset:rig.cutout,at:placement.at,duration:placement.duration,width,
    x:editing?.type === "overlay" ? editing.raw.x : position === "left"?8:position === "right"?92-width:(100-width)/2,y:editing?.type === "overlay" ? editing.raw.y : 12,
    action:mouth?"talk":"look",effect:"none",voice_mode:own?"own":"mine",voice,entrance:"cut",audio_mode:"own",intensity:1}};
}
$("#showFacePreview").addEventListener("click",()=>showMediaJob("Preparing the animation on your video…",async()=>{
  const {placement,overlay}=await buildShowCharacterOverlay();
  const fresh=await api("/show/scenes"),scene=fresh.scenes.find(s=>s.id===placement.scene_id),before=structuredClone(scene.overlays || []);
  try{
    await api(`/show/scenes/${encodeURIComponent(scene.id)}/overlays`,{overlays:[...before.filter(o=>o.id!==overlay.id),overlay]});
    const data=await api(`/show/scenes/${encodeURIComponent(scene.id)}/stickers/${encodeURIComponent(overlay.id)}/preview`,{});
    $("#showFaceVideo").src=data.url;$("#showFaceVideo").hidden=false;$("#showPlaceFace").hidden=false;
    $("#showMediaStatus").textContent="Preview ready, with your chosen voice. Save to keep it.";
  }finally{await api(`/show/scenes/${encodeURIComponent(scene.id)}/overlays`,{overlays:before});}
}));
$("#showPlaceFace").addEventListener("click",()=>showMediaJob("Saving the animated cutout…",async()=>{
  const {placement,overlay}=await buildShowCharacterOverlay();
  const fresh=await api("/show/scenes"),scene=fresh.scenes.find(s=>s.id===placement.scene_id);
  await saveShowOverlays(scene.id,[...scene.overlays.filter(o=>o.id!==overlay.id),overlay]);
  if(showMedia.editing?.type === "proposal")await retireReplacedShowEffect(placement);
  await showMediaChanged(scene.id);
}));
$("#showEffectDialog").addEventListener("close",()=>{$("#showAssetVideo").pause();$("#showFaceVideo").pause();stopShowRecording();});

$("#showSaveExcerpt").addEventListener("click",()=>showMediaJob("Saving this excerpt in the library…",async()=>{
  const asset=showMedia.asset,placement=showMediaPlacement(),start=Number($("#showClipStart").value),duration=Number($("#showLibraryLength").value);
  if(!asset || asset.mediaType!=="video" || !Number.isFinite(start+duration) || start<0 || duration<.1 || start+duration>asset.duration+.001 || duration>showEdit.scenes[showEdit.selected].end-placement.at)throw new Error("Choose a fragment inside this video and no longer than this part.");
  const data=await api(`/show/video-library/${encodeURIComponent(asset.id)}/place`,{...placement,duration});const id=data.proposal.id;
  try{
    await api(`/show/clips/${encodeURIComponent(id)}/settings`,{clip_start:start,matte:$("#showClipMatte").value,audio_mode:"mix",clip_audio:$("#showClipSound").checked});
    await showPatch(`/show/review/${encodeURIComponent(id)}`,{crop:showAssetCrop(),status:"discarded"});
    const saved=await api(`/show/clips/${encodeURIComponent(id)}/save-edit`,{project_id:state.projectId});
    const kept=await api("/montara/show/shelf",{asset_id:saved.asset.id,name:$("#showExcerptName").value.trim() || asset.name});
    await refreshShowLibrary();chooseShowAsset({...saved.asset,mediaType:"video",shelfId:kept.item.id});
    $("#showMediaStatus").textContent="Excerpt kept in your reusable library, available in other videos too.";
  }finally{await showPatch(`/show/review/${encodeURIComponent(id)}`,{status:"discarded"});}
}));

$("#showShelfHidden").addEventListener("change",()=>showMediaJob("Loading library…",refreshShowLibrary));
$("#showHideShelf").addEventListener("click",()=>showMediaJob("Updating the reusable library…",async()=>{if(!showMedia.asset?.shelfId)return;await api(`/montara/show/shelf/${showMedia.asset.shelfId}/visibility`,{hidden:true});$("#showAssetEditor").hidden=true;await refreshShowLibrary();$("#showMediaStatus").textContent="Hidden. Enable Show hidden reusable clips to restore it.";}));

$("#showMediaUploadInstead").onclick=()=>$("#showMediaFile").click();

function renderGreenCategory(){
  const list=$('#showMediaLibrary');list.replaceChildren();
  for(const item of (greenCatalog?.items||[]).filter(i=>i.category===greenCategory)){
    const button=document.createElement('button');button.type='button';button.className='show-library-item';
    const image=document.createElement('img');image.loading='lazy';image.alt='';image.src=item.thumbnail;
    const name=document.createElement('span');name.textContent=item.name;
    const detail=document.createElement('small');detail.textContent=`${item.duration.toFixed(1)}s · ${(item.bytes/1024).toFixed(0)} KB`;
    button.append(image,name,detail);button.onclick=()=>showMediaJob('Opening the green-screen clip…',async()=>{const data=await api('/montara/greenscreens/'+encodeURIComponent(item.id)+'/use',{project_id:state.projectId});chooseShowAsset({...data.asset,mediaType:'video'});$('#showMediaStatus').textContent='Ready. The background will be removed when placed.';});list.append(button);
  }
  if(!list.children.length)list.textContent='This collection is being prepared.';
}
$('#showLibraryCategories').onclick=event=>{const button=event.target.closest('[data-green-category]');if(!button||showMedia.busy)return;greenCategory=button.dataset.greenCategory;document.querySelectorAll('[data-green-category]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));refreshShowLibrary().catch(e=>$('#showMediaStatus').textContent=e.message);};
