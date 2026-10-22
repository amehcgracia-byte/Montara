// Montara web interface. Talks to the unchanged engine API at /api/v1.
"use strict";

const MODES = { youtube: "Stage", reel: "Pulse", show: "Story" };
const state = {
  platform: null,
  files: [],          // {id, name, kind: video|master|songs|ignored|uploading|error, path, progress}
  uploads: 0,
  projectId: null,
  polling: null,
  reviewRendered: false,
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

async function api(path, body) {
  const options = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const response = await fetch(`/api/v1${path}`, options);
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

const STEP_ORDER = ["mode", "footage", "making", "result"];
function show(id) {
  $$(".screen").forEach((s) => { s.hidden = s.id !== id; });
  const inFlow = STEP_ORDER.includes(id) || id === "failed";
  $("#steps").hidden = !inFlow;
  $("#newVideo").hidden = inFlow;
  const current = STEP_ORDER.indexOf(id === "failed" ? "making" : id);
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

// ---------- navigation ----------
document.addEventListener("click", (event) => {
  const go = event.target.closest("[data-go]");
  if (!go) return;
  event.preventDefault();
  const target = go.dataset.go;
  if (target === "mode" && state.polling) return toast("A video is still being made.");
  if (target === "mode") resetFlow();
  show(target);
});

$$(".mode[data-platform]").forEach((card) => card.addEventListener("click", () => {
  state.platform = card.dataset.platform;
  $("#modeLabel").textContent = MODES[state.platform];
  $("#durationRow").hidden = state.platform !== "reel";
  if (!$("#videoName").value) $("#videoName").value = todayName();
  renderFiles();
  show("footage");
}));

function resetFlow() {
  state.platform = null;
  state.files = [];
  state.projectId = null;
  state.reviewRendered = false;
  $("#videoName").value = "";
  renderFiles();
}

// ---------- footage ----------
const drop = $("#drop");
["dragenter", "dragover"].forEach((name) => drop.addEventListener(name, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((name) => drop.addEventListener(name, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (e) => addFiles([...e.dataTransfer.files]));
$("#fileInput").addEventListener("change", (e) => { addFiles([...e.target.files]); e.target.value = ""; });
$("#reelDuration").addEventListener("input", (e) => { $("#reelDurationOut").textContent = `${e.target.value} s`; });

function addFiles(list) {
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
        entry.reason = found[1].reason;
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
      <span class="kind ${f.kind}">${KIND_LABEL[f.kind] || f.kind.toUpperCase()}</span>
      <span class="name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</span>
      <span class="state">${f.kind === "uploading" ? Math.round(f.progress * 100) + "%" : f.kind === "error" ? escapeHtml(f.error) : f.kind === "ignored" ? escapeHtml(f.reason || "not used") : "Ready"}</span>
      ${f.kind === "uploading" ? `<span class="bar"><i style="width:${Math.round(f.progress * 100)}%"></i></span>` : ""}
    </li>`).join("");
  const videos = state.files.filter((f) => f.kind === "video");
  const master = state.files.find((f) => f.kind === "master");
  let hint = "";
  let ready = videos.length > 0 && state.uploads === 0;
  if (state.platform === "youtube" && !master) { hint = "Stage needs a master audio file (WAV or MP3) to sync every camera."; ready = false; }
  if (state.platform === "reel" && !master && videos.length > 1) hint = "Tip: add the master audio so the reel cuts on the music.";
  if (state.uploads) hint = "Uploading…";
  $("#footageHint").textContent = hint;
  $("#makeIt").disabled = !ready;
}

function escapeHtml(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---------- making ----------
$("#makeIt").addEventListener("click", () => make().catch(fail));

async function make() {
  const name = $("#videoName").value.trim() || todayName();
  const platform = state.platform;
  const master = state.files.find((f) => f.kind === "master");
  const inputs = {
    master: master?.path || "",
    songs: state.files.find((f) => f.kind === "songs")?.path || "",
    videos: state.files.filter((f) => f.kind === "video").map((f) => f.path),
  };
  state.reviewRendered = false;
  setProgress(0, "Getting your footage ready…", "");
  show("making");

  await api("/wizard/projects/new", {});
  const draft = await api("/wizard/draft", { name, project_id: null, platform, audio_paths: master ? [master.path] : [], ...inputs });
  state.projectId = draft.project_id;

  if (platform === "youtube") {
    await api("/wizard/prepare", { name, platform, project_id: state.projectId, ...inputs });
    await waitFor((s) => ["waiting_choice", "done"].includes(s.status));
  }
  await api("/wizard/start", {
    project_id: state.projectId, name, platform, ...inputs,
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
      if (s.status === "waiting_review" && !state.reviewRendered) {
        // Montara is fully automatic: accept the proposed shots.
        state.reviewRendered = true;
        await api("/wizard/review/render", {});
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

function stopPolling() { clearInterval(state.polling); state.polling = null; }

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

show("home");
