# Montara performance baseline: reproducible experiment plan

**Status:** protocol only; no performance measurements have been run or claimed.
**Branch:** `fernando/continuacion-montara`.

## Principles

1. Compare all methods against the **same source files, hardware and output fidelity**.
2. Measure separately: ingest, metadata probing, proxy generation, waveform/audio sync, visual sampling, selection, render, transfer and export.
3. Record peak RSS, CPU time, GPU utilisation if available, input bytes, output bytes, read/write bytes, elapsed wall time and errors. For remote work distinguish user upload, object-store egress and GPU download.
4. Keep personally identifying/copyrighted source material out of Git; commit only generator scripts, manifests, timings, anonymised aggregates and tiny licensed fixtures.
5. **Ground truth:** manually identify significant cuts or notable visual moments on unseen clips. Measure precision/recall of sampled detections, and compare against full-frame or dense baseline. Never confuse compression factor with detection quality.
6. At least 3 independent runs after one warm-up; record cold-cache separately; publish median and range.
7. Avoid changing the Mixer or Editor submodule pins in benchmarking experiments. Fork experiment branches and PR only measurable improvements.

## Experiments and questions

| ID | Experiment | Baseline | Candidates | Success criteria |
| --- | --- | --- | --- | --- |
| B01 | Probe and index | ffprobe for all originals | metadata cache, content fingerprint | Same metadata and reduced repeat elapsed time |
| B02 | Generate proxies | current FFmpeg proxy | tuned H.264 encoders, scale/fps/bitrate | Timestamp/frame parity, acceptable edit preview, bytes and time |
| B03 | Music-centric alignment | existing synchronisation engine | audio envelope/cross-correlation before image analysis | Matching offsets within frame tolerance on manually checked media |
| B04 | Select frames | fixed frames-per-second | shot-boundary and motion-guided adaptive sampling | Equal/better human-labeled detection recall with fewer decoded/uploaded frames |
| B05 | Video rendering | current FFmpeg CPU workflow | NVENC/NVDEC GPU when available; cached partial renders | Visual/audio equivalence, accurate timing and lower total cost |
| B06 | Mixed network | full original transfer | proxies + audio + selected original segments | Same final output quality and fewer user-upload/object-store-egress bytes |

## Realistic corpus

- Small (under 1 GB): short 1080p synthetic and licensed tests; runnable in CI.
- Medium (5–20 GB): realistic multi-camera and multi-track 1080p test, local/temporary runner.
- Large (100–800 GB): real jam/concert dataset **off GitHub**, after limits, storage and GPU are explicitly approved.
- Include varying FPS/VFR, rotation, audio drift, silent mic, different stem lengths and concurrent voices.
- CPU-only runner first. Dedicated GPU experiments only after the CPU baseline is reproducible.

## Suggested first run

1. Verify that `python -m pytest tests/test_mixer_source_access.py -q` passes, followed by the documented regression suite.
2. Produce a synthetic licensed ~60 second clip with deterministic FFmpeg settings and an accompanying scene-change ground-truth CSV.
3. Benchmark current scene/frame selection against a fixed sampling baseline, and keep a JSON result schema with input SHA-256, command/tool version, CPU, RAM, elapsed, byte counts and precision/recall.
4. Do not claim paper-level percentage savings until Montara's own data demonstrates them.

## Deployment and pricing constraints

- Prefer free local CPU or GitHub Actions within available minutes; keep sample files small.
- No automatic Vercel deployments, GPU subscriptions, bucket provisioning or Cloud compute changes.
- `main` is owner-controlled; work only on the Fernando branch or smaller experimental branches.
