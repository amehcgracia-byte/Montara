// Montara web interface. Talks to the unchanged engine API at /api/v1 and to
// Montara's own small endpoints at /montara/*.
"use strict";

const MODES = { youtube: "Stage", reel: "Push", show: "Show" };
const SUBJECTS = [
  ["general", "Everyone / wide"], ["singer", "Singer"], ["drummer", "Drums"], ["pianist", "Keys"],
  ["guitarist", "Guitar"], ["bassist", "Bass"], ["audience", "Audience"],
];
// The engine's fixed 360 viewpoint slots; the person names them freely.
const VIEW_SLOTS = [
  ["full_stage", "Wide"], ["singer", "Singer"], ["drummer", "Drums"], ["pianist", "Piano"],
  ["left", "Left"], ["right", "Right"], ["audience", "Audience"],
];
// 360 zoom levels. Rectilinear views stop at 110°; wider ones use the engine's stereographic presets.
const ZOOMS = [
  ["super_close", "Super close", 70, "linear"],
  ["close", "Close", 90, "linear"],
  ["normal", "Normal", 110, "linear"],
  ["wide", "Wide", 140, "megaview"],
  ["ultra_wide", "Ultra wide", 170, "ultrawide"],
];
// Who a 360 view shows. The same person filmed by a camera and a 360 view must share
// one identity so the edit never shows them twice in a row.
const WHO = [["general", "Wide"], ["singer", "Singer"], ["drummer", "Drums"], ["pianist", "Keys"],
  ["guitarist", "Guitar"], ["bassist", "Bass"], ["audience", "Audience"]];
const WHO_WORDS = { stage: "general", wide: "general", everyone: "general", band: "general", singer: "singer", vocals: "singer",
  voice: "singer", drums: "drummer", drummer: "drummer", keys: "pianist", piano: "pianist", guitar: "guitarist",
  bass: "bassist", audience: "audience", crowd: "audience" };
const SLOT_WHO = { full_stage: "general", singer: "singer", drummer: "drummer", pianist: "pianist", audience: "audience" };
function whoOf(slot, view) {
  if (view?.who) return view.who;
  const word = String(view?.subject || "").trim().toLowerCase();
  return WHO_WORDS[word] || SLOT_WHO[slot] || "general";
}
// How a flat camera was filmed; the engine only scores steadiness on handheld cameras.
const guessRole = (f) => (/fixed|tripod|static/i.test(f.name) ? "fixed_rear" : "handheld");
const zoomOf = (view) => ZOOMS.reduce((best, z) => (Math.abs(z[2] - view.fov) < Math.abs(best[2] - view.fov) ? z : best), ZOOMS[2]);
const BOX_HELP = {
  youtube: [
    ["Videos", "Every camera of the same performance: phone, camera, 360. They don't need to start at the same time; Montara syncs them by sound."],
    ["Audio", "The master: one mixed track of the song (WAV or MP3). Separate instrument or mic tracks come with the mixer, soon."],
    ["Not here", "Photos. Use Story for those (coming soon)."],
  ],
  reel: [
    ["Videos", "Any clips, as many as you like: each becomes short, punchy cuts."],
    ["Audio", "Optional: the song to cut on. Without it, the clips' own sound is used."],
    ["Not here", "Photos. Use Story for those (coming soon)."],
  ],
};

const state = {
  platform: null,
  files: [],          // {id, name, kind: video|master|songs|ignored|uploading|error, path, progress, sample, projection}
  uploads: 0,
  projectId: null,
  polling: null,
  framesPoll: null,
  viewpoints: {},     // path -> {slot: {yaw, pitch, fov, subject, enabled}}
  subjects: {},       // path -> subject
  roles: {},          // path -> fixed_rear | handheld
  branding: "montara",
  hasLogo: false,
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

async function api(path, body) {
  const options = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const response = await fetch(path.startsWith("/montara") ? path : `/api/v1${path}`, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if(response.status===410 || location.hostname.endsWith('.vercel.run') && (response.status===401 || [502,503,504].includes(response.status) && !data.error)){
      showPausedPreview();throw new Error('Your preview paused. Reopen Montara to resume your saved project.');
    }
    const error=new Error(data.error?.message || `Request failed (${response.status})`);error.code=data.error?.code;throw error;
  }
  if(body && /^\/show\/(narrator\/framing|captions\/(enabled|style)|scenes\/.+\/(overlays|decision)|review\/)/.test(path))document.dispatchEvent(new Event('montara:edit-saved'));
  return data;
}

function showPausedPreview(){
  const existing=document.querySelector('#pausedPreview');if(existing){if(!existing.open)existing.showModal();return;}
  const dialog=document.createElement('dialog');dialog.id='pausedPreview';dialog.className='cut-dialog';
  const title=document.createElement('h3');title.textContent='Your preview paused';
  const text=document.createElement('p');text.textContent='The test session stopped. Reopen Montara to resume your saved project, then check your last edit.';
  const link=document.createElement('a');link.className='btn primary';link.href='https://montara-tau.vercel.app/';link.textContent='Resume Montara';dialog.append(title,text,link);document.body.append(dialog);dialog.showModal();
}
function toast(text, error = false) {
  const el = $("#toast");
  el.textContent = text;
  el.className = "toast" + (error ? " err" : "");
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { el.hidden = true; }, 5000);
}

