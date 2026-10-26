# Validation of the 0.38 continuation snapshot

- Parent-repository targeted tests: **13 passed** across chroma/library/source cache,
  private-access foundation and mixer FX-level tests.
- Mixer dependency: **13 passed** in test_noise_safety.py, including quiet musical audio.
- Portable selector check: two real MP4 cuts and durations, disk persistence,
  duplicate Yes handling, reversible No, and moving physical files between collections.
- Deployment builder reconstructed **47 sources and 94 assets** from tracked inputs.
- Browser checks on equivalent 0.38 source: Matrix letters over the original video
  while editing, keyed rain and snow, card autoplay, per-series filtering, separate
  full-background pass and visible Yes/No/Review actions.

These are targeted checks, not a full E2E certification or a commercial-readiness audit.
The public preview was already deployed as 0.38 before this source handoff.

![Matrix during live editing](screenshots/Montara-038-matrix-transparente.png)
![Rain without the green plate](screenshots/Montara-038-lluvia-transparente.png)
![Separate visual-library selector](screenshots/Selector-biblioteca-v2.png)
