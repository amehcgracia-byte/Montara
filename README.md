# Montara 0.38

Web editor for music, reels and creator videos. This continuation branch captures
the working public prototype and the separate asset-selection tool.

- **Stage:** multicamera music video and track mixing/mastering.
- **Push:** reels, including four moments from one URL or uploaded video.
- **Show:** Gamer, Influencer, Story and Podcast editing styles.

Full context, current limitations and Fernando's onboarding are in
[docs/HANDOFF_FERNANDO_038.md](docs/HANDOFF_FERNANDO_038.md).
The private repository's main branch was still at 0.10 when this branch was prepared.

## Run locally

Clone this branch with submodules, use Python 3.11, and install FFmpeg/ffprobe.

```sh
git clone --branch codex/montara-038-handoff --recurse-submodules https://github.com/amehcgracia-byte/Montara.git
cd Montara
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py --host 127.0.0.1 --port 8080
```

Review requirements-mac.txt on macOS. Open http://127.0.0.1:8080.
Data belongs in ~/MontaraData or the chosen --data directory, never ~/ZuckerVideos.
The engine and mixer are submodules: retain their pinned revisions.

## Separate visual library selector

```sh
.venv/bin/python tools/asset-selector/server.py
```

Open http://127.0.0.1:8097. Hover previews, Yes/No/Review, per-series folders,
green/black overlays and full-background video passes. Current selections are seeded
from tools/asset-selector/examples; later working data is ignored by Git.
These clips are candidates for review, not commercially cleared assets.
FFmpeg and ffprobe must be on PATH. YouTube embedding/downloading may be restricted.

## Checks

```sh
python -m pytest tests/test_chroma_library.py tests/test_green_library.py tests/test_source_cache.py tests/test_private_access.py tests/test_mixer_fx_levels.py -q
python tools/asset-selector/check_selector.py
```

Full journey tests require Playwright browsers and real rendering time; the targeted
checks above do not certify every mode or production readiness.

## Public preview and deployment source

Stable URL: https://montara-tau.vercel.app/ . Ads: /anuncios/; plan simulator: /planes/.
The editor runs in separate Vercel Sandbox instances, not inside a static page.
Deployment sources are in deployment/vercel. Run npm ci and npm run build there.
Credentials are excluded and account-bound templates must be provisioned separately.
Do not deploy to the owner's account or replace the stable alias without agreement.
