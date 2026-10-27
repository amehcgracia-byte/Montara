# B10 — Volume versus count: no-copy folder baseline (2026-10-27)

## What José Manuel already validated

The existing `docs/VALIDATION_038.md` documents Linux E2E on the main baseline: **Stage 100.23 s at 1920×1080**, **Push 30 s at 1080×1920** and **Mixer + Stage 100.23 s at 1920×1080** with completed output decoding (Actions run 40418744759). These are functional tests, **not comparable performance baseline data** for the new folder/proxy architecture.

## New B10 probe — measured locally

Nine sequential inventory runs per scenario using local temporary *sparse placeholder files* (logical size through truncate, no real video). These measure filesystem metadata enumeration, and separate total logical bytes from file count without allocating 100 GB.

| Files | Logical bytes | Median scan time | Observed range |
|---:|---:|---:|---:|
| 10 | 1 GB | 0.072 ms | 0.070–0.133 ms |
| 100 | 10 GB | 0.793 ms | 0.684–1.135 ms |
| 1000 | 100 GB | 8.000 ms | 7.500–9.558 ms |

This was an isolated reproduction of the `os.walk + stat` metadata workload, **not a measured run of the exact repository B08 function**. Results are environment- and filesystem-specific; synthetic sparse placeholders have **zero allocated media data blocks**, so these timings **must not be extrapolated** to HDD, NAS, network transfer, decoding, proxy creation, seeking, 4K export or total job completion. In this probe metadata enumeration scales primarily with file count, not the nominal footage volume.

Reproducible repository variant: `python -m experiments.media_optimization.benchmark_b10_sparse_inventory` or `python experiments/media_optimization/benchmark_b10_sparse_inventory.py` from repository root; it uses the exact B08 `inventory` function.

## Architecture decision from this phase

We do **not** need remote GPU or server storage to scan filename/size metadata from a user-approved folder. We **do** need a deliberate execution environment to decode/analyze/render raw media; a browser directory handle alone cannot give a remote FFmpeg process access to that folder.

**Next high-value benchmark:** same footage and hardware, compare (1) original ingest bytes/time, (2) cached analysis/proxy generation cold vs warm, (3) several random frame seeks, (4) 1, 10 and 30 minute final exports at fixed output settings, and (5) peak RAM/CPU/temporary disk. Measure stage timings rather than one misleading total number.

We will not redo José Manuel's full E2E suite blindly; instead compare the new optional components to its already validated journeys and only rerun E2E after integrating the new path into the actual editor. No deployment/main changes.
