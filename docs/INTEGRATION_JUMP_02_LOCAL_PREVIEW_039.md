# Integration milestone 02 — local proxy browser playback

**Branch:** `fernando/continuacion-montara` | **Status:** experimental, local-only, not yet a Stage/Show/Push GUI integration.

## What is actually implemented

- An opt-in HTTP bridge in `local_media/preview_http.py` serves only existing **prepared proxies** at `/montara/local-preview/<source_id>/video`.
- The endpoint checks source IDs, the associated private cache manifest, the original file stamp, proxy existence and the bounded proxy signature. It never accepts arbitrary filesystem paths from URL parameters.
- A `/metadata` endpoint returns only the public descriptor. A `/view` endpoint provides a simple HTML5 video player so an actual browser can stream a proxy.
- The bridge is registered by `app.py` only when `MONTARA_EXPERIMENTAL_PROXY_PREVIEW=1`, and rejects non-loopback clients. **Never expose this optional prototype through a reverse proxy to the public Internet.**
- `local_media/session_proxies.py` prepares multi-video manifests with the existing local cache, preserving the mapping to original media for rendering.
- The cold-cache single-flight optimization remains Linux/macOS POSIX-only.

## Reproducible local demonstration

Create `sources.json` with an array of absolute paths to two videos available on the same machine as Montara. They stay outside the repository. From the repository root:

```bash
python -m local_media.session_proxies sources.json \
  --cache "$HOME/MontaraData/LocalProxyCache" \
  --output /tmp/montara-session-public.json

MONTARA_EXPERIMENTAL_PROXY_PREVIEW=1 \
  python app.py --host 127.0.0.1 --port 8080 \
  --data "$HOME/MontaraData"
```

Read the `source_id` from the public JSON file and navigate to:

```
http://127.0.0.1:8080/montara/local-preview/SOURCE_ID/view
```

The browser should request the MP4 from `/video`; HTTP range requests are handled by Flask's conditional file response. The original is not used by this preview endpoint and remains available through `resolve_recipe()` for export.

## Tests and constraints

```bash
python -m pytest tests/test_local_proxy_preview.py \
  tests/test_proxy_singleflight.py tests/test_session_proxies.py \
  tests/test_proxy_cache_fastpath.py tests/test_local_proxies.py -q
```

**These tests have been committed but have not been observed passing on the remote branch yet.** The HTTP page is a bridge smoke-test, not actual editing: Stage timeline interaction, multitrack sync, Web UI project state, upload registration, export with audio and cross-platform support are pending.

## Next incremental deliverable

Connect the editor's preview source selection to these registered proxy IDs, while the output recipe continues to reference originals. Measure cold/warm UI load times, preview seeks, cache footprint, CPU and final-frame accuracy on two cameras plus master audio. No GPU or infrastructure spend until this user journey passes.