function escapeHtml(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const STEP_ORDER = ["footage", "showSetup", "showStyle", "cameras", "mix", "making", "frames", "showReview", "captions", "result"];
// Steps that apply to this video: no Mix step without separate tracks, no Captions outside Pulse.
function stepApplies(step) {
  if (state.platform === "show") return ["footage", "making", "showReview", "result"].includes(step);
  if (step === "showReview") return false;
  if (step === "cameras") return !state.files.length || videos().length > 0;
  if (step === "mix") return mixerMode();
  if (step === "captions") return state.platform === "reel";
  return true;
}
let showNavigating=false;
let introTimer = null;
function finishIntro() {
  if (!$("#home").hidden) { resetFlow(); show("mode"); }
}
function show(id) {
  clearTimeout(introTimer);
  stopFrameHover();
  document.body.classList.toggle("is-intro", id === "home");
  if (id === "home") introTimer = setTimeout(finishIntro, matchMedia("(prefers-reduced-motion: reduce)").matches ? 650 : 2450);
  if(state.platform==='show' && id!=='showReview'){$('#showSceneVideo').pause();clearTimeout(showEdit.previewTimer);showEdit.previewToken++;$('#showPreviewPart').disabled=false;showSmoothRequest++;$('#showLivePlay').disabled=false;if(['showSetup','showStyle'].includes(id))stopPolling();}
  const showStep=state.platform==='show' && ['showSetup','showStyle','making','showReview','result'].includes(id);
  $("#showNavigation").hidden=!showStep;
  $$("[data-show-step]").forEach(b=>b.classList.toggle('on',b.dataset.showStep===id));
  if(showStep && !showNavigating && history.state?.montaraStep!==id)history.pushState({montaraStep:id},'',location.href);
  $$(".screen").forEach((s) => { s.hidden = s.id !== id; });
  const inFlow = STEP_ORDER.includes(id) || id === "failed" || id === "mode";
  $("#steps").hidden = !inFlow || id === "mode" || state.platform==='show';
  $("#newVideo").hidden = inFlow;
  const current = STEP_ORDER.indexOf(id === "failed" ? "making" : id === "mode" || id === "showSetup" ? "footage" : id);
  $$("#steps span").forEach((span, index) => {
    span.hidden = !stepApplies(span.dataset.step);
    const position = STEP_ORDER.indexOf(span.dataset.step);
    span.classList.toggle("on", position === current);
    span.classList.toggle("done", position < current);
  });
  if(['showSetup','showStyle'].includes(id)&&typeof renderShowModeInputs==='function'){const anchor=$('#'+(id==='showSetup'?'showSetupInputs':'showStyleInputs'));anchor.append($('#showModeInputs'));renderShowModeInputs();}
  window.scrollTo({ top: 0 });
}
$("#home").addEventListener("click", finishIntro);
document.addEventListener("keydown", (event) => {
  if (!$("#home").hidden && ["Enter", "Escape", " "].includes(event.key)) { event.preventDefault(); finishIntro(); }
});

function todayName() {
  const d = new Date();
  return `Session ${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const videos = () => state.platform === 'youtube' && $('#stageAudioOnly').checked ? [] : state.files.filter((f) => f.kind === "video");
const audioTracks = () => state.files.filter((f) => f.kind === "master" || f.kind === "songs");
// Several audio files on Stage = separate instrument/mic tracks -> the mixer makes the master.
const audioOnly = () => state.platform === "youtube" && videos().length === 0 && audioTracks().length > 0;
const mixerMode = () => state.platform === "youtube" && (audioTracks().length >= 2 || audioOnly());
const isSphere = (f) => f.cameraType ? f.cameraType === "360" : f.projection === "equirect" || f.projection === "raw_insv" || /\.insv$/i.test(f.name);

// ---------- navigation ----------
document.addEventListener("click", (event) => {
  const go = event.target.closest("[data-go]");
  if (!go) return;
  event.preventDefault();
  const target = go.dataset.go === "footage" && state.platform === "show" ? "showSetup" : go.dataset.go;
  if ((target === "mode" || target === "home") && state.polling) return toast("A video is still being made.");
  if (target === "mode") resetFlow();
  show(target);
});

$$(".mode[data-platform]").forEach((card) => card.addEventListener("click", () => {
  state.platform = card.dataset.platform;
  if (state.platform === "show") { openShowSetup().catch(fail); return; }
  $("#modeLabel").textContent = MODES[state.platform];
  $("#durationRow").hidden = state.platform !== "reel";
  $("#formatRow").hidden = state.platform !== "reel";
  if (!$("#videoName").value) $("#videoName").value = todayName();
  $("#audioSub").textContent = state.platform === "youtube"
    ? "One track per instrument or mic and Montara mixes them for you, or one finished master."
    : "Optional: the song the reel should cut on.";
  state.files = state.files.filter((f) => !f.sample);
  renderFiles();
  show("footage");
  loadSamples().catch((error) => console.warn("Samples unavailable", error));
  offerRestore().catch((error) => console.warn("Footage memory", error));
  watchCompanion();
}));

function resetFlow() {
  stopPolling();
  state.localProject = null;
  state.savedLocally = false;
  range.start = 0; range.end = null;
  state.platform = null;
  state.files = [];
  state.projectId = null;
  state.captioned = false;
  cap.list = [];
  cap.timed = false;
  cap.selected = -1;
  $("#capText").value = "";
  $("#capTitle").value = "";
  state.viewpoints = {};
  state.subjects = {};
  state.roles = {};
  $("#videoName").value = "";
  $("#sampleNote").hidden = true;
  renderFiles();
}

// ---------- samples ----------
let sampleLoadToken=0;
async function loadSamples(variant = "") {
  if(state.platform === "show" && !variant)variant=showEdit.pace;
  if (state.files.some((f) => !f.sample)) return;  // the person already added their own files
  const token=++sampleLoadToken;
  const response = await fetch(`/montara/samples?platform=${encodeURIComponent(state.platform)}&variant=${variant}`);
  const data = await response.json().catch(() => ({enabled:false}));
  if (!response.ok) { $("#footageHint").textContent=data.error?.message || "The example could not load. Try again."; return; }
  if (!data.enabled || token!==sampleLoadToken || state.files.some(f=>!f.sample)) return;
  state.files=state.files.filter(f=>!f.sample);
  for (const [group, kind] of [["videos", "video"], ["master", "master"], ["songs", "songs"]]) {
    for (const item of data[group] || []) {
      state.files.push({ id: crypto.randomUUID(), name: kind === "master" && state.platform === "reel" ? "Song master · Much to Me" : item.path.split("/").pop(), kind, path: item.path, projection: item.projection, sample: true, showSource: state.platform === "show", ...(data.example ? {name:data.example.title,exampleDuration:data.example.duration}: {}) });
    }
  }
  for (const [path, slots] of Object.entries(data.viewpoints || {})) state.viewpoints[path] = structuredClone(slots);
  $("#sampleNote").hidden = false;
  state.sampleVariant = variant;
  if(state.platform === "show"){
    resetShowSources();
    if(data.inputs?.podcast)showSources.podcast=structuredClone(data.inputs.podcast);
    if(data.inputs?.story)showSources.story=structuredClone(data.inputs.story);
    showEdit.resume=null;
    $("#showInputVideo").src=`/montara/show/sample?variant=${encodeURIComponent(variant)}`;
    if($("#showExampleChoice").querySelector(`option[value="${variant}"]`))$("#showExampleChoice").value=variant;
    renderShowExample();
  }
  $("#variantRow").hidden = state.platform !== "youtube";
  $("#switchSample").textContent = variant === "master" ? "Use the separate tracks instead" : "Use the finished master instead";
  renderFiles();
}

$("#switchSample").addEventListener("click", () => loadSamples(state.sampleVariant === "master" ? "" : "master").catch(console.warn));

$("#clearSamples").addEventListener("click", () => {
  state.files = state.files.filter((f) => !f.sample);
  $("#sampleNote").hidden = true;
  renderFiles();
});

// ---------- footage ----------
$$("[data-drop]").forEach((drop) => {
  ["dragenter", "dragover"].forEach((name) => drop.addEventListener(name, (e) => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((name) => drop.addEventListener(name, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", (e) => {
    const files = [...e.dataTransfer.files];
    footageMemory.handlesFromDrop(e.dataTransfer).then((handles) => addFiles(files, handles), () => addFiles(files));
  });
  drop.querySelector("input").addEventListener("change", (e) => { addFiles([...e.target.files]); e.target.value = ""; });
  // Chrome/Edge: the system picker returns handles, so an interrupted upload can resume later.
  if (footageMemory.pickerAvailable) drop.querySelector(".drop-prompt")?.addEventListener("click", async (e) => {
    e.preventDefault();
    try { const {files, handles} = await footageMemory.pick(drop.dataset.drop); addFiles(files, handles); }
    catch (error) { if (error.name !== "AbortError") toast(error.message, true); }
  });
});
$("#reelDuration").addEventListener("input", (e) => { $("#reelDurationOut").textContent = `${e.target.value} s`; });

function addFiles(list, handles = []) {
  if (rejectRaw360(list)) return;
  if (state.files.some((f) => f.sample)) { state.files = state.files.filter((f) => !f.sample); $("#sampleNote").hidden = true; }
  $("#restoreNote").hidden = true;
  const unused = [...handles];
  for (const file of list) {
    const handle = unused.splice(unused.findIndex((h) => h.name === file.name) >>> 0, 1)[0];
    const entry = { id: crypto.randomUUID(), name: file.name, kind: "uploading", progress: 0, localFile: file,
      memory: { platform: state.platform, size: file.size, lastModified: file.lastModified, handle: handle?.name === file.name ? handle : undefined } };
    state.files.push(entry);
    remember(entry);
    upload(file, entry);
  }
  renderFiles();
}

// ---------- idle page: after 30 min without use, pause it ----------
// The lab server switches itself off when nobody uses it (deploy/vm/idle_shutdown.sh);
// background polls do not keep it awake, and an idle page says so instead of failing.
const IDLE_PAGE_MS = 30 * 60 * 1000;
let lastInput = Date.now();
["pointerdown", "keydown", "wheel", "touchstart"].forEach((name) => addEventListener(name, () => { lastInput = Date.now(); }, { passive: true }));
setInterval(() => {
  if (Date.now() - lastInput < IDLE_PAGE_MS || state.polling || state.uploads || document.querySelector("#idlePause")) return;
  clearTimeout(companionWatch);
  const dialog = document.createElement("dialog");
  dialog.id = "idlePause"; dialog.className = "cut-dialog";
  dialog.innerHTML = '<h3>Montara paused</h3><p>Nobody used this page for 30 minutes. Your files and projects are kept; the server may switch itself off to save resources.</p><button class="btn primary" type="button">Continue</button>';
  dialog.querySelector("button").onclick = () => location.reload();
  document.body.append(dialog); dialog.showModal();
}, 60 * 1000);

// ---------- song range: choose the part of the song the video covers ----------
const range = { start: 0, end: null, duration: 0 };
let rangeSourcesList = [];
const clock = (t) => { t = Math.max(0, Math.floor(t || 0)); const h = Math.floor(t / 3600), m = Math.floor(t / 60) % 60, s = String(t % 60).padStart(2, "0"); return h ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`; };
function audioUrl(f) {
  if (f.localFile) return (f.objectUrl ||= URL.createObjectURL(f.localFile));
  return f.path ? `/montara/audio?path=${encodeURIComponent(f.path)}` : "";
}
function openSongRange() {
  rangeSourcesList = state.platform === "youtube" ? audioTracks().filter((f) => audioUrl(f)) : [];
  $("#songRange").hidden = !rangeSourcesList.length;
  if (!rangeSourcesList.length) return;
  const select = $("#rangeTrack");
  const preferred = rangeSourcesList.findIndex((f) => /\b(ov|room|mix|master|ambi|stereo|lr)\b/i.test(f.name.replace(/[_.-]/g, " ")));
  select.innerHTML = rangeSourcesList.map((f, i) => `<option value="${i}">${escapeHtml(f.name)}</option>`).join("");
  select.value = String(preferred >= 0 ? preferred : 0);
  select.hidden = rangeSourcesList.length < 2;
  const url = audioUrl(rangeSourcesList[Number(select.value)]);
  if ($("#rangeAudio").dataset.url !== url) { $("#rangeAudio").src = url; $("#rangeAudio").dataset.url = url; }
  drawRange();
}
function drawRange() {
  const audio = $("#rangeAudio"), d = range.duration || audio.duration || 0;
  const end = range.end ?? d;
  $("#rangeFill").style.left = d ? `${(range.start / d) * 100}%` : "0";
  $("#rangeFill").style.width = d ? `${Math.max(0, (end - range.start) / d) * 100}%` : "100%";
  $("#rangeHead").style.left = d ? `${(audio.currentTime / d) * 100}%` : "0";
  $("#rangeStartOut").textContent = clock(range.start);
  $("#rangeEndOut").textContent = range.end === null ? (d ? clock(d) : "end") : clock(range.end);
}
$("#rangeTrack").addEventListener("change", () => {
  const audio = $("#rangeAudio"), t = audio.currentTime, url = audioUrl(rangeSourcesList[Number($("#rangeTrack").value)]);
  audio.src = url; audio.dataset.url = url;
  audio.addEventListener("loadedmetadata", () => { audio.currentTime = t; }, { once: true });
});
$("#rangeAudio").addEventListener("loadedmetadata", () => { range.duration = $("#rangeAudio").duration || 0; drawRange(); });
$("#rangeAudio").addEventListener("timeupdate", drawRange);
$("#rangeStart").addEventListener("click", () => {
  range.start = $("#rangeAudio").currentTime || 0;
  if (range.end !== null && range.end <= range.start + 1) range.end = null;
  drawRange();
});
$("#rangeEnd").addEventListener("click", () => {
  const t = $("#rangeAudio").currentTime || 0;
  if (t <= range.start + 1) return toast("Mark the end after the start.", true);
  range.end = t; drawRange();
});
$("#rangeReset").addEventListener("click", () => { range.start = 0; range.end = null; drawRange(); });
$("#rangeBar").addEventListener("click", (e) => {
  const audio = $("#rangeAudio"), d = range.duration || audio.duration || 0, box = $("#rangeBar").getBoundingClientRect();
  if (d) audio.currentTime = Math.max(0, Math.min(d, ((e.clientX - box.left) / box.width) * d));
});

// ---------- companion: offer it on a Mac, notice when it starts ----------
const isDesktopMac = /Macintosh|Mac OS X/.test(navigator.userAgent) && !/iPhone|iPad/.test(navigator.userAgent) && navigator.maxTouchPoints < 2;
let companionWatch = null;
async function watchCompanion() {
  clearTimeout(companionWatch);
  const info = await montaraCompanion.detect();
  $("#companionNote").hidden = !info;
  $("#companionOffer").hidden = Boolean(info) || !isDesktopMac || state.platform === "show";
  if (!info && !$("#footage").hidden) companionWatch = setTimeout(watchCompanion, 4000);  // starts while the person installs it
  else if (info && renderFiles.companionSeen === false) toast("Companion connected: videos stay on your computer.");
  renderFiles.companionSeen = Boolean(info);
}

// ---------- footage memory: survive a reload ----------
function remember(entry) {
  if (!entry.memory) return;
  const { id, name, kind, path, reason, projection, duration, uploadId, small, original } = entry;
  footageMemory.save({ id, name, kind: kind === "error" ? "uploading" : kind, path, reason, projection, duration, uploadId, small, original, ...entry.memory });
}
async function offerRestore() {
  const records = (await footageMemory.list(state.platform)).filter((r) => !state.files.some((f) => f.id === r.id));
  state.restorable = records;
  const done = records.filter((r) => r.path).length;
  $("#restoreText").textContent = `${records.length} file${records.length === 1 ? "" : "s"} from your last visit` + (done < records.length ? ` (${records.length - done} still to upload).` : ".");
  $("#restoreNote").hidden = !records.length || state.files.some((f) => !f.sample);
}
$("#restoreForget").addEventListener("click", async () => { await footageMemory.clear(state.platform); state.restorable = []; $("#restoreNote").hidden = true; });
$("#restoreFiles").addEventListener("click", async () => {
  const records = state.restorable || [];
  $("#restoreNote").hidden = true;
  state.files = state.files.filter((f) => !f.sample);
  $("#sampleNote").hidden = true;
  for (const record of records) {
    const entry = { id: record.id, name: record.name, kind: record.kind, path: record.path, reason: record.reason, projection: record.projection,
      duration: record.duration, uploadId: record.uploadId, small: record.small, original: record.original, progress: 0,
      memory: { platform: record.platform, size: record.size, lastModified: record.lastModified, handle: record.handle } };
    state.files.push(entry);
    if (record.path) continue;
    let file = null;
    try { file = await footageMemory.reopen(record); } catch (error) { console.warn(error); }
    if (file) { entry.kind = "uploading"; upload(file, entry); }  // resumable uploads continue where they stopped
    else { entry.kind = "error"; entry.error = "Add this file again to continue its upload"; }
  }
  renderFiles();
});

// With the companion running, a video becomes a small version on the person's
// computer and only that is uploaded; the original stays where it is.
async function uploadSmall(file, entry) {
  entry.viaCompanion = true;
  state.uploads += 1;
  let small = null;
  try {
    small = await montaraCompanion.smallVersion(file, (phase, progress) => { entry.phase = phase; entry.progress = progress; renderFiles(); }, () => entry.removed);
  } catch (error) { console.warn(error); }
  if (!entry.removed) {
    entry.phase = small ? "Uploading small version" : "";
    entry.progress = 0;
    if (small) { entry.small = true; entry.original = small.original; remember(entry); }
    upload(small ? small.file : file, entry);
  }
  state.uploads -= 1;
  renderFiles();
}

function upload(file, entry) {
  if (montaraCompanion.info && !entry.viaCompanion && montaraCompanion.isVideo(file)) return uploadSmall(file, entry);
  if (file.size > 8 * 1024 * 1024) return uploadInParts(file, entry);
  state.uploads += 1;
  const xhr = new XMLHttpRequest();
  entry.xhr = xhr;
  xhr.open("POST", "/api/v1/wizard/upload");
  xhr.setRequestHeader("Content-Type", "application/octet-stream");
  xhr.setRequestHeader("X-Zucker-Filename", encodeURIComponent(file.name));
  xhr.upload.onprogress = (e) => { if (e.lengthComputable) { entry.progress = e.loaded / e.total; renderFiles(); } };
  xhr.onload = () => {
    state.uploads -= 1;
    let data = {};
    try { data = JSON.parse(xhr.responseText); } catch { /* handled below */ }
    if (xhr.status >= 400) {
      entry.kind = "error";
      entry.error = data.error?.message || "Upload failed";
    } else {
      const found = ["videos", "master", "songs", "ignored"].map((kind) => [kind, (data[kind] || [])[0]]).find(([, item]) => item);
      if (found) {
        entry.kind = found[0] === "videos" ? "video" : found[0];
        entry.path = found[1].path;
        entry.reason = found[1].reason || found[1].note;
        entry.projection = found[1].projection;
        entry.duration = Number(found[1].duration) || 0;
        remember(entry);
      } else {
        entry.kind = "error";
        entry.error = "Not a usable media file";
      }
    }
    renderFiles();
  };
  xhr.onerror = () => { state.uploads -= 1; entry.kind = "error"; entry.error = "Connection interrupted"; renderFiles(); };
  xhr.onabort = () => { state.uploads -= 1; renderFiles(); };
  xhr.send(file);
}

async function uploadInParts(file, entry) {
  state.uploads += 1;
  try {
    const data = await sendResumableUpload(file, progress => { entry.progress = progress; renderFiles(); }, id => {entry.uploadId = id; remember(entry);}, () => entry.removed);
    const found = ['videos', 'master', 'songs', 'ignored'].map(kind => [kind, (data[kind] || [])[0]]).find(([, item]) => item);
    if (!found) throw new Error('Not a usable media file');
    entry.kind = found[0] === 'videos' ? 'video' : found[0];
    entry.path = found[1].path; entry.reason = found[1].reason || found[1].note; entry.projection = found[1].projection;
    entry.duration = Number(found[1].duration) || 0;
    remember(entry);
  } catch (error) {
    if (entry.removed) {
      if (entry.uploadId) fetch(`/montara/uploads/${entry.uploadId}`, {method: 'DELETE'}).catch(() => {});
      return;
    }
    entry.kind = 'error'; entry.error = error.message;
  } finally { state.uploads -= 1; renderFiles(); }
}

const KIND_LABEL = { video: "VIDEO", master: "AUDIO", songs: "SONGS", ignored: "SKIPPED", uploading: "UPLOAD", error: "ERROR" };
const isAudioEntry = (f) => f.kind === "master" || f.kind === "songs" || (f.kind !== "video" && /\.(wav|mp3|m4a|aiff?|flac|ogg)$/i.test(f.name));
function fileLabel(f) {
  if (f.kind === "video") return isSphere(f) ? "360" : "VIDEO";
  if (f.kind === "master" || f.kind === "songs") return mixerMode() ? "TRACK" : "MASTER";
  return KIND_LABEL[f.kind] || f.kind.toUpperCase();
}
function fileRow(f) {
  return `
    <li>
      <span class="kind ${f.kind}">${fileLabel(f)}</span>
      <span class="name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</span>
      <span class="state">${f.kind === "uploading" ? (f.phase ? escapeHtml(f.phase) + " " : "") + Math.round(f.progress * 100) + "%" : f.small && f.kind === "video" ? "Ready · small version" : f.kind === "error" ? escapeHtml(f.error) : f.kind === "ignored" ? escapeHtml(f.reason || "not used") : "Ready"}</span>
      <button class="remove" data-remove-file="${f.id}" type="button" aria-label="Remove ${escapeHtml(f.name)}" title="Remove">×</button>
      ${f.kind === "uploading" ? `<span class="bar"><i style="width:${Math.round(f.progress * 100)}%"></i></span>` : ""}
    </li>`;
}
// Every file row can be removed, also while it uploads: the upload stops and
// an unfinished server copy is discarded. Finished files simply leave this project.
document.addEventListener('click', event => {
  const button = event.target.closest('[data-remove-file]');
  if (!button) return;
  const entry = state.files.find(f => f.id === button.dataset.removeFile);
  if (!entry) return;
  entry.removed = true;
  footageMemory.forget(entry.id);
  if (entry.xhr && entry.kind === 'uploading') entry.xhr.abort();
  if (entry.uploadId && entry.kind !== 'video' && entry.kind !== 'master' && entry.kind !== 'songs') {
    fetch(`/montara/uploads/${entry.uploadId}`, {method: 'DELETE'}).catch(() => {});
  }
  state.files = state.files.filter(f => f !== entry);
  if (!state.files.some(f => f.sample)) $('#sampleNote').hidden = true;
  renderFiles();
});
function renderFiles() {
  $('#stageSessionOptions').hidden = state.platform !== 'youtube';
  $('[data-drop="video"]').closest('.box').hidden = state.platform === 'youtube' && $('#stageAudioOnly').checked;
  $("#audioFiles").innerHTML = state.files.filter(isAudioEntry).map(fileRow).join("");
  $("#audioFiles").classList.toggle("compact", state.files.filter(isAudioEntry).length > 4);
  $("#videoFiles").innerHTML = state.files.filter((f) => !isAudioEntry(f)).map(fileRow).join("");
  const master = state.files.find((f) => f.kind === "master");
  let hint = "";
  let ready = (videos().length > 0 || audioOnly()) && state.uploads === 0;
  if (mixerMode()) hint = `${audioTracks().length} separate tracks: Montara will mix them for you, then you can adjust every fader.`;
  else if (state.platform === "youtube" && !master) { hint = "Stage needs the master audio (one mixed track of the song) to sync every camera."; ready = false; }
  if (state.platform === "reel" && !master && videos().length > 1) hint = "Tip: add the song so the reel cuts on the music.";
  if (state.platform === "reel" && master) hint = "The reel uses your song master. Camera sound is muted.";
  if (state.platform === "reel" && state.files.some(f=>f.sample) && !master) { hint = "The example song master is missing. Reopen the example."; ready = false; }
  if (state.uploads) hint = "Uploading…";
  if (state.platform === 'youtube' && $('#fullSessionOn').checked && !state.uploads && audioTracks().length) hint = 'Find and review the songs, then export their mixes. This session step exports audio.';
  const longest = Math.max(0, ...state.files.filter(isAudioEntry).map(f => f.duration || 0));
  if (state.platform === 'youtube' && !$('#fullSessionOn').checked && !state.uploads && longest > 20 * 60) hint = `Your audio is ${Math.round(longest / 60)} min long. If it is a whole session and you want one song, tick Full session to find the songs first, or trim the tracks to that song.`;
  if (!audioOnly() && state.branding === "mine" && !state.hasLogo) { hint = "Choose your logo, or pick another option."; ready = false; }
  $("#footageHint").textContent = hint;
  $("#continueFootage").disabled = !ready;
  if (state.platform === "show") renderShowInput();
}

// ---------- branding ----------
async function loadBranding() {
  try {
    const data = await api("/montara/branding");
    state.branding = data.mode;
    state.hasLogo = data.has_logo;
    const radio = document.querySelector(`input[name=branding][value="${data.mode}"]`);
    if (radio) radio.checked = true;
    if (data.has_logo) showLogoPreview();
  } catch (error) { console.warn(error); }
}
function showLogoPreview() {
  const img = $("#myLogoPreview");
  img.src = `/montara/logo?t=${Date.now()}`;
  img.hidden = false;
  $("#pickLogo").textContent = "Change logo";
}
$$("input[name=branding]").forEach((radio) => radio.addEventListener("change", () => {
  state.branding = radio.value;
  if (radio.value === "mine" && !state.hasLogo) $("#logoInput").click();
  renderFiles();
}));
$("#pickLogo").addEventListener("click", (e) => { e.preventDefault(); $("#logoInput").click(); });
$("#logoInput").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  const response = await fetch("/montara/logo", { method: "POST", body: form });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) return toast(data.error?.message || "Logo upload failed", true);
  state.hasLogo = true;
  state.branding = "mine";
  document.querySelector('input[name=branding][value="mine"]').checked = true;
  showLogoPreview();
  renderFiles();
});

