// Montara web interface. Talks to the unchanged engine API at /api/v1 and to
// Montara's own small endpoints at /montara/*.
"use strict";

const MODES = { youtube: "Stage", reel: "Pulse", show: "Story" };
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
const guessRole = (f) => (/fixed|tripod|static|iphone|\.mov$/i.test(f.name) ? "fixed_rear" : "handheld");
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
  if (!response.ok) throw new Error(data.error?.message || `Request failed (${response.status})`);
  return data;
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

const STEP_ORDER = ["footage", "cameras", "mix", "making", "frames", "captions", "result"];
// Steps that apply to this video: no Mix step without separate tracks, no Captions outside Pulse.
function stepApplies(step) {
  if (step === "cameras") return !state.files.length || videos().length > 1 || videos().some(isSphere);
  if (step === "mix") return mixerMode();
  if (step === "captions") return state.platform === "reel";
  return true;
}
function show(id) {
  $$(".screen").forEach((s) => { s.hidden = s.id !== id; });
  const inFlow = STEP_ORDER.includes(id) || id === "failed" || id === "mode";
  $("#steps").hidden = !inFlow;
  $("#newVideo").hidden = inFlow;
  const current = STEP_ORDER.indexOf(id === "failed" ? "making" : id === "mode" ? "footage" : id);
  $$("#steps span").forEach((span, index) => {
    span.hidden = !stepApplies(span.dataset.step);
    span.classList.toggle("on", index === current);
    span.classList.toggle("done", index < current);
  });
  window.scrollTo({ top: 0 });
}

