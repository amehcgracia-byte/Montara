# MONTARA — RunPod / Cloud Lab, kit v1
Run from the experimental checkout only. **Do not run on a production Montara workspace**.

## Objective
Make a cloud instance measurable and disposable before a real Montara full-project benchmark. **This script is an infrastructure smoke test, not a complete render.** It uses synthetic frames; no original footage is read, modified or uploaded.

## Invocation
```bash
git status --short
git rev-parse HEAD
git submodule status
python experiments/cloud_lab/run_lab.py --output /tmp/montara-lab-cpu.json
python experiments/cloud_lab/run_lab.py --gpu --output /tmp/montara-lab-gpu.json
```
The optional GPU run attempts NVENC; a visible FFmpeg encoder name alone does not prove GPU availability. Inspect `nvidia-smi`, `tests.h264_nvenc.ok`, decode results and host driver. **NVENC successful does NOT prove the current Zucker engine uses NVENC**, nor that 360/v360 improves.

## Before starting any paid pod
1. Obtain the owner's explicit approval of a small maximum spend; verify the credited balance, expiry and allowed service in the provider dashboard. Check actual hourly compute and persistent storage prices.
2. Capture exact Montara/engine/mixer commits and fixture hashes; ensure separate directory, data roots and private access. Do not change main, engine or mixer pins.
3. Prefer one cheap, short-lived GPU pod, CPU mode first, then the same synthetic smoke with `--gpu`. Avoid public open ports; connect via authorized private SSH.
4. Confirm CPU encode, actual GPU encode and decode; capture GPU/driver data. Stop if smoke fails or NVENC not usable.
5. Only then plan the full Montara benchmark using **the same actual source/edit plan** with isolated caches. Distinguish local CPU processing from remote GPU end-to-end time including transfer and storage.
6. Finish by stopping/removing the Pod and separately inspecting any persistent volume/storage and billing; do not run destructive cleanup on another owner's resources.

## Result contract
`run_lab.py` writes a JSON report containing platform, Python, cgroup CPU/RAM limits, SHA pins when running in a checkout, ffmpeg version, nvidia-smi inventory, encoder attempt time, file SHA and decode validation. Test is deliberately limited to 1–10 seconds of 640×360 synthetic footage, and is **not a scientifically comparable speedup** until repeated on identical hardware and settings.

## Current direction
**Local-first architecture remains the primary hypothesis.** Users may grant a folder to a local companion, keeping full originals on their machine; preview proxies/recipes may be movable. Remote GPU is an *optional measured alternative*, not a requirement. A browser by itself cannot magically grant a remote server access to local files. The precise local companion/permission/recovery/security design awaits maintainer coordination.

## Cloud order
RunPod (credit already held) → Google Cloud eligible credits → Azure eligible credits → AWS optional → Oracle ARM Always Free **last**, on the maintainer's independent account if available. Fernando's existing Oracle instance is reserved for other workloads.

## Collaboration
Read `docs/MONTARA_COLLAB_CLOUD_LAB_ENTIRE_PROTOCOL_2026-10-28.md`; no run without owner consent, no GitHub main/engine pin edits, no cloud costs or Entire activation without authorization. Each run requires owner, instance identity, budget cap, cleanup and a concise pass/fail report.

## Implementation status
- Portable runner script committed to Fernando experimental branch; full cloud install and full E2E **not yet tested**.
- Local prototype of the runner: 5 isolated pytest checks passed in Linux x86_64, CPU H.264 successful, NVENC unavailable in that local environment. **The checked-in variant was adapted from that prototype; it has not yet been executed from a full Montara checkout.**