// ---------- continue: register the project, then cameras ----------
$("#continueFootage").addEventListener("click", () => registerProject().catch(fail));

// Pulse format: the engine's reel_aspect (9:16, 16:9, mix = framed, mix_vertical_horizontal = mixed).
const reelFormat = () => document.querySelector("input[name=format]:checked")?.value || "9:16";
const engineReelFormat = () => ({"16:9":"mix",mix:"mix_vertical_horizontal",mix_vertical_horizontal:"mix_vertical_horizontal"})[reelFormat()] || "9:16";
$$("input[name=format]").forEach((radio) => radio.addEventListener("change", () => {
  $("#mixShareRow").hidden = reelFormat() !== "mix";
}));

function inputs() {
  const master = mixerMode() ? (state.mixMaster ? { path: state.mixMaster } : null) : state.files.find((f) => f.kind === "master");
  return {
    master: master?.path || "",
    songs: state.files.find((f) => f.kind === "songs")?.path || "",
    videos: videos().map((f) => f.path),
  };
}

async function registerProject() {
  if (state.platform === 'youtube' && $('#fullSessionOn').checked) return openFullSession();
  $("#continueFootage").disabled = true;
  try {
    if (audioOnly()) { state.mixMaster = null; state.projectId = null; return await openMixer(); }
    await api("/montara/branding", { mode: state.branding });
    const name = $("#videoName").value.trim() || todayName();
    const data = inputs();
    if (montaraCompanion.info && !state.localProject) {
      toast("Choose on your Mac where Montara keeps this project (a window opened).");
      state.localProject = await montaraCompanion.projectFolder(name, state.files.filter((f) => f.original).map((f) => f.original));
      if (state.localProject) toast(`Project folder: ${state.localProject.folder}`);
    }
    await api("/wizard/projects/new", {});
    const draft = await api("/wizard/draft", { name, project_id: null, platform: state.platform, audio_paths: data.master ? [data.master] : [], ...data });
    state.mixMaster = null;
    state.projectId = draft.project_id;
  } finally {
    $("#continueFootage").disabled = false;
  }
  if (state.platform === "show") return makeShow();
  const needsCameras = videos().length > 0;
  if (!needsCameras) return afterCameras();
  renderCameras();
  openSongRange();
  show("cameras");
}

// ---------- cameras & 360 viewpoints ----------
function cameraTypeOf(f){return f.cameraType || (isSphere(f)?'360':(state.roles[f.path] || guessRole(f))==='fixed_rear'?'fixed':'moving');}
function renderCameras() {
  $('#cameraList').innerHTML=videos().map((f,index)=>`<div class="cam"><span class="kind video">${String(index+1).padStart(2,'0')}</span><span class="name">${escapeHtml(f.name)}</span><span class="camsel"><label>Camera type<select data-camera-type="${escapeHtml(f.path)}" aria-label="Camera type for ${escapeHtml(f.name)}">${[['360','360'],['fixed','Fixed camera'],['moving','Moving camera']].map(([value,label])=>`<option value="${value}" ${cameraTypeOf(f)===value?'selected':''}>${label}</option>`).join('')}</select></label></span></div>`).join('');
  $$('[data-camera-type]').forEach(select=>select.onchange=()=>{const f=videos().find(v=>v.path===select.dataset.cameraType);f.cameraType=select.value;if(select.value!=='360')state.roles[f.path]=select.value==='fixed'?'fixed_rear':'handheld';renderCameras();});
  const spheres=videos().filter(isSphere);
  $('#sphereList').innerHTML=spheres.map((f,index)=>`<div class="sphere" data-sphere="${index}"><h3><span class="kind video">360</span> ${escapeHtml(f.name)}</h3><p class="hint">Choose a viewpoint, click where it should look, and give it a name.</p><div class="sphere-body"><ul class="slots"></ul><div class="pano-wrap"><div class="pano"><div class="pano-img"></div><span class="loading">Loading 360 frame…</span></div><p class="hint tiny">Drag to turn · click to place the viewpoint</p><div class="preview"><div class="pv"><img alt="" hidden draggable="false"></div><span class="hint">Drag to aim, scroll to zoom.</span></div></div></div></div>`).join('');
  spheres.forEach((f,index)=>setupSphere(f,$(`[data-sphere="${index}"]`)));
}

function setupSphere(file, root) {
  const views = state.viewpoints[file.path] ||= {};
  let active = Object.keys(views).find((slot) => views[slot].enabled) || "full_stage";
  const pano = root.querySelector(".pano");
  const panoImg = pano.querySelector(".pano-img");
  // The panorama scrolls sideways (it wraps around); start with the stage in the middle.
  const anchor = views.full_stage || Object.values(views).find((v) => v.enabled);
  let offset = anchor ? wrap(0.5 - (anchor.yaw + 180) / 360) : 0;
  const frame = new Image();
  frame.onload = () => { pano.querySelector(".loading").hidden = true; panoImg.style.backgroundImage = `url("${frame.src}")`; place(); preview(); };
  frame.onerror = () => { pano.querySelector(".loading").textContent = "Could not load the 360 frame."; };
  frame.src = `/api/v1/wizard/spherical-source-frame?source=${encodeURIComponent(file.path)}`;

  function wrap(v) { return ((v % 1) + 1) % 1; }
  new ResizeObserver(() => place()).observe(pano);
  function place() {
    // Percentages do nothing on a full-width background: shift it in pixels (it repeats sideways).
    panoImg.style.backgroundPositionX = `${offset * panoImg.clientWidth}px`;
    panoImg.style.backgroundSize = "100% 100%";
    drawMarkers();
  }

  function renderSlots() {
    root.querySelector(".slots").innerHTML = VIEW_SLOTS.map(([slot, fallback]) => {
      const view = views[slot];
      const zoom = view ? zoomOf(view)[0] : "normal";
      return `<li class="slot ${slot === active ? "on" : ""} ${view?.enabled ? "set" : ""}" data-slot="${slot}">
        <input type="checkbox" ${view?.enabled ? "checked" : ""} title="Use this point of view">
        <input type="text" value="${escapeHtml(view?.subject || fallback)}" maxlength="24" title="Name">
        <select class="who" title="Who it shows">${WHO.map(([value, label]) => `<option value="${value}" ${whoOf(slot, view) === value ? "selected" : ""}>${label}</option>`).join("")}</select>
        <select class="zoom" title="Zoom">${ZOOMS.map(([value, label]) => `<option value="${value}" ${zoom === value ? "selected" : ""}>${label}</option>`).join("")}</select>
      </li>`;
    }).join("");
    root.querySelectorAll(".slot").forEach((li) => {
      const slot = li.dataset.slot;
      li.addEventListener("click", (e) => { if (e.target.tagName !== "INPUT" && e.target.tagName !== "SELECT") { select(slot); } });
      li.querySelector("input[type=checkbox]").addEventListener("change", (e) => {
        if (!views[slot]) { select(slot); return toast("Now click in the 360 image where this view should look."); }
        views[slot].enabled = e.target.checked; drawMarkers();
      });
      li.querySelector("input[type=text]").addEventListener("input", (e) => { if (views[slot]) { views[slot].subject = e.target.value; drawMarkers(); } });
      li.querySelector("input[type=text]").addEventListener("focus", () => { active = slot; root.querySelectorAll(".slot").forEach((x) => x.classList.toggle("on", x.dataset.slot === slot)); drawMarkers(); preview(); });
      li.querySelector("select.who").addEventListener("change", (e) => { if (views[slot]) views[slot].who = e.target.value; });
      li.querySelector("select.zoom").addEventListener("change", (e) => {
        if (!views[slot]) return;
        setZoom(slot, ZOOMS.find(([value]) => value === e.target.value));
        if (slot === active) preview();
      });
    });
  }

  function select(slot) { active = slot; renderSlots(); drawMarkers(); preview(); }
  function setZoom(slot, zoom) { views[slot].fov = zoom[2]; views[slot].projection_preset = zoom[3]; }

  function drawMarkers() {
    pano.querySelectorAll(".pin").forEach((pin) => pin.remove());
    for (const [slot, view] of Object.entries(views)) {
      if (!view.enabled && slot !== active) continue;
      const pin = document.createElement("span");
      pin.className = "pin" + (slot === active ? " on" : "");
      pin.style.left = `${wrap((view.yaw + 180) / 360 + offset) * 100}%`;
      pin.style.top = `${(90 - view.pitch) / 180 * 100}%`;
      pin.textContent = view.subject || slot;
      pano.append(pin);
    }
  }

  // The view is drawn in the browser from the panorama already on screen (WebGL), so
  // aiming and zooming are instant. The engine's exact view (wide presets are not
  // rectilinear) replaces it once the person stops moving, if it is still current.
  let previewTimer = null, previewToken = 0;
  function preview() {
    const view = views[active];
    const img = root.querySelector(".preview img");
    if (!view) { img.hidden = true; return; }
    const token = ++previewToken;
    let local = "";
    // Wide and Ultra wide are stereographic in the engine (fisheye look), not stretched rectilinear.
    const stereographic = ["megaview", "ultrawide", "tiny_planet", "crystal_ball"].includes(view.projection_preset || zoomOf(view)[3]);
    try { local = webSphericalStill(frame, { yaw: view.yaw, pitch: view.pitch, fov: view.fov, projection: stereographic ? "sg" : "flat" }); } catch (error) { console.warn(error); }
    if (local) { img.src = local; img.hidden = false; }
    clearTimeout(previewTimer);
    previewTimer = setTimeout(() => {
      const zoom = zoomOf(view);
      const params = new URLSearchParams({ source: file.path, shot: active, yaw: view.yaw, pitch: view.pitch, fov: view.fov,
        projection_preset: view.projection_preset || zoom[3], time_sec: 20 });
      const exact = new Image();
      exact.onload = () => { if (token === previewToken) { img.src = exact.src; img.hidden = false; } };
      exact.src = `/api/v1/wizard/spherical-preview?${params}`;
    }, local ? 1500 : 0);
  }

  // Panorama: drag turns it, a click (no drag) places the selected point of view.
  let drag = null;
  pano.addEventListener("pointerdown", (e) => { drag = { x: e.clientX, start: offset, moved: false }; pano.setPointerCapture(e.pointerId); });
  pano.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const dx = (e.clientX - drag.x) / pano.getBoundingClientRect().width;
    if (Math.abs(e.clientX - drag.x) > 4) drag.moved = true;
    if (drag.moved) { offset = wrap(drag.start + dx); place(); }
  });
  pano.addEventListener("pointerup", (e) => {
    const wasDrag = drag?.moved;
    drag = null;
    if (wasDrag) return;
    const rect = pano.getBoundingClientRect();
    const x = wrap((e.clientX - rect.left) / rect.width - offset);
    const y = Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height));
    const label = VIEW_SLOTS.find(([slot]) => slot === active)[1];
    const previous = views[active];
    views[active] = {
      yaw: Math.round((x * 360 - 180) * 10) / 10,
      pitch: Math.round((90 - y * 180) * 10) / 10,
      fov: previous?.fov || 110,
      projection_preset: previous?.projection_preset || "linear",
      subject: previous?.subject || label,
      enabled: true,
    };
    renderSlots(); drawMarkers(); preview();
  });

  // Preview: drag to aim the selected view, scroll to change the zoom level.
  const pv = root.querySelector(".pv");
  let aim = null;
  pv.addEventListener("pointerdown", (e) => { const view = views[active]; if (!view) return; aim = { x: e.clientX, y: e.clientY, yaw: view.yaw, pitch: view.pitch }; pv.setPointerCapture(e.pointerId); });
  pv.addEventListener("pointermove", (e) => {
    const view = views[active];
    if (!aim || !view) return;
    const width = pv.getBoundingClientRect().width;
    const degPerPx = Math.min(view.fov, 110) / width;
    view.yaw = Math.round(((((aim.yaw - (e.clientX - aim.x) * degPerPx) + 180) % 360 + 360) % 360 - 180) * 10) / 10;
    view.pitch = Math.round(Math.max(-89, Math.min(89, aim.pitch + (e.clientY - aim.y) * degPerPx)) * 10) / 10;
    drawMarkers(); preview();
  });
  pv.addEventListener("pointerup", () => { if (aim) { aim = null; preview(); } });
  pv.addEventListener("wheel", (e) => {
    const view = views[active];
    if (!view) return;
    e.preventDefault();
    const index = ZOOMS.indexOf(zoomOf(view));
    const next = ZOOMS[Math.max(0, Math.min(ZOOMS.length - 1, index + (e.deltaY > 0 ? 1 : -1)))];
    setZoom(active, next);
    renderSlots(); preview();
  }, { passive: false });

  renderSlots();
  preview();
}

