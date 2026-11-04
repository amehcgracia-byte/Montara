# EX-14H-15T - Native sync check

2026-11-04. Isolated engine 0f9ec03. No production changes.

Master: IMG_0044.MOV (iPhone). Clip: VID_20260824_204524_00_004.mp4 (360).

Independent audio alignment reference EX-14H-15I: -19.0369 seconds.
Native recover_offset: -19.0404 seconds, confidence 66.276, threshold 6.
Absolute difference: 0.0035 seconds.
Verification: 3/3 segments agree; unstable_sync false.

Measured time: audio and onset preparation 12.026 s; recover_offset 0.300 s; verify_sync_stability 0.546 s; total 12.871 s. Direct function test in RAM, not complete SyncStage pipeline. No fallback triggered in this direct test. This observation does not rule out ingest, normalization, export or cache bottlenecks.

Conclusion: native onset alignment passes on this pair. Close acoustic investigation and return to complete Stage E2E checks, including audio and video, before Companion and hybrid infrastructure work.
