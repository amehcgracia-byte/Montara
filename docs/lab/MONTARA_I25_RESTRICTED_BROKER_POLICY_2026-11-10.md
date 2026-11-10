# MONTARA I25 — Restricted Engine systemd control policy (2026-11-10)

STATUS: laboratory policy + physical cancellation PASS; NOT yet an installed privileged broker service. Do not turn on Engine endpoint in Owner.

## Implemented
`urano/restricted_systemd_broker.py` implements a trusted-only `RestrictedTargetControl` for I24 ledger jobs and an OS-neutral `SystemdControl` interface. An operation derives the only stoppable unit from a server-generated 128-bit job ID and requires a persisted exact unit mapping, canonical owner, project ID, generation and unfinished state. It forbids stopping any other systemd unit, including Owner and Chema's services. `fixed_launch_properties` defines a fixed set of systemd security/resource settings and syntactically restricts a version-pinned bundle to `/opt/montara/bundles/engine-<sha40>`. This is a policy template, NOT an installed executable or a complete privilege boundary.

Stop checks the verified unit cgroup `/system.slice/montara-i24-job-<32 hex>.service` before signaling, waits boundedly for termination and requires systemd inactive, `cgroup.procs` empty and `cgroup.events populated 0` (or the verified cgroup removed) before returning true. Stale or foreign owner/project/generation never triggers an OS call. Already stopped jobs cannot stop again.

## Physical evidence
On GCP VM via Desktop Commander Remote -> Oracle -> `ssh montara`, executed `tests/urano_i25_restricted_real_engine_lab.py` opt-in. Uses the I24 synthetic project, pinned full Engine `b5e48317ef85225f901adc69af8cc17aa8146880`, DynamicUser host UID **61279**, readonly temporary runtime bundle, cgroup RAM 768M/TasksMax 64/CPUQuota 100%, ledger job reserved before launch and recovered after a simulated controller restart. Policy `RestrictedTargetControl.stop_verified()` stopped that exact unit and attested an empty cgroup, after which the next generation could be reserved. **PASS; 5.48 seconds**, includes bundle preparation, Engine startup, state checks and cancellation.

Offline policy tests: owner/project/generation mismatch, stale job, malformed or foreign unit, foreign cgroup, live PIDs and fixed bundle path. Latest suite together with I24/I21: **19 tests + 19 subtests PASS**. No unit or filesystem leftovers in the prior physical lab. No `main` changes.

## Critical remaining deployment gate
**This is NOT yet a full least-privilege broker.** Physical test's `LabOnlySystemd` still invokes `sudo systemctl` as an operator. The Owner backend does not load this module or control systemd. Next step is a dedicated root-owned broker daemon or helper with a private authenticated Unix-domain socket (peer identity verified), a distinct service UID from Owner, root-owned immutable configuration and ledger/bundle, fixed operation schema, and no arbitrary commands/paths/units/UIDs. Prove denied access from the Owner web service UID before allowing actual Google sessions. No broad `sudo` permission should be delegated to Owner; operator currently has NOPASSWD ALL for lab only. Production bundle must be immutable and reusable, not copied ~1.3GB per job.

Then connect that broker to I21 `GatewayJobBridge`, validate physical restart cleanup, isolate real Engine/FFmpeg, and enable feature flag for user's private beta. Thereafter inspect Windows Companion install/version and complete Stage -> MP4 local.

Do not touch `main`, PR #189, Owner 8115, Cloudflare, Chema 8101/8102/8103. TryGateway retired. Auto-shutdown change deferred.

## Private Unix IPC policy (not deployed)

Added `urano/restricted_broker_ipc.py`: a Linux AF_UNIX request parser that verifies the connecting process via kernel `SO_PEERCRED` (not an untrusted claimed owner), requires an explicitly configured non-root trusted UID **different from the web account UID**, and accepts ONLY `{op: stop, job_id: job-<hex32>, generation: positive integer}` with strict size and exact keys. It resolves the canonical owner/project from the server-side ledger rather than the wire and invokes the restricted target policy; any failure retains ledger `stopping` and prevents reuse. No generic command execution, new-unit creation, shell, path, PID, UID or systemd-property fields.

Tests use real AF_UNIX `socketpair` and kernel peer credentials, check foreign UID rejection, malformed/oversized requests, fake unit/path/command fields, successful isolated stop and fail-closed PIDs. Together **18 tests + 24 subtests PASS** (IPC + policy + I24) on VM.

**Security boundary not yet installed**: there is no root daemon, socket listener, root-owned permissions/configuration or dedicated broker Unix account. This module must NOT be imported into the public Owner process. Need a system administrator-approved installation that verifies real Owner UID cannot reach the socket, checks root-owned readonly runtime and ledger integrity, and supplies a fixed launch API with attestation before real beta.
