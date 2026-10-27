# Montara architecture checkpoint — the five-hour folder test

Status: **architecture acceptance criteria and first zero-copy inventory benchmark**, not a completed browser-to-desktop integration.

## The user goal

A browser-first video editor should let a person select a working folder, organize footage and audio into projects, analyze and preview efficiently, repeat edits without redoing work, and export full quality. A 10-minute project and a 5-hour project should use the **same product flow**, adjusting computation rather than exposing more buttons.

## Technical boundary

A browser File System Access API picker may provide user-granted file/directory handles on supporting desktop browsers, but it **cannot grant a remote Python server access to the local path**. A cloud Flask server cannot resolve browser-local disk paths merely because a picker was opened. A normal web upload transmits bytes; an optional local processor would need separate implementation and installation/permissions. WebCodecs/WebGPU/browser-only processing is another approach with significant implementation and format restrictions.

Do not promise 800 GB direct local/cloud rendering or unrestricted local disk access with the current server architecture. Verify supported browsers, available disk and transfer budgets before choosing a UX.

## Minimal two-lane proof, not two apps

- **Lane A — browser/local:** a user-approved folder inventory, no original media copied by default; browser-supported metadata, thumbnails/proxies and persistence where feasible.
- **Lane B — cloud/heavy:** transfer only authorized assets needed for an operation; an isolated worker uses FFmpeg; final exports use original-quality media at the location capable of accessing it.
- Both lanes should share stable source IDs, clip ranges, scene timestamps and edit recipes. Do not duplicate the editor or its processing rules.

## B08: first measurable baseline

`experiments/media_optimization/benchmark_b08_folder.py` scans the media structure of a local folder **without reading video payloads, transcoding or copying any originals**. It records file counts, logical original bytes, number of ignored entries, filesystem-stat failures and elapsed inventory time. It does not yet derive duration, audio latency, codec, GOP or seek performance.

```bash
python experiments/media_optimization/benchmark_b08_folder.py /path/to/approved-folder \
  --output /tmp/montara-b08-inventory.json
python -m pytest tests/test_benchmark_b08_folder.py -q
```

Tests cover counting original bytes without copies, refusing linked external folders/files, and a bounded file count. **Tests were committed but are not represented as passing without a real run**.

### Benchmark ledger convention

Keep the benchmark scripts and compact JSON/CSV measurements in the repo only when non-sensitive. Record `date`, `commit`, `OS`, `CPU`, `RAM`, `storage`, `FFmpeg version`, `file count`, `resolution`, `duration`, `bytes`, `first-run`, `warm-run`, `output quality` and `failure`. Synthetic tests are clearly separated from concert footage. Prefer one consolidated comparison per phase, not many verbose reports.

## Next acceptance gates

1. **Folder UX:** select a real folder in a supported browser, index it without bulk upload, create/reopen a project, and explain browser constraints.
2. **Scale:** benchmark 10 min, 60 min and 5 hours, with at least two cameras and separate audio; compare metadata scan, proxy generation, preview first frame, seeks, warm reopen, footprint and CPU.
3. **Edit:** make several changes, show that cached information is reused, measure edits/reviews, maintain timestamps and confidence for source alignment.
4. **Render:** verify a full-quality export using untouched originals, including audio/video synchronization and frame-level validation.
5. **Architecture decision:** only after those figures, select browser-only local capability, an optional local worker, remote server/GPU, or a hybrid. Do not force a native agent on users prematurely.

### Caution from earlier experiments

The current `local_media.session_proxies` expects **server-accessible absolute paths**. The optional Stage proxy button also expects files under the server's data root. Neither is a true browser-local folder solution. Both remain experimental and off by default. Stop adding new controls until the main folder flow and its architecture decision are validated.

No changes to main, deployment, Oracle, RunPod or Zucker submodule pins.
