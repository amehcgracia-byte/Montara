# JUPITER-02: browser folder read/write project persistence (experimental)

Branch: `fernando/continuacion-montara`. **Do not merge or deploy to main automatically.**

## Files
- `web/jupiter-02.html` and `web/jupiter-02.js`: separate browser-only lab, not connected to Stage.
- User chooses an existing local folder in Chrome/Edge via `showDirectoryPicker({mode:"read"})`. Video enumeration descends into subdirectories, excluding the dedicated top-level `Montara` folder; a selected file is played using `URL.createObjectURL(file)`, not uploaded.
- IndexedDB stores the browser folder handle. The user manually selects **Recuperar carpeta** after refresh, with browser permission renewal as required.
- User authorizes `readwrite` separately. On **Guardar**, the script creates `Montara/proyecto-jupiter02.json` with a small declarative project recipe: relative source names and clip start/end seconds. Read and restore via **Recuperar proyecto del disco**.
- The app refuses to overwrite an existing file lacking the laboratory's `app` marker. No application code opens existing videos for writing. Keep originals read-only by policy even though directory write permissions technically allow broader access.
- If a recognized laboratory project already exists, saving intentionally replaces its recipe. This is an experiment, NOT an atomic project save/backup strategy.
- The UI does NOT encode/export video, generate proxies, invoke user's FFmpeg, or do background pre-rendering.

## Browser smoke test (NOT executed/verified by assistant)
Use an HTTPS test deployment serving both files in the same `web/` directory, or a minimal local static server. Chromium desktop, `localhost` or HTTPS required. Select a test folder with video (avoid sensitive originals), mark cut, authorize write, save. Verify the file appears in dedicated `Montara/` subdirectory, refresh, click reopen, reload JSON. Optionally deny permission and confirm no write. Never test destructive overwrite on originals. The standalone experiment needs no app-specific Python dependencies; Python HTTP server was used only by the *earlier local lab*.

## Proven user-reported Jupiter-01 precursor
On Windows 10 Pro, i5-6300U, 8GiB RAM, Chrome, user used independent `localhost:8765` HTML lab to discover 3 nested MP4s, play audio/video smoothly, save a clip for the second tutorial from 637.418s to 653.345s, retain cuts after F5; manually reopened folder. No original uploaded or modified. This experiment is not proof of Stage integration.

## Earlier FFmpeg measurements, separate independent experiments
- FFmpeg 9.0.1; video: 1280x720 H.264/AAC, 29.97fps; Tutorial 2 duration 835.384s and source 41.48MiB.
- 30s decode 1.848s; 30s 640px ultrafast/CRF28 proxy 2.672s / 3.58MiB. Full-file proxy 63.509s / 73.72MiB, **larger than original**. User saw modestly reduced image quality and perceived audio-video sync.
- These figures are from FFmpeg alone, one-run, and must NOT be labeled Montara performance or production browser benchmarks. Simple stat-based checks were not real Montara warm-cache measurements.

## Architecture decisions still open
Browser readwrite permission allows a website to save files through supported browser APIs; it does NOT permit remote Python or FFmpeg servers to access local originals or allow a website to launch an installed FFmpeg binary.
Default architecture hypothesis: originals local; small edit recipes local with optional cloud sync; regenerable proxies/thumbnails/audio waveforms local unless a cloud worker has a measured advantage; exports written to user-selected destination when the exporting engine can access it. Cloud GPU needs explicit input transfer and total-time/cost/quality benchmarks. Browser-only render capabilities depend on codecs/browser APIs. No promise of a 60x remote render improvement.

## Next gates
1. Manually browser-test Jupiter-02 on Windows and validate write denial, project persistence and non-overwrite of originals.
2. Inspect cousin's real Stage prerebder/background job architecture and avoid duplicating it.
3. Test sequenced local multi-clip preview and the actual Stage integration using matching engine recipes; measure seeks and smoothness.
4. Validate original-quality export (possibly optional native worker), with sync/frame-level verification.
