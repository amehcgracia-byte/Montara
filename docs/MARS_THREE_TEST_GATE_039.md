# Mars gate — three tests before integration (2026-10-27)

**Decision: proceed to an integrated prototype, not to production.** The three isolated CPU checks establish a sound direction but do not certify browser-to-editor integration.

## A. Audio/video timestamp preservation

Executed FFmpeg H.264/AAC synthetic 4-second source and generated proxy using the options in Montara's local proxy generator.
- Video: first/last offset = 0/0 ms; 120 original and proxy frames.
- Audio: first/last offset = 0/0 ms; 188 original and proxy decoded frames.
- Measured drift between endpoints: **0 ms** for video and audio.

Boundaries: this is CFR with a sine-wave audio track, not a 30-minute concert, real camera offsets, VFR with audio drift, or lost packets. Earlier B05 tests established that non-zero original PTS start may be normalized to zero; that mapping remains important.

Repro: `python experiments/media_optimization/benchmark_b06_av_pts.py`.

## B. Concurrent proxy generation

Two simultaneous calls using the source-equivalent UUID-temporary implementation and the same cold-cache 4-second 640×360 input returned the same source ID. Instrumentation counted **two FFmpeg transcodes** rather than one.

Interpretation: unique temporary output names prevent collisions but do not eliminate duplicate CPU work. A per-source cross-process lock followed by a fresh cache check is warranted before large original files or many jobs. Do not advertise single-flight caching yet.

## C. Proxy recipe → original source → final render

An isolated local test generated a video, prepared its proxy, selected two nominally one-second cuts through `resolve_recipe`, then rendered the cuts with FFmpeg from the untouched original.

- Nominal output: 2.000 s.
- Actual MP4: **1.958333 s**, about one 24-fps frame short.
- Export file: **411,550 bytes**.
- Resolution step referenced the source original, not the proxy.

The 1-frame difference is consistent with exclusive trim boundaries/MP4 timestamp handling in this synthetic example; it is **not proof of perfect edit-point or audio synchronization**. The newly committed `benchmark_b07_original_export.py` reproduces the smoke check. The editor GUI, user file upload, preview, sound mixer, playback seeking and complete user journey have **not** been run end to end by this experiment.

## Readiness checklist for next phase

1. Implement an **integrated preview path** with explicit source timestamp transformation; keep originals for final render.
2. Add source-specific single-flight proxy creation to avoid duplicate transcoding.
3. Compare frame-exact cut points and AAC event timing for full browser/edit/export journeys.
4. Run all branch regression tests on Linux/macOS CI before opening a non-draft PR to owner main.
5. Benchmark user workflow: first load, second load, change/edit, preview, export, peak disk, elapsed time and quality. Compare same material with/without cache.

**Only the experiments were run in the assistant's disposable CPU environment**. The exact remote branch has not completed GitHub CI. No `main`, deployments, GPU credits or engine submodules were changed.
