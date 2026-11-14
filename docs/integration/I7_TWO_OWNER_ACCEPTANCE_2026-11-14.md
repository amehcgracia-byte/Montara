# I7 — Owner two-account acceptance gate (2026-11-14)

## A. Delivered in code
- Deterministic cross-owner integration contract uses actual SessionStore, ProjectCatalog and JobRecoveryLedger SQLite files.
- Six scenarios: project isolation in both directions; CSRF rejection; separate worker reservations; verified-cgroup-only release; unaffected second owner; and restart with orphan fencing until independently verified.
- Does not create any new login, browser, broker, media controller or Companion protocol.

## B. Duplicate avoidance
- Reuses I1–I4 mechanisms, I6a closure policy and existing tests; no copy of Chema's original editor.

## C. What is validated
- Test file: `tests/test_i7_two_owner_acceptance.py`.
- Command: `python -m unittest discover -s tests -p test_i7_two_owner_acceptance.py -v`.
- These are integration-contract tests using REAL SQLite and simulated process lifecycle. They are NOT Google login or end-to-end rendering tests.

## D. Blocking acceptance gates
- Two distinct real Google accounts signed into separate fresh browser profiles.
- Per-account private Projects: create, reopen, Stage/Push/Show, project thumbnails, Save shot, Swap, media playback and exports; unauthorized access attempts must be rejected.
- Windows and macOS installed native Companion; no original upload without explicit confirmation; verify signed package only when certificates available.
- Real Linux Engine isolation and cgroup verification: two simultaneous owners, stop/restart, long FFmpeg job, crash recovery and VM idle watchdog dry run.
- Verify local MP4/audio and inspect Linux E2E screenshots. Fix prior session CI collection error separately; do not mark green on older successes.
- I6b job-aware VM poweroff gate is still NOT complete; do not deploy the multi-Owner runtime on this basis alone.
- I5 Companion commercial signing, macOS notarization and auto-updater can be discussed after integration, but remain release blockers.

## E. Next
- Merge this read-only test and documentation with standard CI; finish I6b safety gate and execute human cross-platform acceptance.
- No deploy or user-data deletion. Engine 92c7bc33f59baae92a8d61e5dd4bf0ce9685d79e and Mixer f15ff91c1b80fc5f157099dcd9451d958d553ae6 unchanged.
