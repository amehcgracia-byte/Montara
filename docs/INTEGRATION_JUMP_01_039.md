# Integration jump 01 — persistent proxies for a Montara session

Date: 2026-10-27. Branch: `fernando/continuacion-montara`.

## Implemented

1. `local_media/proxies.py`: single-flight cold cache preparation on POSIX using an advisory per-source `flock` lock. Checks cache before waiting and rechecks after acquiring lock, so the second request can reuse the completed first result instead of transcoding twice. Retains original proxy key, compression settings, signature and recipe contract. The unique temporary filenames remain as a defensive measure.
2. `local_media/session_proxies.py`: bridge for a private **session source manifest**. It uses existing `prepare()` for each original and outputs public-only source IDs and proxy descriptors. Original paths remain in private cache records, and `resolve_recipe()` still resolves final cuts to originals.
3. `tests/test_proxy_singleflight.py`: tests concurrent cold generation invokes FFmpeg exactly once, plus warm cache hits avoid locking.
4. `tests/test_session_proxies.py`: tests public metadata excludes originals and duplicate source entries are rejected.

## Usage: local experimental bridge

```bash
# sources.json holds a JSON list of paths on the same computer/server.
python -m local_media.session_proxies sources.json \
  --cache /tmp/montara-session-cache \
  --output /tmp/montara-session-public.json
```

Only share the public manifest; `sources.json` and `*.local.json` contain private local paths. The prototype currently performs proxy generation synchronously. It is **not** yet connected to the Stage/Show/Push web GUI or background worker, and not a browser-to-desktop folder integration. Do not expose this function directly to arbitrary public HTTP paths.

## Scope limitations and integration checklist

- The locking implementation explicitly supports POSIX/Linux/macOS. Windows needs a tested equivalent before being supported, rather than silently running without protection.
- A process crash releases `flock`; residual lock files are harmless. A single long-running generation intentionally blocks other clients waiting for the same source. Async status/progress and cancellation must be added for the web experience.
- Existing private proxy cache manifests are still written with `write_text`, not atomic replace; evaluate crash-safe manifests before production.
- No real media playback, waveform display, browser edit session, UX or human-rated output-quality test has passed as part of this change.
- Tests have been committed, but **GitHub CI for the exact branch changes has not yet been observed**. No claims of full regression-pass or production readiness.
- `main`, Zucker submodules, stable Vercel alias, Oracle and RunPod are untouched.

## Next measurable stage

Use the bridge in a test edit session with 2 cameras and one audio master, measure first load / warm load / waveform and thumbnail extraction, then thread generated `source_id` into a minimal Stage preview. Add frame-accurate cut validation and a browser end-to-end test before merging.
