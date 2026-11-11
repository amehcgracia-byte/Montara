# SMART — Real media diagnosis, Chema intro and Engine indicator (11-11-2026)

## Feedback received
Fernando reported Stage with Companion connected; video proxy at 89% uploading, MP3 `4._Minor_7th.mp3` errored as `Upload failed`, and a second resumable record displayed `Upload paused`. The beta's original JM message still claimed final video from small proxies. Trying `Close idle Engine` gave `Project status is not verified. Nothing has been stopped`. Asked for a small red/green vintage Engine switch by Account, restoration of **Chema's actual original logo clip**, and retention of the separate preview site (unchanged).

## What was actually verified
- Service portal, Cloudflare tunnel, broker active. No automatic worker stop or project mutation.
- Real pinned JM video `#home .intro-name` with original SVG bars and 7 characters, and its CSS `intro-assemble`/`intro-bars`, are already used by authenticated entry. Their animations needed restarting when revisiting Home. `owner_mode_entry.py` now recreates the SAME original DOM from an immutable in-tab copy on every Home visit; no video file generated or substituted. All preview assets untouched.
- `owner_original_jm_rpc.py` accepted synthetic MP3 in mocked trusted-worker test, and an additional **native real Engine sandbox** under system Python 3.11 with immutable JM `14cce126` and pinned Engine `b867b3c` accepted `4._Minor_7th.mp3` with HTTP 200, classified as `master`. Sandbox contained only FFmpeg-generated sine audio in temporary directory; no user files, root worker or production SQLite involved. Therefore MP3 as a format is **not** the root issue.
- Actual Chrome→Cloudflare→Owner authenticated upload failure in Fernando's session was **not reproduced or explained** by backend-only tests. The likely investigation layer is XHR browser authorization/transport or user-specific response. We must not claim the actual file uploaded.
- Before change, some Owner JSON error responses were bare strings whereas Chema's XHR expects `error.message`, resulting in generic `Upload failed`. The async XHR admission adapter also swallowed ensure errors via `abort()`, making them opaque.
- Previously diagnosed Engine status requires verified generation and private CSRF; absence of those results in HTTP 409/403 and the previous close failure. The beta switch uses the exact Owner UUID and checks HTTP status before closing.

## Changes deployed in fernando/integracion
1. `urano/owner_original_jm_rpc.py`: only for failed upload requests, normalizes `error: "reason"` to `error: {message:"reason"}` for original Chema XHR. Does not touch successful or streaming media bodies.
2. `urano/owner_browser_bridge.js`: reports failed XHR admission and server 4xx/5xx inline in persistent Footage `role=alert`, rather than silently aborting. Emits `montara-owner-engine-ready` only after broker-verified `ensure`. Still never uploads original video without consent.
3. `urano/owner_project_picker.js` + `.css`: small Engine LED/switch immediately before Account in the original editor header, vintage style. **Green only after verified worker admission; red only after confirmed close; amber when not yet checked/busy**, avoiding false OFF. Switch On uses owner-scoped ensure; switch Off is explicit and gated by ensure + verified generation + authenticated status exactly `idle` + human confirm + Owner's already-proven close endpoint. On errors displays reason without claiming state. This is **beta diagnostics**, not atomic multi-tab safe final switch. Do not use it to stop active renders.
4. `urano/owner_mode_entry.py`: Home uses exact original Chema HTML/SVG/CSS and restarts its animation on revisit.
5. `urano/original_jm_owner_assets.py`: Owner-only replacement of obsolete `Companion ... final video made from small versions` claim with accurate proxy workflow; original Chema source remains untouched. Actual local final export requires Companion/native rendering working.
6. `tests/test_urano_owner_original_jm_rpc.py`, `tests/test_owner_navigation_consistency.py`: synthetic MP3 acceptance, error structure, exact intro, current Companion wording, protected Engine switch.

## Verification
- Consolidated **70 Python PASS, 2 skipped, 71 subtests PASS; 11 Node PASS**, syntax/compile PASS. Two skipped tests not counted as successful.
- Isolated original JM+Engine MP3 200, master classification PASS as above.
- Rollback copy at `~/.config/montara-owner-beta/rollback-engine-led-upload-diagnostics-20261111/`. Portal HTTPS /healthz 200; visitor entry 401; visitor picker 401; Google start 302. Portal, tunnel and broker active.
- The previously verified Windows native 1080p MP4 from local sources remains valid only for pinned older Engine `b867b3c`, NOT proof of E2E from Owner website.
- **No browser-human new upload successful yet**, no new Engine main 92c7bc3 deployed, no permanent local original paths exposed to cloud.
- Preview website not touched, no edits to Chema main, no user uploads/originals manipulated.

## What is still blocking real Stage
- Identify exact browser HTTP or admission failure on a future upload using now-persistent error message; do not ask user to repeat tests or upload originals immediately.
- Verify browser direct proxy transfer through Cloudflare and Companion local final MP4. If a media-size/quota/CSRF error appears, fix that contract concretely with an isolated reproduction.
- True Engine ON/OFF read-only status requires a broker query that **does not start** worker; do not infer from page load. Current switch is explicit-only and tri-state. Production shutdown must fence new starts atomically at broker before stop, across tabs.
- Main Engine `92c7bc3` is 39 commits past pinned `b867b3c`, with changes to shot review, export, tracking. No blind migration.
- Do not replace Chema's native animations or preview.