$("#continueCameras").addEventListener("click", () => saveCameras().then(afterCameras).catch(fail));

function afterCameras() {
  return mixerMode() ? openMixer() : make();
}

// ---------- mixer ----------
const mix = { job: null, plan: null, ctx: null, nodes: {}, buffers: {}, playing: false, startedAt: 0, offset: 0, master: null, timer: null };

async function openMixer(sessionTracks = null) {
  if (!sessionTracks) fullSession.active = false;
  show("mix");
  stopMix();
  $("#mixStatus").classList.remove("done");
  $("#mixStatusText").textContent = "Mixing your tracks automatically…";
  $("#transport").hidden = true;
  $("#referenceRow").hidden = true;
  $("#useMix").disabled = true;
  $("#strips").innerHTML = "";
  const job = await api("/montara/mix", { tracks: sessionTracks || audioTracks().map((f) => f.path) });
  mix.job = job.id;
  $("#referenceName").textContent = "Automatic (no reference)";
  $("#referenceStatus").hidden = true;
  $("#referenceUrl").value = "";
  $("#useReferenceLink").disabled = false;
  $("#pickReference").disabled = false;
  mix.buffers = {};
  mix.fxBuffers = {};
  const ready = await pollMix((j) => j.status !== "analyzing");
  if (ready.status === "failed") throw new Error(ready.error || "The automatic mix failed");
  mix.plan = { ...ready.plan, tracks: ready.plan.tracks.map(track => MixLevels.prepare(sessionTracks ? {...track, active: true} : track)) };
  renderStrips();
  $("#mixStatusText").textContent = "Loading the tracks for the preview…";
  await loadBuffers();
  await animateMixFaders();
  $("#mixStatus").classList.add("done");
  $("#mixStatusText").textContent = "Auto-mix ready. Faders start where Montara put them.";
  $("#transport").hidden = false;
  $("#referenceRow").hidden = false;
  if (sessionTracks) $('#mixStatusText').textContent = 'Previewing the first selected song. Your fader adjustments apply to every selected song.';
  $("#useMix").disabled = false;
}

async function pollMix(done) {
  for (;;) {
    const job = await api(`/montara/mix/${mix.job}`);
    if (done(job) || job.status === "failed") return job;
    await new Promise((r) => setTimeout(r, 1000));
  }
}

const dbToGain = (db) => Math.pow(10, db / 20);
function trackGain(track) {
  return MixLevels.gain(track);
}

function renderStrips() {
  $("#strips").innerHTML = mix.plan.tracks.map((t, i) => `
    <div class="strip ${t.mute || t.active === false ? "off" : ""}" data-track="${i}" title="${escapeHtml(t.active === false ? `${t.file}: almost no signal, so the mix leaves it out` : t.file)}">
      <small>${escapeHtml(t.role)}</small>
      <span class="db">${(t.fader_db >= 0 ? "+" : "") + Number(t.fader_db).toFixed(1)} dB</span>
      <input type="range" min="${Math.min(-60, Math.floor(t.fader_db))}" max="${Math.max(12, Math.ceil(t.fader_db))}" step="0.01" value="${t.fader_db}" aria-label="${escapeHtml(t.name)} fader">
      ${t.active === false ? `<button class="mute" disabled>NO SIGNAL</button>` : `<button class="mute ${t.mute ? "on" : ""}">${t.mute ? "OFF" : "ON"}</button>`}
      <b>${escapeHtml(t.name)}</b>
      <button class="fx-toggle" aria-expanded="false">FX</button>
      <div class="track-fx" hidden>
        ${["reverb", "delay"].map((effect) => `<label><input type="checkbox" data-effect="${effect}" ${t.fx?.[effect]?.enabled ? "checked" : ""}>${effect === "reverb" ? "Reverb" : "Delay"}</label><input class="fx-amount" data-effect="${effect}" type="range" min="0" max="100" value="${t.fx?.[effect]?.amount ?? 35}" aria-label="${escapeHtml(t.name)} ${effect} intensity"><output data-effect="${effect}">${t.fx?.[effect]?.amount ?? 35}%</output>`).join("")}
      </div>
    </div>`).join("");
  $$(".strip").forEach((strip) => {
    const track = mix.plan.tracks[Number(strip.dataset.track)];
    track.auto_mute = track.auto_mute ?? track.mute;
    track.fx ||= { reverb: { enabled: false, amount: 35 }, delay: { enabled: false, amount: 35 } };
    strip.querySelector(".fx-toggle").addEventListener("click", (e) => {
      const panel = strip.querySelector(".track-fx");
      panel.hidden = !panel.hidden;
      e.target.setAttribute("aria-expanded", String(!panel.hidden));
    });
    strip.querySelectorAll(".track-fx input").forEach((input) => input.addEventListener("input", async () => {
      const effect = input.dataset.effect;
      const setting = track.fx[effect];
      if (input.type === "checkbox") setting.enabled = input.checked;
      else setting.amount = Number(input.value);
      strip.querySelector(`output[data-effect="${effect}"]`).textContent = `${setting.amount}%`;
      strip.querySelector(".fx-toggle").classList.toggle("active", Object.values(track.fx).some((s) => s.enabled));
      try {
        if (setting.enabled) await loadFxBuffer(track, effect);
        await syncTrackFx(track);
      } catch (error) {
        setting.enabled = false;
        strip.querySelector(`input[type=checkbox][data-effect="${effect}"]`).checked = false;
        toast(error.message || "Could not prepare the effect", true);
      }
    }));
    strip.querySelector("input").addEventListener("input", (e) => {
      track.fader_db = Number(e.target.value);
      strip.querySelector(".db").textContent = `${track.fader_db >= 0 ? "+" : ""}${track.fader_db.toFixed(1)} dB`;
      applyGain(track);
    });
    if (track.active === false) return;
    strip.querySelector(".mute").addEventListener("click", (e) => {
      track.mute = !track.mute;
      e.target.classList.toggle("on", track.mute);
      e.target.textContent = track.mute ? "OFF" : "ON";
      strip.classList.toggle("off", track.mute);
      applyGain(track);
    });
  });
}

function applyGain(track) {
  const node = mix.nodes[track.file];
  if (node && mix.ctx) node.gain.gain.setTargetAtTime(trackGain(track), mix.ctx.currentTime, 0.03);
}

async function loadFxBuffer(track, effect) {
  const cache = mix.fxBuffers;
  const key = `${track.file}:${effect}`;
  if (!cache[key]) cache[key] = (async () => {
    const response = await fetch(`/montara/mix/${mix.job}/fx/${effect}/${encodeURIComponent(track.file)}`);
    if (!response.ok) throw new Error("Could not prepare the effect");
    return mix.ctx.decodeAudioData(await response.arrayBuffer());
  })();
  try { return await cache[key]; } catch (error) { delete cache[key]; throw error; }
}

async function syncTrackFx(track) {
  const node = mix.nodes[track.file];
  if (!node || !mix.playing) return;
  for (const effect of ["reverb", "delay"]) {
    const setting = track.fx?.[effect];
    if (!setting?.enabled) {
      if (node.fx[effect]) node.fx[effect].gain.gain.setTargetAtTime(0, mix.ctx.currentTime, 0.03);
      continue;
    }
    const buffer = await loadFxBuffer(track, effect);
    if (mix.nodes[track.file] !== node || !mix.playing) return;
    if (!node.fx[effect]) {
      const source = mix.ctx.createBufferSource(); source.buffer = buffer;
      const gain = mix.ctx.createGain(); gain.gain.value = 0;
      source.connect(gain); gain.connect(node.gain);
      const offset = mix.ctx.currentTime - mix.startedAt;
      if (offset >= buffer.duration) continue;
      source.start(0, offset);
      node.fx[effect] = { source, gain };
    }
    node.fx[effect].gain.gain.setTargetAtTime(track.fx[effect].enabled ? track.fx[effect].amount / 100 : 0, mix.ctx.currentTime, 0.03);
  }
}

async function loadBuffers() {
  mix.ctx = mix.ctx || new (window.AudioContext || window.webkitAudioContext)();
  await Promise.all(mix.plan.tracks.map(async (t) => {
    if (mix.buffers[t.file]) return;
    const response = await fetch(`/montara/mix/${mix.job}/track/${encodeURIComponent(t.file)}`);
    mix.buffers[t.file] = await mix.ctx.decodeAudioData(await response.arrayBuffer());
  }));
  $("#mixSeek").max = String(mix.plan.duration || 60);
}

function startMix(offset) {
  const ctx = mix.ctx;
  mix.master = ctx.createDynamicsCompressor();  // keeps the preview from clipping
  mix.master.connect(ctx.destination);
  for (const t of mix.plan.tracks) {
    const source = ctx.createBufferSource();
    source.buffer = mix.buffers[t.file];
    const gain = ctx.createGain();
    gain.gain.value = trackGain(t);
    const pan = ctx.createStereoPanner ? ctx.createStereoPanner() : null;
    if (pan) pan.pan.value = Math.max(-1, Math.min(1, Number(t.pan || 0)));
    source.connect(gain);
    (pan ? gain.connect(pan) && pan : gain).connect(mix.master);
    source.start(0, offset);
    mix.nodes[t.file] = { source, gain, fx: {} };
  }
  mix.startedAt = ctx.currentTime - offset;
  mix.playing = true;
  for (const t of mix.plan.tracks) syncTrackFx(t).catch((error) => toast(error.message, true));
  $("#playMix").textContent = "Pause";
  clearInterval(mix.timer);
  mix.timer = setInterval(() => {
    const now = mix.ctx.currentTime - mix.startedAt;
    if (now >= (mix.plan.duration || 0)) { stopMix(); mix.offset = 0; return; }
    $("#mixSeek").value = String(now);
    $("#mixTime").textContent = `${Math.floor(now / 60)}:${String(Math.floor(now % 60)).padStart(2, "0")}`;
  }, 200);
}

function stopMix() {
  if (mix.playing && mix.ctx) mix.offset = mix.ctx.currentTime - mix.startedAt;
  for (const node of Object.values(mix.nodes)) {
    for (const part of [node, ...Object.values(node.fx || {})]) {
      try { part.source.stop(); } catch { /* already stopped */ }
      part.source.disconnect();
    }
    node.gain.disconnect();
    for (const part of Object.values(node.fx || {})) part.gain.disconnect();
  }
  mix.master?.disconnect();
  mix.nodes = {};
  mix.playing = false;
  clearInterval(mix.timer);
  $("#playMix").textContent = "Play";
}

$("#playMix").addEventListener("click", async () => {
  if (!mix.ctx) return;
  await mix.ctx.resume();
  if (mix.playing) stopMix(); else startMix(mix.offset || 0);
});
$("#mixSeek").addEventListener("input", (e) => {
  const wasPlaying = mix.playing;
  stopMix();
  mix.offset = Number(e.target.value);
  if (wasPlaying) startMix(mix.offset);
});
$("#resetMix").addEventListener("click", async () => {
  stopMix();
  for (const t of mix.plan.tracks) {
    t.fader_db = t.auto_fader_db; t.mute = t.auto_mute;
    t.fx = { reverb: { enabled: false, amount: 35 }, delay: { enabled: false, amount: 35 } };
    applyGain(t); syncTrackFx(t).catch((error) => toast(error.message, true));
  }
  renderStrips();
  await animateMixFaders();
});
$("#pickReference").addEventListener("click", () => $("#referenceInput").click());
$("#referenceInput").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`/montara/mix/${mix.job}/reference`, { method: "POST", body: form });
  if (!response.ok) return toast("Could not use that reference", true);
  $("#referenceName").textContent = `Matched to: ${file.name}`;
});
$("#referenceLinkForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const jobId = mix.job, button = $("#useReferenceLink"), status = $("#referenceStatus");
  button.disabled = true; $("#useMix").disabled = true;
  $("#pickReference").disabled = true;
  status.hidden = false; status.textContent = "Preparing reference audio…";
  try {
    let result = await api(`/montara/mix/${jobId}/reference/link`, { url: $("#referenceUrl").value.trim() });
    while (result.status === "importing") {
      await new Promise((resolve) => setTimeout(resolve, 900));
      result = await api(`/montara/mix/${jobId}/reference/link`);
      if (mix.job !== jobId) return;
    }
    if (result.status !== "ready") throw new Error(result.message || "Could not use this reference.");
    $("#referenceName").textContent = `Matched to: ${result.title}`;
    status.textContent = "Reference ready.";
  } catch (error) { status.textContent = error.message; }
  finally { if (mix.job === jobId) { button.disabled = false; $("#pickReference").disabled = false; $("#useMix").disabled = false; } }
});
$("#mixBack").addEventListener("click", () => { stopMix(); show(fullSession.active ? 'sessionReview' : videos().length > 1 || videos().some(isSphere) ? "cameras" : "footage"); });

$("#useMix").addEventListener("click", async () => {
  try {
    if (fullSession.active) return await renderFullSession();
    stopMix();
    $("#useMix").disabled = true;
    $("#mixStatus").classList.remove("done");
    $("#mixStatusText").textContent = "Rendering the final mix and mastering it…";
    const faders = Object.fromEntries(mix.plan.tracks.map((t) => [t.file, MixLevels.offset(t)]));
    const mutes = Object.fromEntries(mix.plan.tracks.map((t) => [t.file, Boolean(t.mute)]));
    const effects = Object.fromEntries(mix.plan.tracks.map((t) => [t.file, Object.fromEntries(["reverb", "delay"].map((key) => [key, t.fx?.[key]?.enabled ? t.fx[key].amount / 100 : 0]))]));
    const animation = animateMixFaders(true);
    await api(`/montara/mix/${mix.job}/render`, { faders, mutes, effects });
    const job = await pollMix((j) => j.status === "done");
    await animation;
    if (job.status === "failed") throw new Error(job.error || "The final mix failed");
    state.mixMaster = job.master_path;
    if (audioOnly()) return showResult({ result: { audio: true, url: `/montara/mix/${mix.job}/result` } });
    // Register the mix as the project's master audio, then make the video.
    const data = inputs();
    await api("/wizard/draft", { name: $("#videoName").value.trim() || todayName(), project_id: state.projectId, platform: state.platform, audio_paths: [data.master], ...data });
    await make();
  } catch (error) {
    $("#useMix").disabled = false;
    fail(error);
  }
});

