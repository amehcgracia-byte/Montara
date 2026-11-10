# MONTARA I24 — Durable systemd target identity and Engine recovery

Date: 2026-11-10. Physical lab PASS; production broker NOT certified.

## Scope
Connect I18 durable job/fencing and I23 real DynamicUser Engine under an exact, persisted systemd target. Add target_unit to SQLite via additive migration. Derive service name from server-generated random job id only; persist before launch. Never accept a unit or path from HTTP.

## Verified physical evidence
Used Desktop Commander Remote on Oracle -> ssh montara -> GCP. Real pinned Engine b5e48317ef85225f901adc69af8cc17aa8146880, synthetic project, DynamicUser host UID 61973 (not host operator), system service resource quotas MemoryMax=768M, TasksMax=64, CPUQuota=100%, private network/home, readonly bundle.
Job reserved then unit persisted before launching; Engine JSON protocol ready/opened verified; job marked running. New ledger object simulated controller restart with worker still alive; orphan remained associated with exact unit and blocked same-owner admission. Exact unit stopped, saved cgroup verified empty, stopped state recorded, subsequent generation incremented.
All contract fields true. Physical elapsed 9.19 seconds including packaging, real Engine open, recovery and teardown.
24 offline regression tests PASS (+6 subtests) including I18/I19/I21, owner/project/generation mismatch and legacy schema migration. No residual service should remain after test.

## Operational limitations
This remains an operator-only laboratory invoked with sudo systemd-run; not an authenticated, least-privilege production broker. I21 GatewayJobBridge is not yet connected to a privileged service transport. Need a narrowly restricted helper that permits only generated unit IDs and trusted immutable bundle/workspace; no arbitrary sudo or systemd control from HTTP. Require durable IPC mapping and restart reconciliation after actual host failure, plus FFmpeg child cancellation under that policy.
I23 bundle copies ~1.3GB deps per lab run; production requires cached, immutable, versioned readonly bundle. No Companion/Stage/MP4 tested and no real Google session involved in I24.

## Next decision gate
Implement minimal broker helper and link to I21; test owner isolation + actual Engine open, crash/recovery and stop under least privilege, then feature-flagged beta for Fernando. Windows Companion inventory comes only when requested; do not reinstall blindly.
No main merge, no Chema 8101-8103 modification, no Owner 8115 or Cloudflare changes. GitHub #189 remains draft.
Remote access is now Desktop Commander Remote -> Oracle instance-20261001-0035 -> ssh montara -> GCP. TryGateway retired. Auto-shutdown fix deferred.
