# Montara — rules for coding agents

- `engine/` is the Zucker Editor submodule. NEVER edit, patch or commit files inside it.
  If the engine needs a change, it is made in the `zucker_videos` repo and the submodule
  pointer is moved here in a separate commit that names the new engine commit.
- `mixer/` is the Zucker Mixer submodule, same rule as `engine/`. Montara uses it through
  `mixer_adapter/`: `single_song.py` for one song and the isolated `session.py` worker
  for full-session detection and batch audio export. Never import vendor globals in new Flask threads.
- Montara talks to the engine only through its HTTP API (`/api/v1/...`).
- The interface lives in `web/` (plain HTML/CSS/JS). Brand tokens are the CSS variables at
  the top of `web/montara.css`: black #0B0B0D, off-white #F5F3EF, accent #FF4F2E, Inter.
  Minimal, professional; no mascots; one accent colour.
- Mode names shown to users: Stage (engine `youtube`), Push (`reel`), Show (`show`).
  Push descriptions must mention reels; provider names may appear where useful.
  Show subtypes are Gamer, Influencer, Story, Podcast.
- Montara data lives in `~/MontaraData` (or `--data`). Never read or write `~/ZuckerVideos`.
- Done means: `python tests/e2e_journey.py --output <dir>` passes on Linux and the
  screenshots it saves have been looked at.

- Read docs/HANDOFF_FERNANDO_038.md for current context. Older docs with Pulse/Story as top-level modes are historical.
- Keep tools/asset-selector separate from Montara; its candidates and decisions are not automatic production-library approvals.
- Report exactly which checks ran; do not claim full E2E or production readiness from targeted tests.
- Two labs share this repo: read docs/COLLABORATION.md, then docs/lab/STATUS-JM.md and docs/lab/STATUS-FER.md.
  Fernando's experiments are indexed in docs/lab/INVENTORY-FER.md; open long reports only when deciding about that piece.
