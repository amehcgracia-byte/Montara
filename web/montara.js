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
const ZOOMS = [["wide", "Wide", 115], ["normal", "Normal", 95], ["close", "Close", 75]];
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

const STEP_ORDER = ["footage", "cameras", "making", "frames", "result"];
function show(id) {
  $$(".screen").forEach((s) => { s.hidden = s.id !== id; });
  const inFlow = STEP_ORDER.includes(id) || id === "failed" || id === "mode";
  $("#steps").hidden = !inFlow;
  $("#newVideo").hidden = inFlow;
  const current = STEP_ORDER.indexOf(id === "failed" ? "making" : id === "mode" ? "footage" : id);
  $$("#steps span").forEach((span, index) => {
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
  if (!$("#videoName").value) $("#videoName").value = todayName();
  $("#boxHelp").innerHTML = (BOX_HELP[state.platform] || []).map(([t, d]) => `<div><b>${t}</b><span>${d}</span></div>`).join("");
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
  state.viewpoints = {};
  state.subjects = {};
  $("#videoName").value = "";
  $("#sampleNote").hidden = true;
  renderFiles();
}

// ---------- samples ----------
async function loadSamples() {
  if (state.files.length) return;  // the person already added their own files
  const response = await fetch(`/montara/samples?platform=${encodeURIComponent(state.platform)}`);
  const data = response.ok ? await response.json() : { enabled: false };
  if (!data.enabled) return;
  for (const [group, kind] of [["videos", "video"], ["master", "master"], ["songs", "songs"]]) {
    for (const item of data[group] || []) {
      state.files.push({ id: crypto.randomUUID(), name: item.path.split("/").pop(), kind, path: item.path, projection: item.projection, sample: true });
    }
  }
  for (const [path, slots] of Object.entries(data.viewpoints || {})) state.viewpoints[path] = structuredClone(slots);
  $("#sampleNote").hidden = false;
  renderFiles();
}

$("#clearSamples").addEventListener("click", () => {
  state.files = state.files.filter((f) => !f.sample);
  $("#sampleNote").hidden = true;
  renderFiles();
});

// ---------- footage ----------
const drop = $("#drop");
["dragenter", "dragover"].forEach((name) => drop.addEventListener(name, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((name) => drop.addEventListener(name, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (e) => addFiles([...e.dataTransfer.files]));
$("#fileInput").addEventListener("change", (e) => { addFiles([...e.target.files]); e.target.value = ""; });
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
function renderFiles() {
  $("#files").innerHTML = state.files.map((f) => `
    <li>
      <span class="kind ${f.kind}">${f.kind === "video" && isSphere(f) ? "360" : KIND_LABEL[f.kind] || f.kind.toUpperCase()}</span>
      <span class="name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</span>
      <span class="state">${f.kind === "uploading" ? Math.round(f.progress * 100) + "%" : f.kind === "error" ? escapeHtml(f.error) : f.kind === "ignored" ? escapeHtml(f.reason || "not used") : "Ready"}</span>
      ${f.kind === "uploading" ? `<span class="bar"><i style="width:${Math.round(f.progress * 100)}%"></i></span>` : ""}
    </li>`).join("");
  const master = state.files.find((f) => f.kind === "master");
  let hint = "";
  let ready = videos().length > 0 && state.uploads === 0;
  if (state.platform === "youtube" && !master) { hint = "Stage needs the master audio (one mixed track of the song) to sync every camera."; ready = false; }
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

function inputs() {
  const master = state.files.find((f) => f.kind === "master");
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
    state.projectId = draft.project_id;
  } finally {
    $("#continueFootage").disabled = false;
  }
  const needsCameras = videos().length > 1 || videos().some(isSphere);
  if (!needsCameras) return make();
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
      <label>Shows <select data-subject="${escapeHtml(f.path)}">${SUBJECTS.map(([value, label]) =>
        `<option value="${value}" ${(state.subjects[f.path] || "general") === value ? "selected" : ""}>${label}</option>`).join("")}</select></label>
    </div>`).join("");
  $$("[data-subject]").forEach((select) => select.addEventListener("change", () => { state.subjects[select.dataset.subject] = select.value; }));
  $("#sphereList").innerHTML = spheres.map((f, index) => `
    <div class="sphere" data-sphere="${index}">
      <h3><span class="kind video">360</span> ${escapeHtml(f.name)}</h3>
      <p class="hint">Choose a point of view on the left, then click where it should look in the 360 image. Name it as you like.</p>
      <div class="sphere-body">
        <ul class="slots"></ul>
        <div class="pano-wrap">
          <div class="pano"><img alt="360 frame" draggable="false"><span class="loading">Loading 360 frame…</span></div>
          <div class="preview"><img alt="" hidden><span class="hint">Preview of the selected point of view</span></div>
        </div>
      </div>
    </div>`).join("");
  spheres.forEach((f, index) => setupSphere(f, $(`[data-sphere="${index}"]`)));
}

function setupSphere(file, root) {
  const views = state.viewpoints[file.path] ||= {};
  let active = Object.keys(views).find((slot) => views[slot].enabled) || "full_stage";
  const pano = root.querySelector(".pano");
  const panoImg = pano.querySelector("img");
  panoImg.onload = () => { pano.querySelector(".loading").hidden = true; drawMarkers(); };
  panoImg.onerror = () => { pano.querySelector(".loading").textContent = "Could not load the 360 frame."; };
  panoImg.src = `/api/v1/wizard/spherical-source-frame?source=${encodeURIComponent(file.path)}`;

  function renderSlots() {
    root.querySelector(".slots").innerHTML = VIEW_SLOTS.map(([slot, fallback]) => {
      const view = views[slot];
      const zoom = view ? (ZOOMS.find(([, , fov]) => Math.abs(fov - view.fov) < 12)?.[0] || "normal") : "normal";
      return `<li class="slot ${slot === active ? "on" : ""} ${view?.enabled ? "set" : ""}" data-slot="${slot}">
        <input type="checkbox" ${view?.enabled ? "checked" : ""} title="Use this point of view">
        <input type="text" value="${escapeHtml(view?.subject || fallback)}" maxlength="24">
        <select title="Zoom">${ZOOMS.map(([value, label]) => `<option value="${value}" ${zoom === value ? "selected" : ""}>${label}</option>`).join("")}</select>
      </li>`;
    }).join("");
    root.querySelectorAll(".slot").forEach((li) => {
      const slot = li.dataset.slot;
      li.addEventListener("click", (e) => { if (e.target.tagName !== "INPUT" && e.target.tagName !== "SELECT") { active = slot; renderSlots(); drawMarkers(); preview(); } });
      li.querySelector("input[type=checkbox]").addEventListener("change", (e) => {
        if (!views[slot]) { active = slot; renderSlots(); return toast("Now click in the 360 image where this view should look."); }
        views[slot].enabled = e.target.checked; drawMarkers();
      });
      li.querySelector("input[type=text]").addEventListener("input", (e) => { if (views[slot]) views[slot].subject = e.target.value; });
      li.querySelector("input[type=text]").addEventListener("focus", () => { active = slot; root.querySelectorAll(".slot").forEach((x) => x.classList.toggle("on", x.dataset.slot === slot)); drawMarkers(); });
      li.querySelector("select").addEventListener("change", (e) => {
        if (!views[slot]) return;
        views[slot].fov = ZOOMS.find(([value]) => value === e.target.value)[2];
        if (slot === active) preview();
      });
    });
  }

  function drawMarkers() {
    pano.querySelectorAll(".pin").forEach((pin) => pin.remove());
    for (const [slot, view] of Object.entries(views)) {
      if (!view.enabled && slot !== active) continue;
      const pin = document.createElement("span");
      pin.className = "pin" + (slot === active ? " on" : "");
      pin.style.left = `${(view.yaw + 180) / 360 * 100}%`;
      pin.style.top = `${(90 - view.pitch) / 180 * 100}%`;
      pin.textContent = view.subject || slot;
      pano.append(pin);
    }
  }

  function preview() {
    const view = views[active];
    const img = root.querySelector(".preview img");
    if (!view) { img.hidden = true; return; }
    const params = new URLSearchParams({ source: file.path, shot: active, yaw: view.yaw, pitch: view.pitch, fov: view.fov, time_sec: 20 });
    img.src = `/api/v1/wizard/spherical-preview?${params}`;
    img.hidden = false;
  }

  pano.addEventListener("click", (e) => {
    const rect = panoImg.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    if (x < 0 || x > 1 || y < 0 || y > 1) return;
    const label = VIEW_SLOTS.find(([slot]) => slot === active)[1];
    const previous = views[active];
    views[active] = {
      yaw: Math.round((x * 360 - 180) * 10) / 10,
      pitch: Math.round((90 - y * 180) * 10) / 10,
      fov: previous?.fov || 95,
      subject: previous?.subject || label,
      enabled: true,
    };
    renderSlots(); drawMarkers(); preview();
  });

  renderSlots();
  preview();
}

$("#continueCameras").addEventListener("click", () => saveCameras().then(make).catch(fail));

async function saveCameras() {
  const flat = videos().filter((f) => !isSphere(f));
  const subjects = Object.fromEntries(flat.map((f) => [f.path, state.subjects[f.path] || "general"]));
  if (flat.length) await api("/settings/camera-subjects", { camera_subjects: subjects });
  for (const file of videos().filter(isSphere)) {
    const views = state.viewpoints[file.path] || {};
    if (!Object.keys(views).length) continue;
    await api("/settings/spherical-landmarks", { spherical_landmarks: views, spherical_source_path: file.path });
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
  });
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
        showResult(s);
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
    if (item.thumbnail && img.getAttribute("src") !== item.thumbnail) {
      img.src = item.thumbnail;
      img.hidden = false;
      swapping.delete(item.index);
    }
    fig.classList.toggle("busy", !item.thumbnail || swapping.has(item.index));
    const landmark = String(item.landmark || "").replace(/encuadre alternativo/i, "alternative angle");
    fig.querySelector(".src").textContent = landmark ? `360 · ${landmark}` : item.source;
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

// ---------- result ----------
function showResult(s) {
  const result = s.result || {};
  const url = `/api/v1/wizard/result?t=${Date.now()}`;
  $("#resultVideo").classList.toggle("vertical", state.platform === "reel");
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