function todayName() {
  const d = new Date();
  return `Session ${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const videos = () => state.files.filter((f) => f.kind === "video");
const audioTracks = () => state.files.filter((f) => f.kind === "master" || f.kind === "songs");
// Several audio files on Stage = separate instrument/mic tracks -> the mixer makes the master.
const mixerMode = () => state.platform === "youtube" && audioTracks().length >= 2;
const isSphere = (f) => f.projection === "equirect" || f.projection === "raw_insv" || /\.insv$/i.test(f.name);

// ---------- navigation ----------
document.addEventListener("click", (event) => {
  const go = event.target.closest("[data-go]");
  if (!go) return;
  event.preventDefault();
  const target = go.dataset.go;
  if ((target === "mode" || target === "home") && state.polling) return toast("A video is still being made.");
  if (target === "mode") resetFlow();
  show(target);
});

$$(".mode[data-platform]").forEach((card) => card.addEventListener("click", () => {
  state.platform = card.dataset.platform;
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
}));

function resetFlow() {
  stopPolling();
  state.platform = null;
  state.files = [];
  state.projectId = null;
  state.captioned = false;
  cap.list = [];
  cap.timed = false;
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
async function loadSamples(variant = "") {
  if (state.files.some((f) => !f.sample)) return;  // the person already added their own files
  state.files = state.files.filter((f) => !f.sample);
  const response = await fetch(`/montara/samples?platform=${encodeURIComponent(state.platform)}&variant=${variant}`);
  const data = response.ok ? await response.json() : { enabled: false };
  if (!data.enabled) return;
  for (const [group, kind] of [["videos", "video"], ["master", "master"], ["songs", "songs"]]) {
    for (const item of data[group] || []) {
      state.files.push({ id: crypto.randomUUID(), name: item.path.split("/").pop(), kind, path: item.path, projection: item.projection, sample: true });
    }
  }
  for (const [path, slots] of Object.entries(data.viewpoints || {})) state.viewpoints[path] = structuredClone(slots);
  $("#sampleNote").hidden = false;
  state.sampleVariant = variant;
  $("#variantRow").hidden = state.platform !== "youtube";
  $("#switchSample").textContent = variant === "master" ? "Use the 14 separate tracks instead" : "Use the finished master instead";
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
  drop.addEventListener("drop", (e) => addFiles([...e.dataTransfer.files]));
  drop.querySelector("input").addEventListener("change", (e) => { addFiles([...e.target.files]); e.target.value = ""; });
});
$("#reelDuration").addEventListener("input", (e) => { $("#reelDurationOut").textContent = `${e.target.value} s`; });

function addFiles(list) {
  if (state.files.some((f) => f.sample)) { state.files = state.files.filter((f) => !f.sample); $("#sampleNote").hidden = true; }
  for (const file of list) {
    const entry = { id: crypto.randomUUID(), name: file.name, kind: "uploading", progress: 0 };
    state.files.push(entry);
    upload(file, entry);
  }
  renderFiles();
}

function upload(file, entry) {
  state.uploads += 1;
  const xhr = new XMLHttpRequest();
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
      } else {
        entry.kind = "error";
        entry.error = "Not a usable media file";
      }
    }
    renderFiles();
  };
  xhr.onerror = () => { state.uploads -= 1; entry.kind = "error"; entry.error = "Connection interrupted"; renderFiles(); };
  xhr.send(file);
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
      <span class="state">${f.kind === "uploading" ? Math.round(f.progress * 100) + "%" : f.kind === "error" ? escapeHtml(f.error) : f.kind === "ignored" ? escapeHtml(f.reason || "not used") : "Ready"}</span>
      ${f.kind === "uploading" ? `<span class="bar"><i style="width:${Math.round(f.progress * 100)}%"></i></span>` : ""}
    </li>`;
}
function renderFiles() {
  $("#audioFiles").innerHTML = state.files.filter(isAudioEntry).map(fileRow).join("");
  $("#audioFiles").classList.toggle("compact", state.files.filter(isAudioEntry).length > 4);
  $("#videoFiles").innerHTML = state.files.filter((f) => !isAudioEntry(f)).map(fileRow).join("");
  const master = state.files.find((f) => f.kind === "master");
  let hint = "";
  let ready = videos().length > 0 && state.uploads === 0;
  if (mixerMode()) hint = `${audioTracks().length} separate tracks: Montara will mix them for you, then you can adjust every fader.`;
  else if (state.platform === "youtube" && !master) { hint = "Stage needs the master audio (one mixed track of the song) to sync every camera."; ready = false; }
  if (state.platform === "reel" && !master && videos().length > 1) hint = "Tip: add the song so the reel cuts on the music.";
  if (state.uploads) hint = "Uploading…";
  if (state.branding === "mine" && !state.hasLogo) { hint = "Choose your logo, or pick another option."; ready = false; }
  $("#footageHint").textContent = hint;
  $("#continueFootage").disabled = !ready;
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
$$("input[name=format]").forEach((radio) => radio.addEventListener("change", () => {
  $("#mixShareRow").hidden = reelFormat() !== "mix_vertical_horizontal";
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
  $("#continueFootage").disabled = true;
  try {
    await api("/montara/branding", { mode: state.branding });
    const name = $("#videoName").value.trim() || todayName();
    const data = inputs();
    await api("/wizard/projects/new", {});
    const draft = await api("/wizard/draft", { name, project_id: null, platform: state.platform, audio_paths: data.master ? [data.master] : [], ...data });
    state.mixMaster = null;
    state.projectId = draft.project_id;
  } finally {
    $("#continueFootage").disabled = false;
  }
  const needsCameras = videos().length > 1 || videos().some(isSphere);
  if (!needsCameras) return afterCameras();
  renderCameras();
  show("cameras");
}

// ---------- cameras & 360 viewpoints ----------
function renderCameras() {
  const flat = videos().filter((f) => !isSphere(f));
  const spheres = videos().filter(isSphere);
  $("#cameraList").innerHTML = flat.map((f) => `
    <div class="cam">
      <span class="kind video">VIDEO</span><span class="name">${escapeHtml(f.name)}</span>
      <span class="camsel"><label>Shows <select data-subject="${escapeHtml(f.path)}">${SUBJECTS.map(([value, label]) =>
        `<option value="${value}" ${(state.subjects[f.path] || "general") === value ? "selected" : ""}>${label}</option>`).join("")}</select></label>
      <label>Filmed <select data-role="${escapeHtml(f.path)}"><option value="fixed_rear" ${(state.roles[f.path] || guessRole(f)) === "fixed_rear" ? "selected" : ""}>On a tripod</option><option value="handheld" ${(state.roles[f.path] || guessRole(f)) === "handheld" ? "selected" : ""}>Handheld</option></select></label></span>
    </div>`).join("");
  $$("[data-role]").forEach((select) => select.addEventListener("change", () => { state.roles[select.dataset.role] = select.value; }));
  $$("[data-subject]").forEach((select) => select.addEventListener("change", () => { state.subjects[select.dataset.subject] = select.value; }));
  $("#sphereList").innerHTML = spheres.map((f, index) => `
    <div class="sphere" data-sphere="${index}">
      <h3><span class="kind video">360</span> ${escapeHtml(f.name)}</h3>
      <p class="hint">Choose a point of view on the left, then click where it should look in the 360 image. Name it as you like.</p>
      <div class="sphere-body">
        <ul class="slots"></ul>
        <div class="pano-wrap">
          <div class="pano"><div class="pano-img"></div><span class="loading">Loading 360 frame…</span></div>
          <p class="hint tiny">Drag the 360 image to turn it · click to place the selected point of view</p>
          <div class="preview"><div class="pv"><img alt="" hidden draggable="false"></div><span class="hint">Preview. Drag it to aim, scroll to zoom.</span></div>
        </div>
      </div>
    </div>`).join("");
  spheres.forEach((f, index) => setupSphere(f, $(`[data-sphere="${index}"]`)));
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
  frame.onload = () => { pano.querySelector(".loading").hidden = true; panoImg.style.backgroundImage = `url("${frame.src}")`; place(); };
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

  let previewTimer = null;
  function preview(immediate = true) {
    const view = views[active];
    const img = root.querySelector(".preview img");
    if (!view) { img.hidden = true; return; }
    const load = () => {
      const zoom = zoomOf(view);
      const params = new URLSearchParams({ source: file.path, shot: active, yaw: view.yaw, pitch: view.pitch, fov: view.fov,
        projection_preset: view.projection_preset || zoom[3], time_sec: 20 });
      img.src = `/api/v1/wizard/spherical-preview?${params}`;
      img.hidden = false;
    };
    clearTimeout(previewTimer);
    if (immediate) load(); else previewTimer = setTimeout(load, 180);
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
    drawMarkers(); preview(false);
  });
  pv.addEventListener("pointerup", () => { if (aim) { aim = null; preview(); } });
  pv.addEventListener("wheel", (e) => {
    const view = views[active];
    if (!view) return;
    e.preventDefault();
    const index = ZOOMS.indexOf(zoomOf(view));
    const next = ZOOMS[Math.max(0, Math.min(ZOOMS.length - 1, index + (e.deltaY > 0 ? 1 : -1)))];
    setZoom(active, next);
    renderSlots(); preview(false);
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

async function openMixer() {
  show("mix");
  stopMix();
  $("#mixStatus").classList.remove("done");
  $("#mixStatusText").textContent = "Mixing your tracks automatically…";
  $("#transport").hidden = true;
  $("#referenceRow").hidden = true;
  $("#useMix").disabled = true;
  $("#strips").innerHTML = "";
  const job = await api("/montara/mix", { tracks: audioTracks().map((f) => f.path) });
  mix.job = job.id;
  const ready = await pollMix((j) => j.status !== "analyzing");
  if (ready.status === "failed") throw new Error(ready.error || "The automatic mix failed");
  mix.plan = ready.plan;
  renderStrips();
  $("#mixStatusText").textContent = "Loading the tracks for the preview…";
  await loadBuffers();
  $("#mixStatus").classList.add("done");
  $("#mixStatusText").textContent = "Auto-mix ready. Faders start where Montara put them.";
  $("#transport").hidden = false;
  $("#referenceRow").hidden = false;
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
  const fader = Number(track.fader_db || 0);
  return track.mute || track.active === false ? 0 : dbToGain(Number(track.auto_gain_db || 0) + fader);
}

function renderStrips() {
  $("#strips").innerHTML = mix.plan.tracks.map((t, i) => `
    <div class="strip ${t.mute || t.active === false ? "off" : ""}" data-track="${i}" title="${escapeHtml(t.active === false ? `${t.file}: almost no signal, so the mix leaves it out` : t.file)}">
      <small>${escapeHtml(t.role)}</small>
      <span class="db">${(t.fader_db >= 0 ? "+" : "") + Number(t.fader_db).toFixed(1)} dB</span>
      <input type="range" min="-24" max="12" step="0.5" value="${t.fader_db}" aria-label="${escapeHtml(t.name)} fader">
      ${t.active === false ? `<button class="mute" disabled>NO SIGNAL</button>` : `<button class="mute ${t.mute ? "on" : ""}">${t.mute ? "OFF" : "ON"}</button>`}
      <b>${escapeHtml(t.name)}</b>
    </div>`).join("");
  $$(".strip").forEach((strip) => {
    const track = mix.plan.tracks[Number(strip.dataset.track)];
    track.auto_mute = track.auto_mute ?? track.mute;
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
    mix.nodes[t.file] = { source, gain };
  }
  mix.startedAt = ctx.currentTime - offset;
  mix.playing = true;
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
  for (const node of Object.values(mix.nodes)) { try { node.source.stop(); } catch { /* already stopped */ } }
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
$("#resetMix").addEventListener("click", () => {
  for (const t of mix.plan.tracks) { t.fader_db = 0; t.mute = t.auto_mute; applyGain(t); }
  renderStrips();
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
$("#mixBack").addEventListener("click", () => { stopMix(); show(videos().length > 1 || videos().some(isSphere) ? "cameras" : "footage"); });

$("#useMix").addEventListener("click", async () => {
  try {
    stopMix();
    $("#useMix").disabled = true;
    $("#mixStatus").classList.remove("done");
    $("#mixStatusText").textContent = "Rendering the final mix and mastering it…";
    const faders = Object.fromEntries(mix.plan.tracks.map((t) => [t.file, Number(t.fader_db || 0)]));
    const mutes = Object.fromEntries(mix.plan.tracks.map((t) => [t.file, Boolean(t.mute)]));
    await api(`/montara/mix/${mix.job}/render`, { faders, mutes });
    const job = await pollMix((j) => j.status === "done");
    if (job.status === "failed") throw new Error(job.error || "The final mix failed");
    state.mixMaster = job.master_path;
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
    reel_aspect: platform === "reel" ? reelFormat() : undefined,
    reel_mix_vertical_ratio: platform === "reel" && reelFormat() === "mix_vertical_horizontal" ? $("#mixShare").value : undefined,
  });
  state.captioned = false;
  startPolling();
}

async function status() {
  const query = state.projectId ? `?project_id=${encodeURIComponent(state.projectId)}` : "";
  return api(`/wizard/status${query}`);
}

async function waitFor(predicate) {
  for (let i = 0; i < 1200; i += 1) {
    const s = await status();
    renderStatus(s);
    if (s.status === "failed") throw new Error(s.error || s.message || "Preparation failed");
    if (predicate(s)) return s;
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error("The preparation is taking too long.");
}

function startPolling() {
  stopPolling();
  state.polling = setInterval(async () => {
    try {
      const s = await status();
      renderStatus(s);
      if (s.status === "waiting_review") {
        stopPolling();
        openFrames();
      } else if (s.status === "done") {
        stopPolling();
        if (state.platform === "reel" && !state.captioned) openCaptions();
        else showResult(s);
      } else if (s.status === "failed" || s.status === "cancelled") {
        stopPolling();
        fail(new Error(s.error || s.message || "The edit stopped"));
      }
    } catch (error) {
      console.warn(error);
    }
  }, 1000);
}

function stopPolling() { clearInterval(state.polling); state.polling = null; clearInterval(state.framesPoll); state.framesPoll = null; }

function renderStatus(s) {
  const task = (s.tasks || [])[0] || {};
  setProgress(Number(s.progress || 0), task.label || s.message || "Working…", s.detail || "");
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
  show("footage");
});

// ---------- frames ----------
// Name a 360 shot by where it really looks: the person's view closest to the shot's
// direction. The engine's slot type alone can be a variant aimed elsewhere.
const angleGap = (a, b) => Math.abs((((a - b) % 360) + 540) % 360 - 180);
function viewpointName(item) {
  const pose = item.pose || {};
  if (!item.landmark && !pose.type) return "";
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
    return "other angle";
  }
  const type = String(pose.type || "");
  for (const views of Object.values(state.viewpoints)) if (views[type]?.enabled && views[type].subject) return views[type].subject;
  return "360 view";
}
const swapping = new Set();
async function openFrames() {
  show("frames");
  $("#frameGrid").innerHTML = "";
  $("#framesHint").textContent = "Preparing the shots…";
  await refreshFrames(true);
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
        <div class="thumb"><img alt="" hidden><span class="spin"></span></div>
        <figcaption><b>${String(item.index + 1).padStart(2, "0")}</b> <span class="src"></span> <span class="dur"></span></figcaption>
        <button class="btn ghost small swap">Swap</button>
      </figure>`).join("");
    grid.querySelectorAll(".swap").forEach((button) => button.addEventListener("click", () => swap(Number(button.closest(".frame").dataset.index))));
  }
  for (const item of items) {
    const fig = grid.querySelector(`[data-index="${item.index}"]`);
    const img = fig.querySelector("img");
    const landmark = viewpointName(item);
    const label = landmark ? `360 · ${landmark}` : item.source;
    if (item.thumbnail && img.getAttribute("src") !== item.thumbnail) {
      img.src = item.thumbnail;
      img.hidden = false;
      swapping.delete(item.index);
      fig.querySelector(".src").textContent = label;
    } else if (!fig.querySelector(".src").textContent) {
      fig.querySelector(".src").textContent = label;
    }
    fig.classList.toggle("busy", !item.thumbnail || swapping.has(item.index));
    fig.querySelector(".dur").textContent = `${Number(item.duration_sec).toFixed(1)} s`;
    fig.querySelector(".swap").disabled = item.candidate_count !== undefined && item.candidate_count < 2;
  }
  if (!pending) { clearInterval(state.framesPoll); state.framesPoll = null; }
}

async function swap(index) {
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
// which burns them onto a clean copy of the rendered reel.
const CAP_STYLES = [
  ["clean_bottom", "Clean", ""], ["karaoke_word", "Karaoke", "karaoke"], ["bold_pop", "Bold", "big"],
  ["hard_shadow", "Shadow", "shadow"], ["neon_glow", "Glow", "neon"], ["lyric_serif", "Serif", "serif"],
];
const cap = { list: [], style: "clean_bottom", pos: 80, timed: false, raf: 0 };
const capVideo = () => $("#capVideo");
const capDuration = () => Number(capVideo().duration) || Number($("#reelDuration").value) || 30;
const fmtSec = (x) => Number(x).toFixed(1);

function openCaptions() {
  show("captions");
  $("#capStage").classList.toggle("wide", reelFormat() === "16:9");
  capVideo().src = `/api/v1/wizard/compose-base?t=${Date.now()}`;
  $("#capStyles").innerHTML = CAP_STYLES.map(([id, label]) => `<button type="button" class="chip${id === cap.style ? " on" : ""}" data-style="${id}">${label}</button>`).join("");
  renderCapList();
  previewCaption();
}

function spreadCaptions(texts) {
  const duration = capDuration();
  const start = Math.min(1, duration * 0.05);
  const slot = (duration - start - 0.5) / Math.max(1, texts.length);
  cap.list = texts.map((text, i) => ({ text, start: start + i * slot, end: start + (i + 1) * slot - 0.15 }));
}

function textLines() { return $("#capText").value.split("\n").map((line) => line.trim()).filter(Boolean); }

$("#capText").addEventListener("input", () => {
  const lines = textLines();
  if (!cap.timed || lines.length !== cap.list.length) { cap.timed = false; spreadCaptions(lines); }
  else lines.forEach((text, i) => { cap.list[i].text = text; cap.list[i].words = undefined; });
  renderCapList();
  previewCaption();
});
$("#capSpread").addEventListener("click", () => { cap.timed = false; spreadCaptions(textLines()); renderCapList(); previewCaption(); });

function renderCapList() {
  $("#capList").innerHTML = cap.list.map((c, i) => `
    <li data-i="${i}"><input type="text" value="${escapeHtml(c.text)}" data-f="text" aria-label="Caption ${i + 1}">
      <input type="number" step="0.1" min="0" value="${fmtSec(c.start)}" data-f="start" aria-label="Starts at (s)">
      <input type="number" step="0.1" min="0" value="${fmtSec(c.end)}" data-f="end" aria-label="Ends at (s)">
      <button type="button" class="x" aria-label="Delete">✕</button></li>`).join("");
}

$("#capList").addEventListener("input", (event) => {
  const li = event.target.closest("li");
  const c = cap.list[Number(li.dataset.i)];
  const field = event.target.dataset.f;
  if (field === "text") { c.text = event.target.value; c.words = undefined; $("#capText").value = cap.list.map((x) => x.text).join("\n"); }
  else { c[field] = Math.max(0, Number(event.target.value) || 0); cap.timed = true; }
  previewCaption();
});
$("#capList").addEventListener("click", (event) => {
  const li = event.target.closest("li");
  if (!li) return;
  const i = Number(li.dataset.i);
  if (event.target.classList.contains("x")) {
    cap.list.splice(i, 1);
    $("#capText").value = cap.list.map((x) => x.text).join("\n");
    renderCapList();
  } else if (event.target.dataset.f !== "text") {
    capVideo().currentTime = cap.list[i].start + 0.05;
  }
  previewCaption();
});

$("#capStyles").addEventListener("click", (event) => {
  const chip = event.target.closest("[data-style]");
  if (!chip) return;
  cap.style = chip.dataset.style;
  $$("#capStyles .chip").forEach((c) => c.classList.toggle("on", c === chip));
  previewCaption();
});
$("#capPositions").addEventListener("click", (event) => {
  const chip = event.target.closest("[data-pos]");
  if (!chip) return;
  cap.pos = Number(chip.dataset.pos);
  $$("#capPositions .chip").forEach((c) => c.classList.toggle("on", c === chip));
  previewCaption();
});
$("#capTitle").addEventListener("input", previewCaption);

// Approximate live preview over the player (the burn uses the engine's exact style).
function previewCaption() {
  const t = capVideo().currentTime || 0;
  const index = cap.list.findIndex((c) => t >= c.start && t < c.end);
  const line = $("#capPreview");
  line.hidden = index < 0;
  if (index >= 0) {
    line.textContent = cap.list[index].text;
    line.className = `capline ${CAP_STYLES.find(([id]) => id === cap.style)[2]}`;
    line.style.top = `${cap.pos}%`;
  }
  $$("#capList li").forEach((li) => li.classList.toggle("now", Number(li.dataset.i) === index));
  const title = $("#capTitle").value.trim();
  $("#capTitlePreview").hidden = !title;
  $("#capTitlePreview").textContent = title;
}
function previewLoop() { previewCaption(); cap.raf = capVideo().paused ? 0 : requestAnimationFrame(previewLoop); }
capVideo().addEventListener("play", () => { cancelAnimationFrame(cap.raf); previewLoop(); });
capVideo().addEventListener("seeked", previewCaption);
capVideo().addEventListener("loadedmetadata", () => { if (!cap.timed && cap.list.length) spreadCaptions(textLines()); renderCapList(); });

// Transcribe the reel's own audio (local Whisper in the engine) into timed captions.
$("#capRead").addEventListener("click", async () => {
  const button = $("#capRead");
  button.disabled = true;
  $("#capReadStatus").textContent = "Listening to the reel…";
  try {
    await api("/captions/auto-read", { model: "small" });
    for (;;) {
      await new Promise((r) => setTimeout(r, 1500));
      const job = await api("/captions/auto-read/status");
      if (job.status === "failed") throw new Error(job.error || "Could not read the lyrics");
      if (job.status === "done") {
        const cues = job.result?.cues || [];
        if (!cues.length) { $("#capReadStatus").textContent = "No words were heard in this reel."; break; }
        cap.list = cues.map((c) => ({ text: (c.lines || []).join(" "), start: c.start, end: c.end, words: c.words }));
        cap.timed = true;
        $("#capText").value = cap.list.map((c) => c.text).join("\n");
        renderCapList();
        previewCaption();
        $("#capReadStatus").textContent = `${cues.length} captions read. Check the words before adding them.`;
        break;
      }
      $("#capReadStatus").textContent = `Listening to the reel… ${job.progress || 0}%`;
    }
  } catch (error) {
    $("#capReadStatus").textContent = error.message;
  } finally {
    button.disabled = false;
  }
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

$("#capSkip").addEventListener("click", async () => { capVideo().pause(); state.captioned = true; showResult(await status()); });
$("#capApply").addEventListener("click", async () => {
  capVideo().pause();
  const title = $("#capTitle").value.trim();
  const cues = cap.list.filter((c) => c.text.trim() && c.end > c.start).map((c) => ({
    lines: splitCaption(c.text.trim()), start: c.start, end: c.end, words: c.words || [], style_override: { vertical: cap.pos },
  }));
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

// ---------- result ----------
function showResult(s) {
  const result = s.result || {};
  const url = `/api/v1/wizard/result?t=${Date.now()}`;
  $("#resultVideo").classList.toggle("vertical", state.platform === "reel" && reelFormat() !== "16:9");
  $("#resultVideo").src = url;
  $("#download").href = url;
  if (result.filename) $("#download").setAttribute("download", result.filename);
  const bits = [];
  if (result.cut_count) bits.push(`${result.cut_count} cuts`);
  if (result.camera_usage) bits.push(`${Object.keys(result.camera_usage).length} camera${Object.keys(result.camera_usage).length === 1 ? "" : "s"}`);
  $("#resultInfo").textContent = bits.join(" · ");
  show("result");
}

function fail(error) {
  stopPolling();
  $("#errorText").textContent = error.message;
  show("failed");
}

loadBranding();
show("home");
