# Mars expedition — proxy robustness, 2026-10-27

## Three experiments against Montara's 0.39 proxy code

These measurements were executed with a source-equivalent copy of `local_media/proxies.py` in a disposable Linux environment, with FFmpeg 7.1.5. The exact GitHub commit has **not yet been validated by GitHub CI**.

1. **Concurrent generation** — two threads called `prepare()` on the same fresh 1280×720/7s original and shared cache. Before the patch, one completed and one failed when `ffprobe` inspected the same transient `.pending.mp4` filename. After using distinct UUID temporary filenames, both completed successfully in one repeat. This removes the immediate temporary-file collision; it does **not** prevent duplicate simultaneous transcodes or completely serialize final manifest commits.
2. **Damaged cached MP4** — after a successful prepare, overwriting the cached video with 128 invalid bytes still yielded a warm cache hit in around 0.2 ms. A nonempty file is not sufficient evidence that a proxy can be decoded. A regression test captures the failure as `xfail` until an appropriate lightweight validation/checksum policy is designed.
3. **VFR baseline** — a synthetic 6s H.264 with mixed 15fps/30fps intervals retained a 6s duration after proxy preparation; reported average frame rate 22.5 fps. This is only a duration test: exact timestamp alignment, audio drift, unusual camera formats and VFR with missing timestamps remain untested.

## Code change

`local_media/proxies.py` now generates a **distinct random `.pending.mp4` name per concurrent attempt**. Final cache naming, `source_id`, codec, quality, output, and original-resolution contracts are unchanged. The change was kept intentionally minimal; the two workers can still do redundant work.

Regression suite added: `tests/test_proxy_mars_known_issues.py` (parallel preparation should finish, a known failure on cached corruption is marked expected-failure, plus synthetic VFR smoke test).

## Next decision and guardrails

- **Preferred next step:** add an actual per-source cross-process lock and recheck the completed cache under the lock before transcoding. Use a cross-platform tested solution (Linux/macOS/Windows), but do not add an unreviewed locking library or create unbounded wait on stale locks.
- Add **lightweight cache verification** with a design for bounded work on 800 GB sources (e.g. progressive hash/sampled digest plus occasional actual decode), retaining provenance and safe invalidation. A header-only MP4 check will not detect all damage.
- Benchmark alignment with actual frame PTS on multi-camera/long-VFR samples. A similar total duration is not sufficient for synchronized montage.
- Do not assume the 97% synthetic compression result will apply to live concert footage.
- Keep everything on Fernando's branch until existing regressions and full media tests are run. No RunPod, Vercel, Oracle or main changes.
