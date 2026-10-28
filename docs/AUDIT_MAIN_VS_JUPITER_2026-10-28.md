# AUDIT 2026-10-28: main versus Jupiter browser-local experiments

Scope: static read of repository `main` and existing documentation; no Python/browser integration tests executed during this audit. Branch for this report: `fernando/continuacion-montara`. No changes to main, production, or submodules.

## Confirmed existing capabilities
1. Shared edits: `web/cut-editor.js` begins "All edit modes use the same boundary control"; exposes timeline editing, exact frame-rounded edits, split/remove/roll and shot framing. However `docs/audit/PARIDAD_EDITOR_MIXER.md` explicitly marks split/ripple-delete **partial** across Stage/Push/Show (Show single-source most complete). Do not assume feature parity.
2. Shared UI: `web/compact-editor.js` provides compact playback controls; `scheduleShowAutoPreview` asynchronously requests rendered scene preview and continues allowing edits. UI-level cache `showPlaybackState.cache` exists; not proof of automatic background export for all modes.
3. Stage: `web/montara.js` renders shots/thumbnails, hover videos, swap camera and shot edit; `/wizard/review?render=...` and `/wizard/review/render` are backend endpoints. `docs/VALIDATION_038.md` documents Stage, Push and Mixer+Stage completed render journeys (export VIDEO durations, NOT measured export time).
4. Persistence: `app.py` line ~87 restores a previous engine `project.json` path under configured data root. `web/full-session.js` keeps session ID in browser localStorage; `full_session.py` maintains on-disk session manifests, cancellation and status, with POSIX `fcntl` locks and worker checks. `docs/PLAYHEAD_033.md` describes sandbox preview session resume; session storage is backend, not user's browser folder.
5. Uploads: `web/montara.js` uploads media to `/api/v1/wizard/upload`, or resumable chunks when file >8 MiB; `resumable_upload.py` writes incoming source parts to SERVER filesystem, with 256 MiB/file preview limit and up to 30 GiB outside restricted previews, conditional on storage. This is not local-zero-upload workflow.
6. Cache: `source_cache.py` reuses previously downloaded/imported sources; `show_playback.py` creates hashed segment-based preview files with FFmpeg via a background thread on the SERVER and stores them under backend data root. The repository `local_media/proxies.py` is experimental and docs say it is not integrated with browser local handles/editor.
7. Deployment: `docs/HANDOFF_FERNANDO_038.md` and `deploy/sandbox_entry.py` identify isolated Vercel Sandbox with server-side storage/snapshots; public web is NOT a browser-only video engine. `.gitmodules` points to separate Zucker Video engine and ZuckerMixer source repositories; their full implementations are not inside the Montara parent tree.
8. Prior audit: `docs/audit/PARIDAD_EDITOR_MIXER.md` already catalogs many parity gaps; `docs/PRE_ABACUS_2026-10-27.md` (latest located in main) reports CI 40517716811 with 115 Python tests + 6 preview cycle tests and rendered Stage/Push/Mix/Session journeys; this is source-documented, not rerun here. That report explicitly calls local-proxy browser integration and multi-song video exports pending.

## Major implications
- User's suspicion of shared cuts, caches and background previews is substantially supported; avoid reinventing Stage/Show cut UI and server render scheduling.
- **Core gap** for desired new browser folder UX: current production app expects originals uploaded or otherwise accessible to backend. A browser-approved local directory neither makes local originals visible to Vercel Sandbox nor lets browser JS directly call host-installed FFmpeg.
- Jupiter-01 user confirmed Chrome access to 3 nested local MP4s, playback and persisted non-destructive in/out metadata. Jupiter-02 user reports subfolder creation and ability to save a JSON recipe, but full JSON read-after-restart and denied-permission tests remain to be verified. These experiments should become an INPUT/PERSISTENCE ADAPTER, not another editor.
- Need design source IDs and local/remote media resolver for **existing engine's** timeline/render contract. Test existing engine recipe compatibility and support for absent/removable local media. Keep UI minimal.
- GPU or cloud option only after measuring upload + server compute + output download versus local processing; large source transfers can dominate.
- Windows portability: `full_session.py` and `resumable_upload.py` use POSIX fcntl, unsuitable for native Windows execution without adaptation; server Linux unaffected. Browser-only mode would not run these Python components anyway.

## Prioritized validation (no speculative implementation)
1. Identify concrete engine routes, serialized edit recipe format and project storage location from ZuckerVideos submodule pinned SHA; trace `/api/v1/wizard/review/render`, `/edit/timeline`, `/show/scenes/.../preview` end-to-end.
2. Trace backend data directories and retention in preview sandbox, including source cache and session; check actual main implementation versus older design docs.
3. Draft folder-backed media adapter: relative path/file handle in browser + browser object URLs + stable IDs, without granting backend magical local access.
4. Test playback sequential cuts with existing timeline structures; measure hand-off latency and seek accuracy, beyond simple isolated browser lab.
5. Test export of same recipe with original media: browser-only supported formats vs optional local worker vs explicitly uploaded remote media.
6. Benchmark real media, 10min/1h/5h only with meaningful original size; check disk/CPU/RAM, A/V sync, final fidelity; do not mistake export duration for elapsed processing time.

## Main files examined
`web/cut-editor.js`, `web/compact-editor.js`, `web/montara.js`, `web/show-editor.js`, `web/show-live.js`, `web/full-session.js`, `source_cache.py`, `show_playback.py`, `show_cut_edit.py`, `show_editor_state.py`, `full_session.py`, `resumable_upload.py`, `app.py`, `deploy/sandbox_entry.py`, `deploy/preview_storage.py`, `docs/audit/PARIDAD_EDITOR_MIXER.md`, `docs/PRE_ABACUS_2026-10-27.md`, `docs/VALIDATION_038.md`, `docs/PLAYHEAD_033.md`, `docs/TIMELINE_032.md`, `docs/HANDOFF_FERNANDO_038.md`, `.gitmodules`.