async function saveCameras() {
  await api("/settings/camera-types",{project_id:state.projectId,camera_types:Object.fromEntries(videos().map(f=>[f.path,cameraTypeOf(f)]))});
  const flat = videos().filter((f) => !isSphere(f));
  const subjects = Object.fromEntries(flat.map((f) => [f.path, state.subjects[f.path] || "general"]));
  if (flat.length) await api("/settings/camera-subjects", { camera_subjects: subjects });
  const roles = Object.fromEntries(flat.map((f) => [f.path, state.roles[f.path] || guessRole(f)]));
  if (flat.length) await api("/settings/camera-roles", { camera_roles: roles });
  for (const file of videos().filter(isSphere)) {
    const views = state.viewpoints[file.path] || {};
    if (!Object.keys(views).length) continue;
    // The engine identifies people by subject; the free name stays in Montara (frames, pins).
    const landmarks = Object.fromEntries(Object.entries(views).map(([slot, view]) => {
      const { who, ...rest } = view;
      return [slot, { ...rest, subject: whoOf(slot, view) }];
    }));
    for (const slot of [...VIEW_SLOTS.map(([key]) => key), "audience_stage_wide", "planet"]) {
      if (!landmarks[slot]) landmarks[slot] = { yaw: 0, pitch: 0, enabled: false, weight: 0 };
    }
    await api("/settings/spherical-landmarks", { spherical_landmarks: landmarks, spherical_source_path: file.path });
  }
}

// ---------- making ----------
async function make() {
  const name = $("#videoName").value.trim() || todayName();
  const platform = state.platform;
  const data = inputs();
  setProgress(0, "Getting your footage ready…", "");
  show("making");
  if (platform === "youtube") {
    await api("/wizard/prepare", { name, platform, project_id: state.projectId, ...data });
    await waitFor((s) => ["waiting_choice", "done"].includes(s.status));
  }
  await api("/wizard/start", {
    project_id: state.projectId, name, platform, ...data,
    reel_duration_sec: platform === "reel" ? Number($("#reelDuration").value) : undefined,
    trim_start_sec: platform === "youtube" && range.start > 0 ? range.start : undefined,
    trim_end_sec: platform === "youtube" && range.end !== null ? range.end : undefined,
    reel_aspect: platform === "reel" ? engineReelFormat() : undefined,
    reel_mix_vertical_ratio: platform === "reel" ? (reelFormat() === "mix" ? $("#mixShare").value : "auto") : undefined,
  });
  state.captioned = false;
  startPolling();
}

async function status() {
  const query = state.projectId ? `?project_id=${encodeURIComponent(state.projectId)}` : "";
  return api(`/wizard/status${query}`);
}

// Long footage (a whole jam, 4K phone video) can prepare for hours. Wait while the
// engine reports progress; give up only if nothing changes for 45 minutes.
const STALL_LIMIT_MS = 45 * 60 * 1000;
async function waitFor(predicate) {
  let signature = "", changedAt = Date.now();
  for (;;) {
    let s;
    try { s = await status(); }
    catch (error) {  // a dropped connection must not end a job the server is still doing
      if (Date.now() - changedAt > STALL_LIMIT_MS) throw error;
      await new Promise((r) => setTimeout(r, 5000));
      continue;
    }
    renderStatus(s);
    if (s.status === "failed") throw new Error(s.error || s.message || "Preparation failed");
    if (predicate(s)) return s;
    const now = JSON.stringify([s.status, s.stage, s.progress, s.message, s.detail, (s.tasks || []).map((t) => [t.label, t.progress])]);
    if (now !== signature) { signature = now; changedAt = Date.now(); }
    if (Date.now() - changedAt > STALL_LIMIT_MS) throw new Error("The preparation stopped making progress.");
    await new Promise((r) => setTimeout(r, 2000));
  }
}

function startPolling() {
  stopPolling();
  const generation = state.pollGeneration;
  const poll = async () => {
    try {
      const s = await status();
      if (generation !== state.pollGeneration) return;
      renderStatus(s);
      if (s.status === "waiting_show_review" && state.platform === "show") {
        stopPolling(); await openShowReview();
      } else if (s.status === "waiting_review") {
        stopPolling(); openFrames();
      } else if (s.status === "done") {
        stopPolling();
        if (state.platform === "reel" && !state.captioned) openCaptions(); else showResult(s);
      } else if (s.status === "failed" || s.status === "cancelled") {
        stopPolling(); fail(new Error(s.error || s.message || "The edit stopped"));
      }
    } catch (error) {
      if (generation === state.pollGeneration) { console.warn(error); if (state.platform === "show") fail(error); }
    }
    if (generation === state.pollGeneration) state.polling = setTimeout(poll, 1000);
  };
  state.polling = setTimeout(poll, 0);
}

function stopPolling() {
  state.pollGeneration = (state.pollGeneration || 0) + 1;
  clearTimeout(showEdit.previewTimer); clearTimeout(state.polling); state.polling = null;
  clearInterval(state.framesPoll); state.framesPoll = null;
}

function renderStatus(s) {
  if(state.platform==='show' && (!$('#showSetup').hidden || !$('#showStyle').hidden))return;
  if (state.platform === "show") {
    const p = Number(s.progress || 0);
    const exporting = s.stage === "export";
    setProgress(exporting && s.status !== "done" ? Math.min(99, p) : p, exporting ? "Finishing your video…" : p < 40 ? "Listening and finding the cuts…" : "Shaping your edit…", exporting && p >= 99 ? "Joining, checking playback and saving the final file. This can take a little longer." : exporting ? "Keeping the choices from your preview." : "Preparing the framing and the rhythm you chose.");
    return;
  }
  renderShotBars(s);
  const rendering = (s.tasks || []).some((t) => /^segment-/.test(t.id || ""));
  const task = rendering ? { label: "Rendering your video" } : (s.tasks || [])[0] || {};
  const finalizing = s.status !== "done" && Number(s.progress || 0) >= 99;
  setProgress(finalizing ? 99 : Number(s.progress || 0), finalizing ? "Finishing your video…" : task.label || s.message || "Working…", finalizing ? "Joining, checking playback and saving the final file. This can take a little longer." : s.detail || "");
}

// One small bar per shot while the engine renders (tasks "segment-N", label "Shot N/T").
function renderShotBars(s) {
  const box = $("#renderBars");
  const shots = (s.tasks || []).filter((t) => /^segment-\d+$/.test(t.id || ""));
  const total = Math.max(0, ...shots.map((t) => Number((/\/(\d+)/.exec(t.label || "") || [])[1] || 0)));
  if (!total || s.status === "done") { box.hidden = true; box.innerHTML = ""; return; }
  if (box.children.length !== total) box.innerHTML = Array.from({ length: total }, () => "<i></i>").join("");
  box.classList.toggle("many", total > 60);
  for (const t of shots) {
    const index = Number(t.id.split("-")[1]) - 1;
    const bar = box.children[index];
    if (bar) bar.style.setProperty("--p", Math.max(0, Math.min(1, Number(t.percent || 0) / 100)).toFixed(3));
  }
  box.hidden = false;
}

function setProgress(percent, message, detail) {
  const p = Math.max(0, Math.min(100, Math.round(percent)));
  $("#pct").textContent = `${p}%`;
  $("#ringBar").style.strokeDashoffset = String(326.7 * (1 - p / 100));
  $("#stageMsg").textContent = message;
  $("#stageDetail").textContent = detail;
}

$("#cancel").addEventListener("click", async () => {
  try { await api("/wizard/cancel", {}); } catch (error) { toast(error.message, true); }
  stopPolling();
  show(state.platform === "show" ? "showSetup" : "footage");
});

// ---------- frames ----------
// Name a 360 shot by where it really looks: the person's view closest to the shot's
// direction. The engine's slot type alone can be a variant aimed elsewhere.
const angleGap = (a, b) => Math.abs((((a - b) % 360) + 540) % 360 - 180);
function viewpointName(item) {
  const pose = item.pose || {};
  if (!item.landmark && !pose.type) return "";
  if (pose.type === "planet") return "little planet";  // the engine's own round view of the whole stage
  if (Number.isFinite(pose.yaw)) {
    let best = null;
    for (const views of Object.values(state.viewpoints)) {
      for (const view of Object.values(views)) {
        if (!view?.enabled) continue;
        const gap = angleGap(pose.yaw, view.yaw) + 0.5 * Math.abs((pose.pitch ?? view.pitch) - view.pitch);
        if (!best || gap < best.gap) best = { gap, name: view.subject };
      }
    }
    if (best && best.gap <= 20) return best.name;
    return item.landmark || "other angle";
  }
  const type = String(pose.type || "");
  for (const views of Object.values(state.viewpoints)) if (views[type]?.enabled && views[type].subject) return views[type].subject;
  return item.landmark || "360 view";
}
const swapping = new Set();
let frameHover = null;
// Shot previews stay loaded once played, and are made in the background one by one
// after the shots appear, so hovering shows the movement at once.
function stopFrameHover() {
  if (!frameHover) return;
  clearTimeout(frameHover.timer);
  const { video, thumb } = frameHover;
  video.pause(); video.hidden = true;
  if (video.readyState >= 2) { try { video.currentTime = 0; } catch { /* not seekable yet */ } }
  thumb.querySelector(".hover-status").hidden = true;
  frameHover = null;
}
function resetFrameVideo(thumb) {
  const video = thumb.querySelector("video");
  video.pause(); video.removeAttribute("src"); video.load(); video.hidden = true;
  delete thumb.dataset.warm;
}
let previewWarmer = 0;
async function warmFramePreviews() {
  const run = ++previewWarmer;
  for (const thumb of $$("#frameGrid .thumb")) {
    if (run !== previewWarmer || $("#frames").hidden) return;
    if (thumb.dataset.warm || thumb.closest(".frame").classList.contains("busy") || !thumb.dataset.preview) continue;
    try {
      const response = await fetch(thumb.dataset.preview, { headers: { Range: "bytes=0-1" } });
      if (response.ok) thumb.dataset.warm = "1";
      else if (response.status === 409) return;  // the engine is busy again; try on the next refresh
    } catch { return; }
  }
}
function startFrameHover(thumb) {
  if (frameHover?.thumb === thumb) return;
  stopFrameHover();
  if (thumb.closest(".frame").classList.contains("busy")) return;
  const video = thumb.querySelector("video"), label = thumb.querySelector(".hover-status");
  const entry = { thumb, video, timer: null }; frameHover = entry;
  if (video.getAttribute("src") === thumb.dataset.preview && video.readyState >= 2) {
    video.hidden = false; label.hidden = true;
    video.play().catch(() => {});
    return;
  }
  entry.timer = setTimeout(() => {
    if (frameHover !== entry || $("#frames").hidden) return;
    label.textContent = "Preparing preview…"; label.hidden = false;
    video.oncanplay = () => {
      if (frameHover !== entry) return;
      video.hidden = false; label.hidden = true;
      video.play().catch(() => { label.textContent = "Tap the picture to play"; label.hidden = false; });
    };
    video.onerror = () => { if (frameHover === entry) { label.textContent = "Preview unavailable"; label.hidden = false; } };
    video.preload = "auto";
    video.src = thumb.dataset.preview;
    video.load();
  }, thumb.dataset.warm ? 0 : 120);
}
async function openFrames() {
  show("frames");
  $("#frameGrid").innerHTML = "";
  $("#framesHint").textContent = "Preparing the shots…";
  await refreshFrames(true);
  await loadMusicCuts();
  clearInterval(state.framesPoll);
  state.framesPoll = setInterval(() => refreshFrames(false).catch(console.warn), 1500);
}

async function refreshFrames(first) {
  const data = await api(`/wizard/review?render=${first ? 1 : 0}`);
  const items = data.items || [];
  const pending = items.filter((item) => !item.thumbnail).length;
  $("#framesHint").textContent = pending ? `Preparing shots… ${items.length - pending} of ${items.length}` : `${items.length} shots`;
  const grid = $("#frameGrid");
  if (grid.children.length !== items.length) {
    grid.innerHTML = items.map((item) => `
      <figure class="frame" data-index="${item.index}">
        <div class="thumb" tabindex="0" aria-label="Preview shot ${item.index + 1}"><img alt="" hidden><video muted playsinline loop preload="none" hidden></video><span class="spin"></span><span class="hover-status" role="status" hidden></span></div><div class="frame-actions"><button class="btn ghost small swap">Swap</button><button class="btn ghost small shot-edit">Edit</button></div>
        <figcaption><b>${String(item.index + 1).padStart(2, "0")}</b> <span class="src"></span> <span class="dur"></span></figcaption>
      </figure>`).join("");
    grid.querySelectorAll(".shot-edit").forEach(button=>button.onclick=()=>{stopFrameHover();openMusicShot(Number(button.closest(".frame").dataset.index));});
    grid.querySelectorAll(".swap").forEach((button) => button.addEventListener("click", () => swap(Number(button.closest(".frame").dataset.index))));
    grid.querySelectorAll(".thumb").forEach((thumb) => {
      thumb.onpointerenter = (event) => { if (event.pointerType !== "touch") startFrameHover(thumb); };
      thumb.onpointerleave = () => { if (frameHover?.thumb === thumb) stopFrameHover(); };
      thumb.onfocus = () => startFrameHover(thumb);
      thumb.onblur = () => { if (!thumb.matches(":hover") && frameHover?.thumb === thumb) stopFrameHover(); };
      thumb.onclick = (event) => {
        if (event.target.closest("button")) return;
        if (frameHover?.thumb === thumb && frameHover.video.readyState >= 2) frameHover.video.play().catch(() => {});
        else startFrameHover(thumb);
      };
      thumb.onkeydown = (event) => { if (event.target === thumb && ["Enter", " "].includes(event.key)) { event.preventDefault(); startFrameHover(thumb); } };
    });
  }
  for (const item of items) {
    const fig = grid.querySelector(`[data-index="${item.index}"]`);
    const img = fig.querySelector("img");
    const thumb = fig.querySelector(".thumb");
    // The thumbnail changes when a shot is swapped: use it to version the preview URL.
    const preview = item.preview || `/api/v1/wizard/review/preview/${item.index}?v=${encodeURIComponent(item.thumbnail || "")}`;
    if (thumb.dataset.preview && thumb.dataset.preview !== preview) { if (frameHover?.thumb === thumb) stopFrameHover(); resetFrameVideo(thumb); }
    thumb.dataset.preview = preview;
    const landmark = viewpointName(item);
    const type=item.camera_type || (item.pose && Object.keys(item.pose).length?"360":"moving");
    const label = `${{fixed:"Fixed",moving:"Moving","360":"360"}[type]}${type==="360" && landmark?" · "+landmark:""}`;
    if (item.thumbnail && img.getAttribute("src") !== item.thumbnail) {
      img.src = item.thumbnail;
      img.hidden = false;
      swapping.delete(item.index);
      fig.querySelector(".src").textContent = label;
    } else if (!fig.querySelector(".src").textContent) {
      fig.querySelector(".src").textContent = label;
    }
    fig.querySelector(".src").textContent=label;
    if(!item.thumbnail)img.hidden=true;
    fig.classList.toggle("busy", !item.thumbnail || swapping.has(item.index));
    fig.querySelector(".dur").textContent = `${Number(item.duration_sec).toFixed(1)} s`;
    fig.querySelector(".swap").disabled = item.candidate_count !== undefined && item.candidate_count < 2;
  }
  if (!pending) { clearInterval(state.framesPoll); state.framesPoll = null; warmFramePreviews(); }
}

