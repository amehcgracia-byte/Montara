# B05 — Mars crater: proxy/original timestamp origin

## Actual measurement — 2026-10-27

Compared every per-frame `best_effort_timestamp_time` in an FFmpeg-generated H.264 original and an MP4 generated with the exact options currently used in `local_media.proxies.prepare()`: `-copyts -start_at_zero -fps_mode passthrough`.

| Fixture | Frames original/proxy | First PTS original | First PTS proxy | Maximum absolute PTS difference | Difference after constant-offset mapping |
| --- | ---: | ---: | ---: | ---: | ---: |
| 30fps CFR, four seconds | 120/120 | 0.0 s | 0.0 s | 0 ms | 0 ms |
| VFR, 2 s at 15fps + 2 s at 30fps | 90/90 | 0.0 s | 0.0 s | 0 ms | 0 ms |
| 30fps, encoded PTS shifted +3 s | 120/120 | 3.0 s | 0.0 s | **3000 ms** | 0 ms |

**Interpretation:** the current proxy generator deliberately normalizes original nonzero start timestamps to a zero-based stream. This need not be a bug: it may be correct for a normalized edit timeline. However, consumers must use an explicit source-to-proxy timestamp transform when comparing frames with external camera audio/timecode.

Do not blindly remove `-start_at_zero`; that would change the existing editor contract and could create leading gaps. Instead document/derive a shared offset and test video **and** audio timeline alignment before connecting proxies to multicamera editing.

## Reproducing

```bash
python experiments/media_optimization/benchmark_b05_pts.py
python -m pytest tests/test_benchmark_b05_pts.py -q
```

The standalone B05 script was run successfully in a disposable Linux environment using FFmpeg/ffprobe. The exact committed GitHub CI run has not been observed yet. The new pytest file checks the documented contract; it has not been represented as a completed CI run.

## Still missing

- Audio PTS origin, channel delays, timecode tracks, B-frame timestamps and camera drift.
- VFR with discontinuities, missing PTS or dropped frames.
- 30+ minute concert and 360 samples.
- Dynamic frame-selection accuracy vs a human annotated baseline.
- Concurrent work elimination: UUID temporary filenames prevent collision but do not stop redundant transcodes.
- A complete checksum: the current sampled proxy fingerprint detects some corruption but may miss changed middle bytes.

No engine submodules, production deployments or `main` were modified. No RunPod credits used.
