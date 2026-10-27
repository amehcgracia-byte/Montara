# Mars expedition 2 — bounded proxy integrity (2026-10-27)

## Changes in Fernando branch

- `local_media/proxies.py` adds `proxy_signature()`, which hashes the proxy's byte length and at most the first and last 64 KiB (128 KiB total, independent of proxy size).
- A newly prepared proxy stores this signature in its private local manifest. On a normal cache hit, `prepare()` checks that the signature still matches before returning the cached record.
- The corrupt-proxy end-to-end regression is no longer marked as expected failure: it now requires regeneration of the damaged proxy.
- The earlier stat-first fast path remains, though reading and hashing up to 128 KiB adds some work compared with the previous 0.083-ms synthetic test.
- Legacy manifests without `proxy_signature` are still accepted for backwards compatibility. They do not gain protection until regenerated/migrated. This is an explicit limitation.

## Verification scope

A standalone local reproduction of the bounded signature helper passed four checks: identical file produces stable digest, mutation near the beginning is detected, mutation near the end is detected, and mutation strictly in the middle of a large file is **not** detected. A 2 MB synthetic file was read 100 times for an average signature calculation of about 0.095 ms in this environment (not a disk-cache guarantee and not a measurement of `prepare()`).

Tests committed to GitHub:
- `tests/test_proxy_signature.py` — three direct fingerprint tests.
- `tests/test_proxy_mars_known_issues.py` — corruption case changed from xfail to required regeneration, plus concurrency and VFR cases.

**Important:** the committed code and complete test suite have not been executed by GitHub CI in this turn. The signature reproduction is not a substitute for end-to-end video validation.

## Remaining vulnerabilities and next batch

1. Sampling the first and last 64 KiB can miss corruption elsewhere. For high-assurance delivery use a full streaming hash once at proxy creation plus a verification policy, or decode/error-check on scheduled occasions, balancing I/O cost.
2. Without a per-source lock two workers may still redundantly transcode the same input and publish the same final paths; unique temp names only eliminated their earlier collision. Seek a well-tested cross-platform lock.
3. Atomic JSON manifest publication and crash-recovery cleanup need review. A partially written manifest currently causes a slower re-probe/rebuild, but concurrent writes can still conflict.
4. Temporal correctness is not proven by equal durations: next experiments must compare PTS mapping and audio-offset drift on realistic VFR and multicamera footage.
5. The local proxy generator is not yet fully connected to the public browser-to-local architecture.

No change to Zucker engines, `main`, Vercel, Oracle or RunPod.