async function swap(index) {
  stopFrameHover();
  swapping.add(index);
  $(`.frame[data-index="${index}"]`)?.classList.add("busy");
  try {
    const result = await api("/wizard/review/replace", { rejected: [index] });
    if (!(result.replaced || []).length) { swapping.delete(index); toast("No other moment available for this shot."); }
  } catch (error) {
    swapping.delete(index);
    toast(error.message, true);
  }
  clearInterval(state.framesPoll);
  state.framesPoll = setInterval(() => refreshFrames(false).catch(console.warn), 1500);
  await refreshFrames(false);
  await loadMusicCuts();
}

$("#renderFrames").addEventListener("click", async () => {
  try {
    clearInterval(state.framesPoll);
    await api("/wizard/review/render", {});
    setProgress(0, "Rendering your video…", "");
    show("making");
    startPolling();
  } catch (error) { fail(error); }
});

// ---------- captions (Pulse) ----------
// Same engine as Zucker's "Overlay & Captions": cues + style go to /wizard/compose,
// which burns them onto a clean copy of the rendered reel. Every caption carries its
// own place, size, colour, font and effect (engine style_override).
const CAP_STYLES = [
  ["clean_bottom", "Clean", "", 52], ["karaoke_word", "Karaoke", "karaoke", 54], ["bold_pop", "Bold", "big", 64],
  ["hard_shadow", "Shadow", "shadow", 58], ["neon_glow", "Glow", "neon", 64], ["lyric_serif", "Serif", "serif", 52],
];
const CAP_COLORS = ["#FFFFFF", "#0B0B0D", "#FF4F2E", "#FFE14D", "#3EE6C1", "#4DA3FF", "#FF5CC8"];
const CAP_FONTS = [["", "Look's font"], ["Arial", "Sans"], ["Georgia", "Serif"], ["Impact", "Impact"], ["Courier New", "Mono"]];
const CAP_EFFECTS = [
  ["word", "Word by word", { animation_in: "none", animation_out: "none", fun_effect: "none" }],
  ["none", "None", { animation_in: "none", animation_out: "none", fun_effect: "none" }],
  ["fade", "Fade", { animation_in: "fade", animation_out: "fade", fun_effect: "none" }],
  ["pop", "Pop", { fun_effect: "pop" }], ["bounce", "Bounce", { fun_effect: "bounce" }],
  ["pulse", "Pulse", { fun_effect: "pulse" }], ["shake", "Shake", { fun_effect: "shake" }],
  ["fly", "Fly in", { fun_effect: "fly_left" }], ["drop", "Drop", { fun_effect: "drop" }],
];
const cap = { list: [], style: "clean_bottom", timed: false, raf: 0, selected: -1 };
const capVideo = () => $("#capVideo");
const capDuration = () => Number(capVideo().duration) || Number($("#reelDuration").value) || 30;
const capBaseSize = () => CAP_STYLES.find(([id]) => id === cap.style)[3];
const outSize = () => [1080, 1920];
const fmtTime = (x) => `${Math.floor(x / 60)}:${String(Math.floor(x % 60)).padStart(2, "0")}`;
const newCaption = (text, start, end) => ({ text, start, end, x: 50, y: 80, size: null, color: null, font: "", effect: "fade" });

function openCaptions() {
  show("captions");
  $("#capFrame").classList.remove("wide");
  capVideo().src = `/api/v1/wizard/compose-base?t=${Date.now()}`;
  $("#capStyles").innerHTML = CAP_STYLES.map(([id, label]) => `<button type="button" class="chip${id === cap.style ? " on" : ""}" data-style="${id}">${label}</button>`).join("");
  $("#capColors").innerHTML = CAP_COLORS.map((c) => `<button type="button" class="swatch" data-color="${c}" style="background:${c}" aria-label="${c}"></button>`).join("")
    + `<label class="swatch custom" title="Any colour"><input type="color" id="capCustomColor" value="#ffffff"></label>`;
  $("#capFonts").innerHTML = CAP_FONTS.map(([f, label]) => `<button type="button" class="chip" data-font="${f}" style="${f ? `font-family:'${f}'` : ""}">${label}</button>`).join("");
  $("#capEffects").innerHTML = CAP_EFFECTS.map(([id, label]) => `<button type="button" class="chip" data-effect="${id}">${label}</button>`).join("");
  renderCaps();
}

function splitCaptionPhrases(text) {
  return (String(text).match(/[^.!?¿¡,;\n]+[.!?,;]*/g) || []).map(line => line.trim()).filter(Boolean);
}
function textLines() { return splitCaptionPhrases($("#capText").value); }
function syncText() { $("#capText").value = cap.list.map((c) => c.text).join("\n"); }

function spreadCaptions(texts) {
  const duration = capDuration();
  const start = Math.min(1, duration * 0.05);
  const slot = (duration - start - 0.5) / Math.max(1, texts.length);
  const old = cap.list;
  cap.list = texts.map((text, i) => ({ ...(old[i] || newCaption()), text, words: undefined, start: start + i * slot, end: start + (i + 1) * slot - 0.15 }));
}

$("#capText").addEventListener("input", () => {
  const lines = textLines();
  if (!cap.timed || lines.length !== cap.list.length) { cap.timed = false; spreadCaptions(lines); }
  else lines.forEach((text, i) => { if (cap.list[i].text !== text) { cap.list[i].text = text; cap.list[i].words = undefined; } });
  if (cap.selected >= cap.list.length) cap.selected = -1;
  renderCaps();
});
$("#capSpread").addEventListener("click", () => { cap.timed = false; spreadCaptions(textLines()); renderCaps(); });
$("#capTitle").addEventListener("input", renderCaps);

// ---- what is on screen: captions over the video, bars on the timeline, the inspector ----
// Speech timestamps take priority; typed/spread lines use evenly spaced words.
function captionWords(c) {
  const words = (c.words || []).map(w => ({ text: String(w.text || w.word || "").trim(), start: Math.max(c.start, Number(w.start ?? w.start_sec)), end: Math.min(c.end, Number(w.end ?? w.end_sec)) }))
    .filter(w => w.text && Number.isFinite(w.start) && Number.isFinite(w.end) && w.end > w.start);
  if (words.length) return words;
  const text = c.text.trim().split(/\s+/).filter(Boolean);
  return text.map((word, i) => ({ text: word, start: c.start + (c.end - c.start) * i / text.length, end: c.start + (c.end - c.start) * (i + 1) / text.length }));
}
function captionCues(c) {
  const style_override = captionOverride(c);
  if (c.effect === "word") return captionWords(c).map(w => ({ lines: [w.text], start: w.start, end: w.end, words: [], style_override }));
  return [{ lines: splitCaption(c.text.trim()), start: c.start, end: c.end, words: c.words || [], style_override }];
}

function capScale() { return $("#capFrame").clientHeight / outSize()[1]; }
function renderCaps() {
  const t = capVideo().currentTime || 0;
  const layer = $("#capLayer");
  const previous = new Map([...layer.querySelectorAll(".capline")].map(el => [Number(el.dataset.i), el]));
  const look = CAP_STYLES.find(([id]) => id === cap.style)[2];
  cap.list.forEach((c, i) => {
    const visible = (t >= c.start && t < c.end) || (capVideo().paused && i === cap.selected);
    if (!visible) return;
    const el = previous.get(i) || document.createElement("div");
    previous.delete(i);
    el.className = `capline ${look} fx-${c.effect || "none"}${i === cap.selected ? " sel" : ""}${t >= c.start && t < c.end ? "" : " ghost"}`;
    el.dataset.i = i;
    el.style.left = `${c.x}%`;
    el.style.top = `${c.y}%`;
    el.style.fontSize = `${(c.size || capBaseSize()) * capScale()}px`;
    if (c.color) el.style.color = c.color;
    if (c.font) el.style.fontFamily = `'${c.font}'`;
    el.style.animationDelay = `-${Math.max(0, t - c.start)}s`;
    el.style.animationPlayState = "paused";
    el.style.color = c.color || (cap.style === "neon_glow" ? "#FFE14D" : "");
    el.style.fontFamily = c.font ? `'${c.font}'` : "";
    el.textContent = c.effect === "word" ? (captionWords(c).find(w => t >= w.start && t < w.end)?.text || (capVideo().paused ? c.text : "")) : c.text;
    const grip = document.createElement("i");
    grip.className = "grip";
    el.append(grip);
    layer.append(el);
  });
  previous.forEach(el => el.remove());
  const title = $("#capTitle").value.trim();
  $("#capTitlePreview").hidden = !title;
  $("#capTitlePreview").textContent = title;
  // timeline
  const d = capDuration();
  $("#capBars").innerHTML = cap.list.map((c, i) => `<div class="capbar${i === cap.selected ? " sel" : ""}" data-i="${i}" style="left:${c.start / d * 100}%;width:${Math.max(0.5, (c.end - c.start) / d * 100)}%"><i class="edge l"></i><span>${escapeHtml(c.text)}</span><i class="edge r"></i></div>`).join("");
  $("#capHead").style.left = `${Math.min(100, t / d * 100)}%`;
  $("#capTime").textContent = `${fmtTime(t)} / ${fmtTime(d)}`;
  renderInspector();
}

function renderInspector() {
  const c = cap.list[cap.selected];
  $("#capInspect").hidden = !c;
  $("#capNoneSelected").hidden = Boolean(c) || !cap.list.length;
  if (!c) return;
  $("#capWhich").textContent = `Caption ${cap.selected + 1} · ${fmtTime(c.start)}–${fmtTime(c.end)}`;
  if (document.activeElement !== $("#capEditText")) $("#capEditText").value = c.text;
  $$("#capColors .swatch[data-color]").forEach((b) => b.classList.toggle("on", (c.color || (cap.style === "neon_glow" ? "#FFE14D" : "#FFFFFF")).toUpperCase() === b.dataset.color));
  $$("#capFonts .chip").forEach((b) => b.classList.toggle("on", (c.font || "") === b.dataset.font));
  $$("#capEffects .chip").forEach((b) => b.classList.toggle("on", (c.effect || "none") === b.dataset.effect));
  $("#capSize").value = c.size || capBaseSize();
}


// ---- dragging: captions on the video (move / resize), bars on the timeline (move / trim) ----
let capDrag = null;
$("#capLayer").addEventListener("pointerdown", (e) => {
  const el = e.target.closest(".capline");
  if (!el) return;
  e.preventDefault();
  const i = Number(el.dataset.i);
  const c = cap.list[i];
  cap.selected = i;
  capDrag = { kind: e.target.classList.contains("grip") ? "size" : "move", i, x0: e.clientX, y0: e.clientY, cx: c.x, cy: c.y, size: c.size || capBaseSize() };
  $("#capLayer").setPointerCapture(e.pointerId);
  renderInspector();
});
$("#capTimeline").addEventListener("pointerdown", (e) => {
  const bar = e.target.closest(".capbar");
  const rect = $("#capTimeline").getBoundingClientRect();
  if (!bar) {  // seek
    capVideo().currentTime = Math.max(0, (e.clientX - rect.left) / rect.width * capDuration());
    renderCaps();
    return;
  }
  e.preventDefault();
  const i = Number(bar.dataset.i);
  const c = cap.list[i];
  cap.selected = i;
  const kind = e.target.classList.contains("l") ? "start" : e.target.classList.contains("r") ? "end" : "slide";
  capDrag = { kind, i, x0: e.clientX, start: c.start, end: c.end, width: rect.width };
  $("#capTimeline").setPointerCapture(e.pointerId);
  renderCaps();
});
$("#capTimeline").addEventListener("dblclick", (e) => {
  if (e.target.closest(".capbar")) return;
  const rect = $("#capTimeline").getBoundingClientRect();
  const at = Math.max(0, (e.clientX - rect.left) / rect.width * capDuration());
  const base = cap.list[cap.selected] || newCaption();
  cap.list.push({ ...base, text: "New caption", words: undefined, start: at, end: Math.min(capDuration(), at + 2.5) });
  cap.list.sort((a, b) => a.start - b.start);
  cap.timed = true;
  cap.selected = cap.list.findIndex((c) => c.start === at);
  syncText();
  renderCaps();
  $("#capEditText").focus();
  $("#capEditText").select();
});
function dragMove(e) {
  if (!capDrag) return;
  const c = cap.list[capDrag.i];
  if (capDrag.kind === "move") {
    const frame = $("#capFrame").getBoundingClientRect();
    c.x = Math.round(Math.max(5, Math.min(95, capDrag.cx + (e.clientX - capDrag.x0) / frame.width * 100)) * 10) / 10;
    c.y = Math.round(Math.max(4, Math.min(96, capDrag.cy + (e.clientY - capDrag.y0) / frame.height * 100)) * 10) / 10;
  } else if (capDrag.kind === "size") {
    const grow = ((e.clientX - capDrag.x0) + (e.clientY - capDrag.y0)) / capScale() / 3;
    c.size = Math.round(Math.max(24, Math.min(140, capDrag.size + grow)));
  } else {
    const d = capDuration();
    const dt = (e.clientX - capDrag.x0) / capDrag.width * d;
    if (capDrag.kind === "slide") {
      const len = capDrag.end - capDrag.start;
      c.start = Math.max(0, Math.min(d - len, capDrag.start + dt));
      c.end = c.start + len;
    } else if (capDrag.kind === "start") c.start = Math.max(0, Math.min(c.end - 0.3, capDrag.start + dt));
    else c.end = Math.min(d, Math.max(c.start + 0.3, capDrag.end + dt));
    c.words = undefined;
    cap.timed = true;
  }
  renderCaps();
}
function dragEnd() { if (capDrag?.kind && ["slide", "start", "end"].includes(capDrag.kind)) { cap.list.sort((a, b) => a.start - b.start); } capDrag = null; }
["capLayer", "capTimeline"].forEach((id) => {
  $(`#${id}`).addEventListener("pointermove", dragMove);
  $(`#${id}`).addEventListener("pointerup", dragEnd);
});

