# Montara — rules for coding agents

- `engine/` is the Zucker Editor submodule. NEVER edit, patch or commit files inside it.
  If the engine needs a change, it is made in the `zucker_videos` repo and the submodule
  pointer is moved here in a separate commit that names the new engine commit.
- Montara talks to the engine only through its HTTP API (`/api/v1/...`).
- The interface lives in `web/` (plain HTML/CSS/JS). Brand tokens are the CSS variables at
  the top of `web/montara.css`: black #0B0B0D, off-white #F5F3EF, accent #FF4F2E, Inter.
  Minimal, professional; no mascots; one accent colour.
- Mode names shown to users: Stage (engine `youtube`), Pulse (`reel`), Story (`show`).
  Never show "YouTube", "Reel", "Zucker" or "Einstein" in the interface.
- Montara data lives in `~/MontaraData` (or `--data`). Never read or write `~/ZuckerVideos`.
- Done means: `python tests/e2e_journey.py --output <dir>` passes on Linux and the
  screenshots it saves have been looked at.
