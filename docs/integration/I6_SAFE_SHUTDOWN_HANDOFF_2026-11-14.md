# I6 — Cooperative worker stop and safe VM poweroff boundary (2026-11-14)

## A. Novedades
- Native Owner systemd worker receives SIGTERM as a shutdown request instead of raising SystemExit.
- Its original private threaded WSGI server stops accepting requests and waits for active request threads to finish on close (daemon_threads=False, block_on_close=True).
- Exact-unit systemd policy gives 90 seconds (TimeoutStopSec=90s) before the existing SendSIGKILL=yes limit. An uncooperative task can still be terminated.
- No automatic restart, UI change, new server, owner identity or external scheduler.

## B. Duplicidades
- Reuses I3a/I3b ledger, cgroup control and I4 native Chema worker and original WSGI/Unix transport.
- No alternate shutdown daemon; no changes to Chema's current VM watchdog or idle timer.

## C. Reutilizacion
- Preserves KillMode=control-group, broker-authenticated stop, generation fencing and empty-cgroup verification.
- Current live VM idle watcher uses 120-minute threshold, 20-minute checks, 120-minute boot grace, real SSH/FFmpeg/benchmark checks. An opened idle worker alone does not prevent poweroff.

## D. Riesgos y puertas
- Graceful HTTP drain is NOT a durability guarantee for FFmpeg children, queued jobs, recipe persistence or concurrent Stage socket work. The 90-second hard limit can interrupt a long render. Do not deploy as complete shutdown safety without a job-level checkpoint/quiescence protocol.
- Current broker waits about 6 seconds for a cgroup after requesting stop. On longer stops it returns unverified and MUST retain the fenced Owner ledger, never release the slot early.
- Host poweroff can independently stop units; require operator-tested poweroff/drain gate for active rendering; fail closed when state is unknown.
- No changes to live systemd services, VM watchdog, originals or users.
- Separate I5 public cert/notarization/updater and I7 two-owner E2E remain pending.

## E. Validation and next gate
- Focused owner worker, systemd policy and I6 shutdown tests.
- Linux acceptance still needs test worker: active save, long-running render, SIGTERM, poweroff dry-run, restart/recovery, empty-cgroup verification.
- Engine/Mixer submodule SHAs unchanged.
