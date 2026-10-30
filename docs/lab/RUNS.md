# Montara — history of measured runs

Every finished job we time goes here, newest first: date, versions, machine, inputs and seconds per engine stage.
It lets both labs compare like with like. Only compare rows with the same `engine` and the same machine.

- **Chema's lab:** run `montara-runs` on the Mac (from `deploy/vm/mac-tools.sh`). It runs `deploy/vm/run_history.py` on the VM and saves `~/montara-runs.jsonl`; attach that file to Claude, who adds the new rows to `docs/lab/runs.jsonl` and to the table below.
- **Fernando's lab:** add your rows in the same format (an E2E `summary.json` also works) and say where they came from.
- Records carry file names only, never paths: this repository is public.

| Date | Lab | Mode | Inputs | Small versions | ingest | sync | edit | export | Engine total | Engine · machine | Note |
|---|---|---|---|---|---:|---:|---:|---:|---:|---|---|
| 2026-10-30 | Fer | Stage (synthetic E2E) | 2 synthetic cameras, 40.2 s output | no | 38.8 | 54.5 | 24.7 | 195.1 | 313.1 | c89e779 · GCP 4 vCPU / 16 GB | `JUPITER_E2E_STAGE_2026-10-30.md`; CPU shared with a `jm` job at the same time, so not an isolated benchmark |

Raw records: `docs/lab/runs.jsonl` (one JSON object per line, written by `run_history.py`).
