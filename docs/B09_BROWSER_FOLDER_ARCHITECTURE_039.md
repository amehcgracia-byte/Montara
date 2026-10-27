# Folder architecture proof — B09 browser-local folder selection

Date: 2026-10-27. Branch: `fernando/continuacion-montara`.

## Delivered

- `web/folder-lab.html` + `web/folder-lab.js`: standalone architecture lab, **not a modification of Stage**.
- Desktop user explicitly chooses a folder through `showDirectoryPicker({mode:'read'})`; a selected directory handle is saved in this browser's IndexedDB.
- Local recursive inventory counts video/audio files and total logical byte sizes using `getFile().size`. It never reads media payloads via `arrayBuffer`, `stream` or remote `fetch`.
- A separate action reopens the handle if the browser grants or renews permission. A forget action deletes the saved handle.
- The lab measures client-side elapsed inventory time with `performance.now()`, records `bytes_uploaded: 0`, and makes no claim of proxy/render speed improvements.
- It is a **standalone page for experiments** so production editing UX does not gain unrelated buttons.
- Flask static assets are served from `web/`, so a local server should expose `/folder-lab.html`.

## How to try

Run Montara in its existing local developer configuration (see repo README), open `http://127.0.0.1:8080/folder-lab.html` if Flask uses port 8080, and pick a video/audio folder in a compatible desktop browser. Chrome/Chromium-derived browsers are generally the most relevant starting point; feature-checking is performed before invoking the API. Reopen the page and use **Reopen saved folder**, allowing a permission prompt if needed.

Suggested five-minute checks:
1. Folder of multiple 10-minute recordings + audio: note count, elapsed time, zero uploads.
2. Refresh: reopen stored handle; no upload.
3. Folder with 5-hour recordings: inventory should require no media decoding and memory should not scale with the file byte size (but still scales with number of files/handles).
4. Deny permission or use unsupported browser: clear message, no background scanning.

## What this does NOT prove

- Browser access to local FFmpeg: **not available** through the folder picker.
- Persistent handles in all browsers: not guaranteed; permission may expire or be revoked.
- Video duration, codecs, sync, proxy generation, re-edit, browser playback or 5-hour render: **not measured**.
- Folder selection on cloud server grants the server access to user disk: **false**.
- User media privacy is an explicit principle; this proof only reads local file metadata.
- The new JS is committed but has **not yet been exercised in an interactive browser or a CI browser automation**. No fabricated 5-hour performance figures.

## Benchmark policy

Keep code and reproducible tests. Publish one compact results summary per architecture gate, not a separate ceremony for every microbenchmark. Collect 10 min / 1 hr / 5 hr on identical hardware and note file count, bytes, inventory time, memory, permission/reopen behavior and network requests. Treat proxy preparation, waveform/sync and export as separate phases. Never claim end-to-end success from metadata-only inventory.

## Practical deployment decision

Docker is a **packaging and reproducibility tool**, not a server or a browser disk-access bridge. Oracle Free Tier may host a low-cost coordinating API, but does not give that API permission to read local user videos. Abacus/RunPod/GPU are relevant only after profiling work that can actually benefit from remote compute. Avoid moving GB/TB of video without a measured reason.

Next gate: wire browser-selected handles into a stable local project index (without uploads) and measure seek/frame decode & thumbnail/proxy strategies in a controlled worker environment, then the actual editor recipe+export.
