# Montara

Drop your footage. Get the edit.

Montara is the commercial, web-first sibling of **Zucker Editor**. It reuses the
Zucker engine untouched and gives it a new interface and brand.

| Mode  | What it makes                                   | Engine mode |
|-------|-------------------------------------------------|-------------|
| Stage | Full multicam video, synced and cut on the beat | `youtube`   |
| Pulse | Reel from all your clips: vertical, horizontal or mixed, with captions | `reel`      |
| Story | Scenes, text and motion (coming soon)           | `show`      |

## How it is built

```
montara/
├── engine/   Zucker Editor, git submodule pinned to one commit. Never edited here.
├── mixer/    Zucker Mixer, git submodule pinned to one commit. Never edited here.
├── mixer_adapter/  Single-song mode for the mixer: no song detection, one song = all tracks.
├── app.py    Starts the engine's API and serves Montara's interface.
├── web/      Montara interface (HTML/CSS/JS, no build step).
└── tests/    End-to-end journey: real server, real browser, real renders.
```

Zucker Editor stays the free local app with its own look. Montara never
changes it: engine improvements are made in `zucker_videos` and picked up here
by moving the submodule pointer (`git -C engine checkout <commit>` + commit).

## Run it (Linux or macOS)

```bash
git clone --recurse-submodules https://github.com/amehcgracia-byte/Montara-.git montara
cd montara
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
sudo apt install ffmpeg        # macOS: brew install ffmpeg
python app.py                  # open http://127.0.0.1:8080
```

Data lives in `~/MontaraData` (change with `--data`), never in `~/ZuckerVideos`.

## Test it for free

* **Automatic:** every push runs `.github/workflows/e2e.yml` on GitHub's Ubuntu
  runners: Stage and Pulse are made through the real interface and the exported
  MP4s are checked and attached to the run.
* **By hand in the browser:** *Code → Codespaces → Create codespace on this branch*.
  It installs everything, starts Montara and opens it in a new tab (port 8080).
  Real test footage to upload is in `tests/fixtures/real/`.
* **Locally:** `python tests/e2e_journey.py --output /tmp/montara-e2e`.
