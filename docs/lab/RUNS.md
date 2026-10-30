# Montara — history of measured runs

Every finished job we time goes here, newest first: date, versions, machine, inputs and seconds per engine stage.
It lets both labs compare like with like. Only compare rows with the same `engine` and the same machine.

- **Chema's lab:** run `montara-runs` on the Mac (from `deploy/vm/mac-tools.sh`). It runs `deploy/vm/run_history.py` on the VM and saves `~/montara-runs.jsonl`; attach that file to Claude, who adds the new rows to `docs/lab/runs.jsonl` and to the table below.
- **Fernando's lab:** add your rows in the same format (an E2E `summary.json` also works) and say where they came from.
- Records carry file names only, never paths: this repository is public.

| Date | Lab | Mode | Inputs | Small versions | ingest | sync | edit | export | Engine total | Engine · machine | Note |
|---|---|---|---|---|---:|---:|---:|---:|---:|---|---|
| 2026-10-30 | Chema | Stage (real jam) | Sony 1080p H.264 90 s + 360 3840×1920 HEVC 15 min + 4K H.264 3840×2160 29.97 fps 16 min; master «The Floor Remembers», song range 23.3–631.3 s; 628 s output | no (originals uploaded) | 0.0 (cache) | 9.8 | 16.8 | **1388.1** | 1414.7 | c89e779 · GCP e2-standard-8 (AMD EPYC 7B12) / 32 GB | 2.2 s of export per output second, against 6.3 in the 4 vCPU row: 2.8× faster with one more 4K camera. Twice the cores alone does not explain it; the share of 360 shots was not recorded, so the rest is unattributed |
| 2026-10-30 | Chema | Stage (real jam) | Sony 1080p H.264 90 s + 360 3840×1920 HEVC 15 min; master «The Floor Remembers»; 654 s output | no | 0.0 (cache) | 7.3 | 49.0 | **4101.5** | 4157.8 | c89e779 · GCP e2-standard-4 (Intel Xeon 2.20 GHz) / 16 GB | Export 6.3× slower than real time, almost all 360 reprojection of the original on CPU; no song range |
| 2026-10-30 | Fer | Stage (synthetic E2E) | 2 synthetic cameras, 40.2 s output | no | 38.8 | 54.5 | 24.7 | 195.1 | 313.1 | c89e779 · GCP 4 vCPU / 16 GB | `JUPITER_E2E_STAGE_2026-10-30.md`; CPU shared with a `jm` job at the same time, so not an isolated benchmark |

`run_history.py` reads the machine when it runs, not when the job ran: after a machine change, correct the `machine` field of older jobs by hand.

Raw records: `docs/lab/runs.jsonl` (one JSON object per line, written by `run_history.py`).