// ---- inspector: this caption's own text, colour, font, size, effect ----
const current = () => cap.list[cap.selected];
$("#capEditText").addEventListener("input", (e) => { const c = current(); if (!c) return; c.text = e.target.value; c.words = undefined; syncText(); renderCaps(); });
$("#capColors").addEventListener("click", (e) => { const b = e.target.closest("[data-color]"); if (b && current()) { current().color = b.dataset.color; renderCaps(); } });
$("#capColors").addEventListener("input", (e) => { if (e.target.id === "capCustomColor" && current()) { current().color = e.target.value.toUpperCase(); renderCaps(); } });
$("#capFonts").addEventListener("click", (e) => { const b = e.target.closest("[data-font]"); if (b && current()) { current().font = b.dataset.font; renderCaps(); } });
$("#capEffects").addEventListener("click", (e) => { const b = e.target.closest("[data-effect]"); if (b && current()) { current().effect = b.dataset.effect; renderCaps(); replayEffect(); } });
$("#capSize").addEventListener("input", (e) => { if (current()) { current().size = Number(e.target.value); renderCaps(); } });
$("#capDelete").addEventListener("click", () => { if (!current()) return; cap.list.splice(cap.selected, 1); cap.selected = -1; syncText(); renderCaps(); });
$("#capApplyAll").addEventListener("click", () => {
  const c = current();
  if (!c) return;
  cap.list.forEach((other) => Object.assign(other, { x: c.x, y: c.y, size: c.size, color: c.color, font: c.font, effect: c.effect }));
  renderCaps();
  toast("Every caption now has this look.");
});
function replayEffect() { const el = $("#capLayer .capline.sel"); if (el) { el.style.animation = "none"; void el.offsetWidth; el.style.animation = ""; } }

$("#capStyles").addEventListener("click", (event) => {
  const chip = event.target.closest("[data-style]");
  if (!chip) return;
  cap.style = chip.dataset.style;
  $$("#capStyles .chip").forEach((c) => c.classList.toggle("on", c === chip));
  renderCaps();
});

// ---- player ----
function capLoop() { renderCaps(); cap.raf = capVideo().paused ? 0 : requestAnimationFrame(capLoop); }
$("#capPlay").addEventListener("click", () => { if (capVideo().paused) capVideo().play().catch(() => toast("This browser cannot play the preview.", true)); else capVideo().pause(); });
capVideo().addEventListener("play", () => { $("#capPlay").textContent = "Pause"; cancelAnimationFrame(cap.raf); capLoop(); });
capVideo().addEventListener("pause", () => { $("#capPlay").textContent = "Play"; renderCaps(); });
capVideo().addEventListener("seeked", renderCaps);
capVideo().addEventListener("loadedmetadata", () => { if (!cap.timed && cap.list.length) spreadCaptions(textLines()); renderCaps(); });
$("#capFrame").addEventListener("click", (e) => { if (!e.target.closest(".capline") && !capDrag) { cap.selected = -1; renderCaps(); } });
new ResizeObserver(() => { if (!$("#captions").hidden) renderCaps(); }).observe($("#capFrame"));

// Do not mistake Whisper's music-only markers for recognised lyrics.
function isLyricCue(cue) {
  const text = (cue.lines || []).join(" ").trim();
  const bare = text.replace(/[♪♫♬♩🎵🎶\s.,!?:;()[\]{}—_-]/gu, "");
  return /[\p{L}\p{N}]/u.test(bare) && !/^(music|instrumental|música|musica|musique|applause|silence)$/iu.test(bare);
}
function lyricReadProgress(value) {
  const percent = Math.max(0, Math.min(100, Math.round(Number(value) || 0)));
  return percent > 0 ? `Listening to your song… ${percent}%` : "Listening to your song…";
}
$("#capRead").addEventListener("click", async () => {
  const button = $("#capRead");
  button.disabled = true;
  const statusText = $("#capReadStatus");
  try {
    let cues = [];
    for (const model of ["small", "medium"]) {
      statusText.textContent = "Listening to your song…";
      await api("/captions/auto-read", { model });
      for (;;) {
        await new Promise(r => setTimeout(r, 1500));
        const job = await api("/captions/auto-read/status");
        if (job.status === "failed") throw new Error(job.error || "Could not read the lyrics");
        statusText.textContent = lyricReadProgress(job.progress);
        if (job.status === "done") {
          cues = (job.result?.cues || []).filter(isLyricCue);
          break;
        }

      }
      if (cues.length) break;
    }
    if (!cues.length) {
      statusText.textContent = "Whisper could not make out the sung words. Your captions are unchanged. Paste the lyrics and use Spread captions instead.";
      return;
    }
    const base = cap.list[0] || newCaption();
    cap.list = cues.map(c => ({ ...base, text: (c.lines || []).join(" "), start: c.start, end: c.end,
      words: (c.words || []).map(w => ({ ...w, start: w.start ?? w.start_sec, end: w.end ?? w.end_sec })) }));
    cap.timed = true;
    cap.selected = -1;
    syncText();
    renderCaps();
    statusText.textContent = `${cues.length} captions read. Check the words before adding them.`;
  } catch (error) {
    statusText.textContent = `Could not read the lyrics: ${error.message}. Your captions are unchanged.`;
  } finally { button.disabled = false; }
});

function splitCaption(text) {
  const words = text.split(/\s+/).filter(Boolean);
  if (text.length <= 32 || words.length < 2) return [text];
  let best = 1;
  for (let i = 1; i < words.length; i += 1) {
    const diff = (k) => Math.abs(words.slice(0, k).join(" ").length - words.slice(k).join(" ").length);
    if (diff(i) < diff(best)) best = i;
  }
  return [words.slice(0, best).join(" "), words.slice(best).join(" ")];
}

function captionOverride(c) {
  const effect = (CAP_EFFECTS.find(([id]) => id === (c.effect || "none")) || CAP_EFFECTS[0])[2];
  return {
    horizontal: c.x, vertical: c.y, ...effect,
    ...(cap.style === "neon_glow" ? { color: c.color || "#FFE14D", glow_color: "#FFE14D" } : (c.color ? { color: c.color } : {})),
    ...(c.size ? { size: c.size } : {}), ...(c.font ? { font: c.font } : {}),
  };
}

$("#capSkip").addEventListener("click", async () => { capVideo().pause(); state.captioned = true; showResult(await status()); });
$("#capApply").addEventListener("click", async () => {
  capVideo().pause();
  const title = $("#capTitle").value.trim();
  const cues = cap.list.filter((c) => c.text.trim() && c.end > c.start).flatMap(captionCues);
  state.captioned = true;
  if (!cues.length && !title) return showResult(await status());
  try {
    await api("/wizard/compose", {
      cues, style: cap.style, lang: "und", texts: [], images: [], videos: [], letterbox: { enabled: false },
      header: { title_enabled: Boolean(title), title, logo_source: "none" },
    });
    setProgress(0, "Adding your captions…", "");
    show("making");
    startPolling();
  } catch (error) { fail(error); }
});

// ---------- Show: one video, four rhythms, a short scene review ----------
const showEdit = { pace: "normal", scenes: [], proposals: [], selected: 0, previewTimer: null, previewToken: 0, blob: null };
async function openShowSetup() {
  stopPolling();
  state.platform = "show";
  show("showSetup");
  await loadShowExamples();
  if (!state.projectId) {
    const current = await api("/wizard/status");
    if (current.project_path) {
      const saved = await api("/project");
      const wizard = saved.settings?.wizard || {};
      let resumeStatus=current.status;
      if(wizard.platform==='show' && !['running','waiting_show_review','done','completed'].includes(resumeStatus)){
        try{const savedScenes=await api('/show/scenes');if(savedScenes.scenes?.length)resumeStatus='waiting_show_review';}catch{}
      }
      if (wizard.platform === "show" && ['running','waiting_show_review','done','completed'].includes(resumeStatus)) {
        state.projectId = current.project_path;
        state.files = (saved.inputs?.videos || []).map(f => ({ id: crypto.randomUUID(), name: f.path.split("/").pop(), kind: "video", path: f.path, showSource: true }));
        $("#videoName").value = saved.name || todayName();
        showEdit.pace = ({choe:"fast",calm:"normal"})[wizard.show?.style] || wizard.show?.style || "normal";
        await restoreShowModeSources(showEdit.pace);
        if (videos()[0]) $("#showInputVideo").src = `/api/v1/show/source?path=${encodeURIComponent(videos()[0].path)}`;
        showEdit.resume={projectId:current.project_path,style:showEdit.pace,source:videos()[0]?.path,status:resumeStatus};
      }
    }
  }
  if (!videos().length || !state.files.some(f => f.showSource)) {
    state.files = [];
    $("#showInputVideo").src = "/montara/show/sample";
    await loadSamples();
    state.files.forEach(f => { f.showSource = true; });
  }
  if(showExampleList.some(item=>item.id===showEdit.pace)){$("#showExampleChoice").value=showEdit.pace;renderShowExample();}
  $$("[data-show-pace]").forEach(b=>{const on=b.dataset.showPace===showEdit.pace;b.classList.toggle("on",on);b.setAttribute("aria-pressed",String(on));});
  renderShowInput();
}
function renderShowInput() {
  const file = videos()[0];
  const busy = state.uploads > 0;
  const error = state.files.find(f => f.kind === "error");
  $("#showInputStatus").textContent = busy ? `Uploading… ${Math.round((state.files[0]?.progress || 0) * 100)}%` : error ? error.error : file ? (file.sample ? `Example · ${file.name}${file.exampleDuration ? " · "+file.exampleDuration+"s" : ""}` : file.name) : "Choose your talking video.";
  $("#showMake").disabled = busy || !file;
  $("#showChooseType").disabled=busy || !file;
  if(typeof renderShowModeInputs==='function')renderShowModeInputs();
  if(typeof renderShowMaterialBoxes==='function')renderShowMaterialBoxes();
  $("#showChosenVideo").textContent=file?.name || "Choose a video first.";
}
async function chooseShowVideo(files) {
  if(rejectRaw360(files)||state.uploads||!files.length)return;
  try{
    const wasKit=state.files.some(f=>f.sample);
    if(wasKit){state.files=[];resetShowSources();state.sampleVariant='';}
    showEdit.resume=null;
    const items=await uploadShowSupport(files);
    for(const item of items){
      const audio=/\.(wav|mp3|m4a|flac|ogg|aac)$/i.test(item.name);
      const image=/\.(png|jpe?g|webp|gif)$/i.test(item.name);
      if(audio){if(showEdit.pace==='podcast')showSources.podcast.people.push({name:item.name.replace(/\.[^.]+$/,''),mic:item.path});else showSources.story.narration=item;}
      else {
        if(!image)state.files.push({...item,id:crypto.randomUUID(),kind:'video',showSource:true});
        if(showEdit.pace==='storytelling')showSources.story.clips.push(item);
      }
    }
    if(videos()[0])$('#showInputVideo').src=showInputURL(videos()[0].path);
    renderShowInput();
  }catch(error){toast(error.message,true);}
}

