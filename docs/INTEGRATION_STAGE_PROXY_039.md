# Integration 03 — Stage camera source preview (experimental)

Implemented on `fernando/continuacion-montara`, 2026-10-27.

## User path

With `MONTARA_EXPERIMENTAL_PROXY_PREVIEW=1` on a local Flask server, Stage's **Cameras** screen probes `GET /montara/local-preview/availability` and adds a **Cached preview (experimental)** button to each camera. Clicking the button starts a background proxy-preparation job; Stage polls until complete and displays **Play cached proxy**, a normal link opening a local HTML5 player in a new tab.

Preparation uses `local_media.proxies.prepare`: caches persist in `MONTARA_DATA/LocalProxyCache`, and concurrent cold requests to the same source use the previous POSIX single-flight lock. Browser playback uses the proxy. Stage's original `state.files`, camera assignments, edit recipe and export endpoints are **not replaced**.

This integration is deliberately additive, not a wholesale refactor of Stage.

## Constraints and correct expectations

- Works only through loopback on the **same computer as Flask**. The server accepts camera paths only under `MONTARA_DATA`, with supported video suffixes. Browser-local files not uploaded to MontaraData and bundled fixture files outside it will be refused.
- Disabled unless `MONTARA_EXPERIMENTAL_PROXY_PREVIEW=1`. Windows is unsupported for cold generation because the current single-flight lock uses POSIX `fcntl`.
- Slow transcodes may take a long time; the browser polls up to 120 seconds and then invites a retry. Server-side jobs continue.
- This is **camera preview on the Cameras screen**, not yet automatic proxy playback in Stage's shot/timeline editor; user can compare visual quality manually. Original export remains unchanged.
- Proxy jobs are tracked in memory; restarting Flask discards pending statuses, though the underlying cached proxy can persist when completed.
- A localhost-based feature flag is not an authentication system or a safe public deployment. Do not enable the prototype on a publicly exposed service or proxy forwarded to external users.
- No model-generated media, GPU, additional cloud resources, deployments, or `main` changes.

## How to try

```bash
export MONTARA_EXPERIMENTAL_PROXY_PREVIEW=1
python app.py --host 127.0.0.1 --port 8080 --data "$HOME/MontaraData"
```

Open `http://127.0.0.1:8080`, select Stage, register an uploaded camera video inside MontaraData and continue to **Cameras**. The experimental button appears only when the feature is available. Click it to prepare a proxy; use **Play cached proxy** to view it.

## Regression scope

Added `tests/test_stage_proxy_preview.py` for asynchronous preparation, availability, rejection of non-MontaraData paths and non-local clients.

```bash
python -m pytest tests/test_stage_proxy_preview.py tests/test_local_proxy_preview.py tests/test_proxy_singleflight.py tests/test_local_proxies.py -q
```

The source and tests are committed but **have not yet been run end-to-end in a real Stage browser session or certified in CI**. The next milestone is to instrument and test **automatic source switching inside the actual editor timeline**, preserving original-backed exports and accurate audio synchronization. A browser end-to-end test is mandatory before considering it done.
