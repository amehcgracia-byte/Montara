# SATURNO — three varied codec trims and transition to SAT-04 (2026-10-29)

**Empirical:** Linux FFmpeg 7.1.5; generated 8 s testsrc2 at 160×90, 30fps. Trial code and JSON are attached in conversation as `/mnt/data/saturno_timeline/three_trials.py` and `.../three_trials/results.json`; **not yet versioned as source in GitHub**.

Three materially distinct codecs/GOP structures: H264 libx264 GOP90 B=3, HEVC libx265 GOP60 B=3, H264 all-I GOP1 B=0. Each cut with input seek and stream copy in MKV, once with requested duration, plus 0.5 s and plus 1.0 s. Decoded framemd5 hashes compared to full source. PASS = all fragment frames map to a *unique, contiguous* run of source frames; does not prove requested start/end or Montara export.

| Case | Source bytes | No padding (frames/bytes/contiguous) | +0.5s | +1s |
|---|---:|---|---|---|
| H264 GOP90 B3 | 137477 | 68 / 42302 / NO | 83 / 48534 / NO | 98 / 58817 / NO |
| HEVC GOP60 B3 | 164487 | 62 / 48454 / NO | 77 / 57553 / YES | 92 / 68786 / NO |
| H264 all-I GOP1 | 483269 | 60 / 122424 / YES | 75 / 154526 / YES | 90 / 185982 / YES |

**New negative outcome:** Increasing postroll is not monotonic for compressed stream-copy. In HEVC +0.5 succeeds but +1.0 fails under this mapping criterion. The earlier 2.4s success in a different H264 experiment **cannot** be generalized to a universal padding rule.

**Scientific closure criterion:** Stop padding sweeps. Future attempt must be based on real codec reference dependency information/PTS and independent decoded-sequence verification, rather than selecting an ad hoc margin. Reopen SAT-03 only when an adapter to the *real* Zucker and an isolated A/B QA is available.

**Next:** SATURNO-04 will model end-to-end transfer + queue + remote compute + download *against local render* under measured or explicitly hypothetical parameters; no assertion of real savings until fixture/network measurements. This also informs whether GPU cloud is necessary at all.

**Important limitations:** Small synthetic footage, no audio in these three trials, no VFR, no full export, no independent confirmation of exact packet reference graph, no latency/cost measurement. All variants emitted decodable MKV in this trial. Sources: FFmpeg docs https://ffmpeg.org/ffmpeg.html and FFprobe https://ffmpeg.org/ffprobe.html .
