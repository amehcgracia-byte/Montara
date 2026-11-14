# I6b — Read-only Owner shutdown guard (2026-11-14)

## A. What changed
- `urano/owner_poweroff_guard.py` inspects operator-selected Owner SQLite ledgers strictly read-only.
- Any starting/running/stopping/orphaned reservation blocks poweroff. Missing, corrupt, symlinked or unconfigured ledger fails closed.
- Exits 0 only for **candidate** ledgers with no unverified jobs; 1 for reserved, 2 for unknown. This tool NEVER shuts down a VM.
- Seven focused tests use real, isolated SQLite and cover unverified jobs, crash and verified cleanup.

## B. Duplicates avoided
- Existing I3 ledger and stop verification reused. No second watchdog, broker, process supervisor or server.
- Live VM timer (20 min checks, 120 min inactivity) and systemd services are not modified.

## C. Reuse
- Only an operator can supply ledger paths. The tool never accepts a browser path, creates directories, mutates jobs, releases cgroups or performs poweroff.
- Explicitly conservative: an idle running Owner reservation counts as reserved until broker has verified stopping and cgroup empty. This may increase VM uptime if used without an orderly idle-worker reaper.

## D. Blocking gates — NOT DEPLOYABLE YET
- Between a read-only snapshot and a host poweroff a new Owner admission can start. A real deployment MUST serialize admission with shutdown using a trusted broker-level gate/lock, quiesce and drain active jobs, recheck after closing admission, and only then request poweroff. This PR does NOT implement that transaction.
- Actual long-running Python, FFmpeg and cache/persistent writes need OS-level acceptance under separate systemd test workers. Failure/unknown must retain VM.
- Do not install this preflight into the live watchdog until the admission-lock transaction is implemented and reviewed.
- Never assume that zero open rows alone prove no externally launched Engine work.

## E. Verification
- `python -m unittest discover -s tests -p test_owner_poweroff_guard_i6b.py -v` => 7/7 PASS in isolated VM checkout.
- No original files, credentials, systemd units, timers, Engine/Mixer submodules or other lab state touched.
- Engine `92c7bc33f59baae92a8d61e5dd4bf0ce9685d79e`, Mixer `f15ff91c1b80fc5f157099dcd9451d958d553ae6`.
- I7a contracts integrated in main; I7b real two-account and Companion acceptance not yet validated.
