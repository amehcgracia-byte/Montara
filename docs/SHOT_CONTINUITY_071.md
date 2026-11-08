# Camera synchronization and continuity — 0.71

Engine b5e48317 follows 98bce068; Mixer f15ff91 is unchanged.

- Strong but unstable onset matches now try spectral evidence before costly HPSS. A verified lower score wins. The confidence and independent-check thresholds are retained. An actual rejected camera verified at −23.638 s, three checks within 46 ms; old onset checks differed by 622.23 s. No manual offsets were stored.
- Decorative cutaways over covered performances: at most two, spaced over the song. Actual uncovered gaps retain their existing fallback policy.
- Adjacent contiguous shots of the same view share one motion clock. Different authored angles/source times remain cuts. Edit boundaries remain independently selectable. Review and export use the same continuity recipe.
- Swap can return from decorative filler to a synchronized camera and prioritizes another source when available. A sole required camera shot keeps the existing coverage guard. New spherical candidates receive a saved full-stage pose.
- Video fades beneath a transparent logo; opaque logo borders extend to the matching matte. Opening and closing pictures/audio retain the selected duration, including original-quality Companion exports.
- Companion 0.6.10 verifies three CPU-decoded sample images before accepting GPU proxies. A successful encoder exit does not prove correct pixels. CPU fallback uses both CPU decoding and libx264. Older healthy caches can be checked once and retained; bad ones are rebuilt.

Real 26.4-second camera proof: original 184.6 MB, corrupt editing proxy picture error 0.1963, rebuilt 5.5 MB CPU proxy error 0.00366. These are bounded sample image differences, not a general perceptual-quality score or performance benchmark. Private sources and frames remain outside Git.

Local: 142 focused engine tests (including real FFmpeg logo fades), 28 Companion/cancellation tests; repeated real source synchronization passed. An additional real original-quality Companion export with a transparent personal logo passed: four selected seconds remain four seconds, with audible start/end and blended logo/footage. Final Linux CI run 42494645203 passed Stage, Push, Mix, Session and private-container journeys; screenshots were inspected. Windows discovery passed separately. The full Engine fast suite retains exactly the same 22 failures as base 98bce068 after correcting one obsolete alternating-motion test (test-only d49638f); there are no additional failure IDs. The complete Engine suite is not claimed green.

Installed release 765a34c on JM and Companion 0.6.10 on the Mac, with Engine b5e48317 and unchanged Mixer f15ff91. Authenticated version checks and the local health response agree. Private before/after comparison confirms the same active project, identical inputs and unchanged source size, timestamp and inode. No FER service or data was modified. Existing rendered videos and already uploaded corrupt proxies are not rewritten automatically.
