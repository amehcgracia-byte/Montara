# External research radar — Montara architecture/performance (2026-10-28)

This catalog is **research input**, not authorization to vendor/clone/reimplement libraries. Follow up with primary papers, source compatibility/license review, isolated benchmarks and comparison against pinned ZuckerVideos and ZuckerMixer code.

## Reuse what humans have built first
| Domain | Reference | External evidence | Specific Montara question |
|---|---|---|---|
| Video transcoding | https://github.com/FFmpeg/FFmpeg (65k+ stars, observed October 2026) | Broad maintained encoding/probing framework | Can existing FFmpeg pipeline choose proxy strategy based on input bitrate and intended preview/seek? |
| Computer vision | https://github.com/opencv/opencv (90k+ stars) | Established computer vision framework | Are existing shot detection/framing algorithms already using equivalent primitives? Avoid injecting a full dependency for a small feature. |
| Source media retrieval | https://github.com/yt-dlp/yt-dlp (far above 50k stars) | Robust extractor/downloader with caveats about remote providers and terms | Does Montara already use it? What improvements in error handling/recovery are useful without bypassing site verification? |
| Subjective-quality proxy metrics | https://github.com/Netflix/vmaf (below 50k stars but technical reference) and https://github.com/Netflix/vmaf/blob/master/resource/doc/references.md | VMAF combines perceptual signals; VMAF models v1 released June 2026 | For equal-quality A/B, evaluate at matched res, framerate and aligned frames. VMAF must not be used in isolation, especially for reframed 360 and effects. |
| Caching/compute graphs | https://bazel.googlesource.com/bazel/+/refs/heads/error-details/site/docs/remote-caching.md and https://doc.dvc.org/user-guide/pipelines/defining-pipelines | Build/action cache and CAS keyed by declared inputs; DVC caches stages with parameter-aware invalidation | Compare existing preview keys (path, size, mtime, cuts, codec version) to declared upstream dependencies. Measure stale hit and excess rebuild; no requirement to adopt Bazel/DVC. |
| Music identification | https://github.com/acoustid/chromaprint and https://acoustid.org/chromaprint | Fast compact fingerprint oriented to near-identical audio/full matching, **not** a general precise multicamera sync solution; its README cites Yan Ke et al (CVPR 2005), Kurth & Müller (2008), Jang et al (2009) | Analyze current sound sync before considering fingerprint as a coarse index/filter. Cross-correlate locally for exact offsets, drift, silence and clock mismatch if missing. |

## Search policy
- **Two lanes**: (A) mature >50k-star repositories as ecosystem references, (B) niche authoritative papers/libraries regardless of star count. Popularity is a discovery heuristic, not evidence of technical suitability or permissive licensing.
- For every architecture topic: identify present code and test, collect relevant primary literature, extract testable hypothesis, define baseline, quality constraints, wall time/CPU/RAM/I/O/net/storage and A/B threshold before proposing code.
- Keep URLs, author/date, precise claim, limitations and license considerations; star counts are snapshots and change over time.
- Prefer no dependency until isolated quality/performance gains cover integration and maintenance costs.

## Suggested first research experiment
Existing Montara Show continuous-preview encoder is x264 ultrafast CRF24, 720p; engine review hover is x264 veryfast CRF30, 480x270/15 fps. They solve different tasks and cannot be assumed interchangeable. With the SAME clips and equivalent preview requirements, profile x264 preset trade-off, bytes per minute and time-to-first-preview. Use VMAF where meaningful for aligned reference plus perceptual/manual inspection, cut/seek and A/V sync verification. Audit engine benchmarks already in `tools/benchmarks/` first. Prior isolated 835-second source produced bigger proxy than original; not evidence of production failure.

## Next research theme queues
- Audio/video cross-correlation, robust synchronization, sub-sample offset, variable drift (inspect `core/stages/sync.py` before research recommendation).
- Incremental video-edit DAGs, content-addressable caches and eviction budgets, concurrency/single-flight.
- Hardware codecs/zero-copy decode and preview, browser WebCodecs and GPU with codec coverage and fidelity controls.
- Hybrid CPU/GPU vs data-transfer model on zero-cost infrastructure, with 10min/1h/5h workload classes.

Research derived from external sources verified 2026-10-28; not a new benchmark and no changes to main.