$("#showInputFile").addEventListener("change", event => {
  chooseShowVideo([...event.target.files]);
  event.target.value = "";
});
["dragenter", "dragover"].forEach(name => $("#showDrop").addEventListener(name, event => {
  event.preventDefault(); $("#showDrop").classList.add("over");
}));
["dragleave", "drop"].forEach(name => $("#showDrop").addEventListener(name, event => {
  event.preventDefault(); $("#showDrop").classList.remove("over");
  if (name === "drop") chooseShowVideo([...event.dataTransfer.files]);
}));
$$("[data-show-pace]").forEach(button => button.addEventListener("click", async () => {
  showEdit.pace = button.dataset.showPace;
  $$("[data-show-pace]").forEach(b => { b.classList.toggle("on", b === button); b.setAttribute("aria-pressed", String(b === button)); });
  $("#showExampleChoice").value=showEdit.pace;renderShowExample();
  $("#showPaceHint").textContent=showEdit.pace==='podcast'?"One microphone per person. Cameras follow the speakers; every shot stays editable.":showEdit.pace==='storytelling'?"Narration and matching pictures, with a saved, editable montage plan.":"The original voice stays with your video.";
  if(state.files.length&&state.files.every(f=>f.sample)&&state.sampleVariant!==showEdit.pace){state.files=[];state.projectId=null;await loadSamples(showEdit.pace);renderShowInput();}else renderShowModeInputs();
}));
$("#showMake").addEventListener("click", () => {
  if(['waiting_show_review','running','done','completed'].includes(showEdit.resume?.status) && state.projectId===showEdit.resume.projectId && videos()[0]?.path===showEdit.resume.source && showEdit.pace===showEdit.resume.style){if(showEdit.resume.status==='running'){show('making');startPolling();}else openShowReview().catch(fail);return;}
  $("#showMake").disabled = true;
  $("#showInputVideo").pause();
  $("#videoName").value = videos()[0]?.name.replace(/\.[^.]+$/, "") || todayName();
  state.branding = "montara";
  registerProject().catch(fail).finally(renderShowInput);
});
async function makeShow() {
  await prepareShowSources();
  setProgress(0, "Listening to your video…", "Finding the natural cuts and preparing your preview.");
  show("making");
  await api("/wizard/start", { project_id: state.projectId, name: $("#videoName").value, platform: "show", videos: videos().map(f => f.path), show_main: videos()[0].path,
    show_style: showEdit.pace, show_review: true, captions_english:false, show_captions:true, show_idea_mode: "automatic", show_gags: ["podcast","storytelling"].includes(showEdit.pace) ? "off" : "keywords", show_auto_research: !["podcast","storytelling"].includes(showEdit.pace) });
  startPolling();
}
async function showPatch(path, body) {
  const response = await fetch(`/api/v1${path}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message || "Could not save your change.");
  document.dispatchEvent(new Event('montara:edit-saved'));
  return data;
}
async function openShowReview() {
  showEdit.direction = await api("/montara/show/direction", {});
  const data = await api("/show/scenes");
  const fast=await api("/montara/show/editor");showEdit.timelineCache=fast.timeline;showEdit.narratorCache=fast.narrator;
  showEdit.scenes = data.scenes || [];
  showEdit.proposals = data.proposals || [];
  showEdit.source = data.source;
  showEdit.sourceUrl = data.source_url;
  $('[data-show-step="showReview"]').disabled=false;
  if(!videos().length && data.source_url){
    const path=new URL(data.source_url,location.origin).searchParams.get('path');
    if(path)state.files=[{id:crypto.randomUUID(),name:path.split('/').pop(),kind:'video',path,showSource:true}];
  }
  showEdit.resources = data.resources || [];
  await loadShowModeReview(data);
  if (!showEdit.scenes.length) throw new Error("No scenes were found in this video.");
  // Ready automatic effects are kept; no drawing or provider sign-in is triggered here.
  for (const scene of showEdit.scenes) if (scene.decision === "pending") {
    await api(`/show/scenes/${encodeURIComponent(scene.id)}/decision`, { decision: "modified" });
    scene.decision = "modified";
  }
  showEdit.selected = 0;
  show("showReview");
  requestAnimationFrame(()=>document.querySelector(".show-picture-console").scrollIntoView({block:"start"}));
  renderShowScene();
  drawShowCaptions();renderShowProgramTimeline();
}
function renderShowScene() {
  const resumeOffset=showEdit.seekAfterEdit || 0;delete showEdit.seekAfterEdit;
  clearTimeout(showEdit.previewTimer);
  const token = ++showEdit.previewToken;
  const scene = showEdit.scenes[showEdit.selected];
  $("#showSceneTabs").innerHTML = showEdit.scenes.map((s, i) => `<button class="chip${i === showEdit.selected ? " on" : ""}" data-scene-index="${i}">Part ${i + 1}</button>`).join("");
  $("#showSceneTime").textContent = `Part ${showEdit.selected + 1} · ${fmtTime(scene.start)}–${fmtTime(scene.end)}`;
  $("#showSceneText").textContent = scene.text || "";
  $("#showSelectionEffect").hidden = true;
  $("#showSelectionEffect").dataset.text = "";
  const sceneLength = Math.max(0, scene.end - scene.start);
  $("#showEffectAt").value = "0";
  $("#showEffectAt").max = String(Math.max(0, sceneLength - 0.1));
  $("#showEffectDuration").value = String(Math.min(2, sceneLength));
  $("#showEffectDuration").max = String(sceneLength);
  $("#showEffectStatus").textContent = "";
  $("#showSceneVideo").pause();
  $("#showSceneVideo").hidden = true;

  renderShowEffectRows(scene);
  document.dispatchEvent(new CustomEvent("montara:show-scene"));
  $("#showPreviewPart").disabled = false;
  showPlayback(scene,false,resumeOffset);
  if(!showEdit.skipAutoPreviewOnce && scene.preview?.status!=='ready')scheduleShowAutoPreview();
  showEdit.skipAutoPreviewOnce=false;
}
async function pollShowScene(id, token) {
  if (token !== showEdit.previewToken || $("#showReview").hidden) return;
  try {
    const data = await api("/show/scenes");
    const scene = (data.scenes || []).find(s => s.id === id);
    if (!scene) throw new Error("This part is no longer available.");
    if (token !== showEdit.previewToken) return;
    if (scene.preview?.status === "ready") {
      const storedScene = showEdit.scenes.find(s => s.id === id);
      if (storedScene) storedScene.preview = scene.preview;
      $("#showPreviewPart").disabled = false;
      showPlayback(storedScene || scene);
      return;
    }
    if (scene.preview?.status === "failed") throw new Error(scene.preview.error || "Could not prepare this preview.");
    $("#showPreviewStatus").textContent = "Preparing this part…";
    showEdit.previewTimer = setTimeout(() => pollShowScene(id, token), 1200);
  } catch (error) { if (token === showEdit.previewToken) { $("#showPreviewStatus").textContent = error.message; $("#showPreviewPart").disabled = false; } }
}
$("#showSceneTabs").addEventListener("click", event => { const button = event.target.closest("[data-scene-index]"); if (button) { showEdit.selected = Number(button.dataset.sceneIndex); renderShowScene(); } });
$("#showSceneEffects").addEventListener("change", async event => {
  const id = event.target.dataset.showEffect || event.target.dataset.showText;
  if (!id) return;
  const item = showEdit.proposals.find(p => p.id === id);
  if (!item) return;
  try {
    const changes = event.target.dataset.showEffect ? { status: event.target.checked ? "approved" : "discarded" } : { text: event.target.value };
    await showPatch(`/show/review/${encodeURIComponent(id)}`, changes);
    if (changes.status) item.status = changes.status;
    else { item.params ||= {}; item.params.text = changes.text; }
    renderShowScene();
  } catch (error) { toast(error.message, true); renderShowScene(); }
});
document.addEventListener("selectionchange", () => {
  if ($("#showReview").hidden) return;
  const selection = window.getSelection();
  const transcript = $("#showSceneText");
  const text = selection && transcript.contains(selection.anchorNode) && transcript.contains(selection.focusNode) ? selection.toString().trim() : "";
  const button = $("#showSelectionEffect");
  // Keep the choice while the button takes focus; a new selection replaces it.
  if (text) { button.dataset.text = text; button.hidden = false; }
});
$("#showSelectionEffect").addEventListener("click", () => {
  const text = $("#showSelectionEffect").dataset.text || "";
  if (!text) return;
  $("#showEffectKind").value = "word";
  $("#showEffectTextLabel").hidden = false;
  $("#showEffectText").value = text.slice(0, 40);
  $("#showEffectStatus").textContent = text.length > 40 ? "Shortened to 40 characters. Choose the moment and duration below." : "Choose the moment and duration for these words.";
  openShowEffectTools("word", false);
  $("#showEffectText").focus({preventScroll: true});
});
$("#showEffectKind").addEventListener("change", () => {
  $("#showEffectTextLabel").hidden = $("#showEffectKind").value !== "word";
});
$("#showAddEffect").addEventListener("submit", async event => {
  event.preventDefault();
  const scene = showEdit.scenes[showEdit.selected];
  const offset = Number($("#showEffectAt").value);
  const duration = Number($("#showEffectDuration").value);
  const kind = $("#showEffectKind").value;
  const text = $("#showEffectText").value.trim();
  if (!scene || !Number.isFinite(offset) || !Number.isFinite(duration) || offset < 0 || duration < 0.1 || offset + duration > scene.end - scene.start + 0.001) {
    $("#showEffectStatus").textContent = "Keep the effect inside this part."; return;
  }
  if (kind === "word" && !text) { $("#showEffectStatus").textContent = "Write the words for your effect."; return; }
  const button = event.currentTarget.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const item = await api("/show/review/add", {kind, text, at: scene.start + offset, duration, warp: "wave"});
    await showPatch(`/show/review/${encodeURIComponent(item.id)}`, {status: "approved"});
    showPushUndo({type:'proposal',id:item.id,sceneId:scene.id,changes:{status:'discarded'}});
    await refreshShowEditor(scene.id);
    $("#showEffectDialog").close();
  } catch (error) { $("#showEffectStatus").textContent = error.message; }
  finally { button.disabled = false; }
});
$("#showCleanScene").addEventListener("click", async () => {
  const scene=showEdit.scenes[showEdit.selected];
  try{await clearShowSceneEffects(scene);}catch(error){toast(error.message,true);}
});
$("#showStartOver").addEventListener("click",()=>{clearTimeout(showEdit.previewTimer);++showEdit.previewToken;$("#showSceneVideo").pause();show('showStyle');renderShowInput();});
$("#showExport").addEventListener("click", async () => {
  const button = $("#showExport");button.disabled = true;
  try {
    clearTimeout(showEdit.previewTimer);++showEdit.previewToken;$("#showSceneVideo").pause();
    await prepareShowProgramPreview();
    await api("/show/review/render", {});
    setProgress(0, "Finishing your video…", "Keeping the edits you chose.");show("making");startPolling();
  } catch (error) { toast(error.message, true); } finally { button.disabled = false; }
});

// ---------- result ----------
function showResult(s) {
  const result = s.result || {};
  footageMemory.clear(state.platform);  // the video is made; next visit starts clean
  if (state.localProject && !state.savedLocally) {
    state.savedLocally = true;
    const resultUrl = result.url || `/api/v1/wizard/result?t=${Date.now()}`;
    const fileName = `${(result.filename || $("#videoName").value.trim() || todayName()).replace(/\.[a-z0-9]+$/i, "").replace(/[\/\\]/g, "-")}${result.audio ? ".mp3" : ".mp4"}`;
    fetch(resultUrl).then((r) => r.blob()).then((blob) => montaraCompanion.saveInProject(state.localProject.id, fileName, blob))
      .then((saved) => toast(`Saved on your computer: ${saved}`)).catch((error) => toast(error.message, true));
  }
  const url = result.url || `/api/v1/wizard/result?t=${Date.now()}`;
  $("#resultVideo").hidden = Boolean(result.audio);
  $("#resultAudio").hidden = !result.audio;
  $("#resultAudio").src = result.audio ? url : "";
  $("#resultTitle").textContent = result.audio ? "Your master is ready." : state.platform === "show" ? "Your video is ready." : "Your night, edited.";
  const sourceName = result.filename || $("#videoName").value.trim() || todayName();
  const baseName = sourceName.replace(/\.[a-z0-9]+$/i, "").replace(/[\/\\]/g, "-");
  const downloadName = `${baseName}${/montara/i.test(baseName) ? "" : "-Montara"}${result.audio ? ".mp3" : ".mp4"}`;
  $("#resultVideo").classList.toggle("vertical", state.platform === "reel");
  $("#resultVideo").src = result.audio ? "" : url;
  $("#download").href = `${url}${url.includes("?") ? "&" : "?"}download_name=${encodeURIComponent(downloadName)}`;
  $("#download").setAttribute("download", downloadName);
  const bits = [];
  if (result.cut_count) bits.push(`${result.cut_count} cuts`);
  if (result.camera_usage) bits.push(`${Object.keys(result.camera_usage).length} camera${Object.keys(result.camera_usage).length === 1 ? "" : "s"}`);
  $("#resultInfo").textContent = result.audio ? "Your mastered audio is ready." : bits.join(" · ");
  show("result");
  refreshResultAttribution().catch(console.warn);
}

function fail(error) {
  stopPolling();
  $("#errorText").textContent = error.message;
  show("failed");
}

document.addEventListener("DOMContentLoaded", () => {
loadBranding();
api("/montara/version").then((v) => { $("#version").textContent = `Montara ${v.version}`; }).catch(() => {});
show("home");
if (new URLSearchParams(location.search).get("mode") === "show") { state.platform = "show"; openShowSetup().catch(fail); }

});

let showExampleList=[];
async function loadShowExamples(){
  const response=await api('/montara/show/examples');showExampleList=response.items || [];
  $("#showExamples").hidden=!showExampleList.length;
  $("#showExampleChoice").replaceChildren(...showExampleList.map(item=>new Option(item.title,item.id)));
  if(showExampleList.some(item=>item.id===showEdit.pace))$("#showExampleChoice").value=showEdit.pace;
  renderShowExample();
}
function renderShowExample(){
  const item=showExampleList.find(item=>item.id===$("#showExampleChoice").value);if(!item)return;
  $("#showExampleInfo").textContent=`${item.duration} seconds · ${(item.bytes/1024/1024).toFixed(1)} MB including support files`;
  $("#showExampleGuide").href=item.guide_url;$("#showExampleKit").href=item.kit_url;
  $("#showExampleGuideText").textContent=item.id==='podcast' ? "Includes 4 cameras and 5 microphones, with a saved seat map for the first test." : item.id==='storytelling' ? "Includes narration, matching clips and a reference-guided montage plan for the first test." : "Use the same example with Gamer or Influencer to compare the cuts.";
}
$("#showExampleChoice").addEventListener('change',renderShowExample);
$("#showUseExample").addEventListener('click',async()=>{
  if(state.uploads)return;
  const variant=$("#showExampleChoice").value;
  showEdit.pace=variant;
  $$("[data-show-pace]").forEach(button=>{const on=button.dataset.showPace===variant;button.classList.toggle('on',on);button.setAttribute('aria-pressed',String(on));});
  $("#showPaceHint").textContent=variant==='podcast' ? "Microphones and cameras are loaded from the example kit. Every camera shot stays editable." : "The original voice stays with your video.";
  $("#showUseExample").disabled=true;
  try{
    state.files=[];state.projectId=null;
    if(showEdit.blob){URL.revokeObjectURL(showEdit.blob);showEdit.blob=null;}
    await loadSamples(variant);renderShowInput();
  }catch(error){fail(error);}finally{$("#showUseExample").disabled=false;}
});

$("#showChooseType").addEventListener('click',()=>{if(!videos().length)return;$("#showInputVideo").pause();show('showStyle');renderShowInput();});
$("#showStyleBack").addEventListener('click',()=>{show('showSetup');renderShowInput();});
$("#showBackHome").addEventListener('click',()=>show('mode'));
$$("[data-show-step]").forEach(button=>button.addEventListener('click',()=>{if(button.dataset.showStep==='showReview')openShowReview().catch(fail);else{show(button.dataset.showStep);renderShowInput();}}));
window.addEventListener('popstate',event=>{
  const step=event.state?.montaraStep;
  if(state.platform==='show' && ['showSetup','showStyle','showReview','making','result'].includes(step)){
    if(step==='showReview' && !showEdit.scenes.length){showNavigating=true;show('showSetup');showNavigating=false;return;}
    if(['showSetup','showStyle'].includes(step))stopPolling();
    $("#showSceneVideo").pause();showNavigating=true;show(step);showNavigating=false;renderShowInput();
  }else if(state.platform==='show'){showNavigating=true;show('mode');showNavigating=false;}
});

function rejectRaw360(files) {
  if (!Array.from(files).some(f => /\.(insv|msv|insp|lrv|360)$/i.test(f.name))) return false;
  toast("Export a stitched 360 MP4 (equirectangular) from your camera app first. Camera-original INSV/MSV files cannot be edited here.", true);
  return true;
}
async function animateMixFaders(keepLocked = false) {
  const strips = Array.from($("#strips").children), duration = matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 1050;
  const job = mix.job;
  strips.forEach(strip => strip.querySelectorAll("input,button").forEach(el => el.disabled = true));
  $("#playMix").disabled = true; $("#useMix").disabled = true;
  $("#resetMix").disabled = true;
  if (keepLocked) { $("#mixBack").disabled = true; $("#pickReference").disabled = true; $("#useReferenceLink").disabled = true; }
  await new Promise(resolve => {
    const start = performance.now();
    const frame = now => {
      if (mix.job !== job || $("#mix").hidden) { resolve(); return; }
      const p = duration ? Math.min(1, (now - start) / duration) : 1;
      strips.forEach((strip, i) => {
        const t = mix.plan.tracks[i], amount = 1 - Math.pow(1 - p, 3);
        const value = -60 + (t.fader_db + 60) * amount;
        strip.querySelector('input[type=range]').value = value;
        strip.querySelector('.db').textContent = `${value >= 0 ? '+' : ''}${value.toFixed(1)} dB`;
      });
      if (p < 1) requestAnimationFrame(frame); else resolve();
    };
    requestAnimationFrame(frame);
  });
  if (mix.job === job && !keepLocked) {
    strips.forEach((strip, i) => strip.querySelectorAll("input,button").forEach(el => el.disabled = mix.plan.tracks[i].active === false));
    $("#playMix").disabled = false; $("#useMix").disabled = false;
    $("#resetMix").disabled = false; $("#mixBack").disabled = false;
  }
}
