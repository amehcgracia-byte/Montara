# SATURNO — GOP/B end-boundary audit (2026-10-29)

**Status:** synthetic experimental evidence; **no** Zucker E2E; **no** universal packet-minimization rule.

Fixture: H.264 160x90 30fps 8s, FFmpeg 7.1.5, source 240 frames. Desired window starts at 3.2 seconds, and the source is compared to decoded pixel hashes without conflating PTS with hash. The original 2-second stream-copy MP4 contains 68 compressed packets and 62 decoded frames. Hash mapping identifies a non-consecutive source index transition 156→158 at the fragment end.

### Controlled experiment: vary only stream-copy duration

| Input seek 3.2s, duration | Decoded frames | Contiguous unique sequence against source? |
|---|---:|---|
| 2.0 s | 62 | NO |
| 2.067 s | 65 | NO |
| 2.1 s | 65 | NO |
| 2.2 s | 68 | NO |
| **2.4 s** | **74** | **YES** |

This is consistent with end-of-fragment dependencies, including B-frame references, but **the exact causal mechanism is not isolated**. **Adding 0.4s is NOT a general solution.** A closed dependency graph and VFR/PTS mapping must be investigated before approval.

### Independent method contrast
- Input `-ss`, stream-copy to MKV: 68 decoded frames, discontinuity.
- Output `-ss`, stream-copy to MKV: a non-decodable 741-byte result (FFmpeg itself exited 0). `-copyts` with input seek in this fixture also produced a non-decodable result. These outputs are explicit FAIL, not zero-frame successes.
- Output seek and `libx264 -crf 0`: 60 frames with unique exact decoded pixel sequence starting at source index 96; larger output and **not stream-copy**.

### Method notes
Investigated via `ffprobe -show_packets` and `-show_frames` with PTS/DTS; frame identity uses a separate decoder and per-frame pixel hashes. Count, monotonic timestamps and pixel hashes are separate validation requirements. This work reuses existing experiment fixture, does not change Zucker. Needs further validation of packet reference picture lists/POC/DPB, audio timing, multiple GOP patterns, VFR, and actual engine E2E.

### Primary technical references
- FFmpeg seek / stream-copy behavior: https://www.ffmpeg.org/ffmpeg.html
- FFprobe packet/frame introspection: https://ffmpeg.org/ffprobe.html

Source artifacts (not all yet versioned in repo): local `saturno_timeline/deep_audit/{REPORT.md,compare.py,variants.json,duration_sweep.json,source_packets.json,fragment_packets.json,source_frames.json,fragment_frames.json}`. Keep provenance clear: this checked-in document is **not** equivalent to archiving raw FFprobe evidence.
