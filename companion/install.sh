#!/usr/bin/env bash
# Montara companion: one command in Terminal, no app window, no wizard.
#   curl -fsSL https://raw.githubusercontent.com/amehcgracia-byte/Montara/main/companion/install.sh | bash
# Installs into ~/.montara-companion, adds the 'montara-companion' command and starts it.
# Needs Python 3.9+ (macOS ships it with the Command Line Tools) and FFmpeg.
set -euo pipefail
DIR="$HOME/.montara-companion"
REF="${MONTARA_REF:-main}"
RAW="https://raw.githubusercontent.com/amehcgracia-byte/Montara/$REF/companion"

say() { printf '  %s\n' "$*"; }
echo "Montara companion"

PY=""
for c in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    PY="$(command -v "$c")"; break
  fi
done
if [ -z "$PY" ]; then
  say "Python 3.9 or newer is needed. On a Mac run:  xcode-select --install   then run this command again."
  exit 1
fi
say "python: $PY"

if ! command -v ffmpeg >/dev/null 2>&1 && [ ! -x /opt/homebrew/bin/ffmpeg ] && [ ! -x /usr/local/bin/ffmpeg ]; then
  if command -v brew >/dev/null 2>&1; then
    say "installing FFmpeg with Homebrew (a few minutes the first time)…"
    brew install ffmpeg
  else
    say "FFmpeg is needed. Install Homebrew (https://brew.sh), then:  brew install ffmpeg"
    say "and run this command again."
    exit 1
  fi
fi
say "ffmpeg: ok"

# Do not replace code underneath a local mix, proxy or video render.
if command -v lsof >/dev/null 2>&1; then
  for listener in $(lsof -t -iTCP:47820 -sTCP:LISTEN 2>/dev/null || true); do
    if pgrep -P "$listener" >/dev/null 2>&1; then say "Wait for the current Montara work to finish, then run this installer again.";exit 1;fi
  done
fi
mkdir -p "$DIR/bin"
for f in video_recipe.py video_jobs.py; do
  curl -fsSL "$RAW/$f" -o "$DIR/$f.new" && mv "$DIR/$f.new" "$DIR/$f"
done
curl -fsSL "$RAW/companion.py" -o "$DIR/companion.py.new" && mv "$DIR/companion.py.new" "$DIR/companion.py"
cat > "$DIR/bin/montara-companion" <<EOF
#!/bin/bash
exec "$PY" "$DIR/companion.py" "\$@"
EOF
chmod +x "$DIR/bin/montara-companion"

for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
  if [ -f "$rc" ] || [ "$rc" = "$HOME/.zshrc" ]; then
    grep -q 'montara-companion/bin' "$rc" 2>/dev/null || echo 'export PATH="$HOME/.montara-companion/bin:$PATH"' >> "$rc"
  fi
done
# Optional local mixer (about 150 MB): songs of a full session are mixed on this computer with
# the same mixer as the server, and only the finished MP3 is uploaded.
#   curl -fsSL https://raw.githubusercontent.com/amehcgracia-byte/Montara/main/companion/install.sh | bash -s -- --mixer
if [ "${1:-}" = "--mixer" ] || [ "${MONTARA_MIXER:-}" = "1" ]; then
  MIX="$DIR/mixer"; ROOT_RAW="https://raw.githubusercontent.com/amehcgracia-byte/Montara/$REF"
  say "local mixer: preparing (one time, about 150 MB)…"
  SHA="$(curl -fsSL "https://api.github.com/repos/amehcgracia-byte/Montara/contents/mixer?ref=$REF" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["sha"])')"
  [ -n "$SHA" ] || { say "could not read the server's mixer version; try again later"; exit 1; }
  mkdir -p "$MIX/mixer_adapter"
  rm -rf "$MIX/mixer.new" && mkdir -p "$MIX/mixer.new"
  curl -fsSL "https://codeload.github.com/amehcgracia-byte/ZuckerMixer/tar.gz/$SHA" | tar -xz -C "$MIX/mixer.new" --strip-components=1
  rm -rf "$MIX/mixer" && mv "$MIX/mixer.new" "$MIX/mixer"
  for f in mixer_adapter/single_song.py mixer_adapter/extract.py mixer_adapter/render_progress.py track_types.py; do
    curl -fsSL "$ROOT_RAW/$f" -o "$MIX/$f"
  done
  curl -fsSL "$RAW/local_mix.py" -o "$MIX/local_mix.py"
  [ -x "$MIX/venv/bin/python" ] || "$PY" -m venv "$MIX/venv"
  "$MIX/venv/bin/python" -m pip install -q --upgrade pip
  # Only what the render uses (no Matchering: songs with a mastering reference stay on the server).
  "$MIX/venv/bin/python" -m pip install -q numpy scipy soundfile pyloudnorm flask
  (cd "$MIX" && ZUCKER_MIXER_STATE_ROOT="$(mktemp -d)" "$MIX/venv/bin/python" -c 'import sys; sys.path[:0] = [".", "mixer"]; import jam_app, jam_mix_pipeline, track_types; from mixer_adapter.single_song import SingleSongMix') \
    || { say "the local mixer could not start; the server keeps mixing your songs"; rm -f "$MIX/MIXER_COMMIT"; exit 1; }
  echo "$SHA" > "$MIX/MIXER_COMMIT"
  say "local mixer ready (mixer ${SHA:0:7}, $(du -sh "$MIX" | cut -f1))"
fi

# Optional native video renderer: reuse the pinned Editor's export, not a
# second simplified renderer. It needs no speech model, LLM or torch download.
if [ "${1:-}" = "--video" ] || [ "${MONTARA_VIDEO:-}" = "1" ]; then
  VIDEO="$DIR/video"; ROOT_RAW="https://raw.githubusercontent.com/amehcgracia-byte/Montara/$REF"
  VPY=""
  for candidate in python3.11 python3.12 python3.10 "$DIR/mixer/venv/bin/python" "$PY"; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys;sys.exit(0 if (3,10)<=sys.version_info[:2]<=(3,12) else 1)' 2>/dev/null; then VPY="$(command -v "$candidate")";break;fi
  done
  if [ -z "$VPY" ] && command -v brew >/dev/null 2>&1; then
    brew install python@3.11
    VPY="$(brew --prefix python@3.11)/bin/python3.11"
  fi
  [ -n "$VPY" ] || { say "The video renderer needs Python 3.10–3.12. Install Python 3.11, then run this installer with --video."; exit 1; }
  SHA="$(curl -fsSL "https://api.github.com/repos/amehcgracia-byte/Montara/contents/engine?ref=$REF" | "$VPY" -c 'import json,sys; print(json.load(sys.stdin)["sha"])')"
  mkdir -p "$VIDEO/brand"
  touch "$VIDEO/INSTALLING"
  rm -rf "$VIDEO/engine.new" && mkdir -p "$VIDEO/engine.new"
  curl -fsSL "https://codeload.github.com/amehcgracia-byte/zucker_videos/tar.gz/$SHA" | tar -xz -C "$VIDEO/engine.new" --strip-components=1
  rm -rf "$VIDEO/engine" && mv "$VIDEO/engine.new" "$VIDEO/engine"
  for f in local_video.py video_recipe.py; do curl -fsSL "$RAW/$f" -o "$VIDEO/$f"; done
  for f in montara-logo.png montara-watermark.png; do curl -fsSL "$ROOT_RAW/web/brand/$f" -o "$VIDEO/brand/$f"; done
  [ -x "$VIDEO/venv/bin/python" ] || "$VPY" -m venv "$VIDEO/venv"
  "$VIDEO/venv/bin/python" -m pip install -q 'numpy>=1.26,<2' 'scipy>=1.11,<1.15' 'opencv-python-headless>=4.9,<4.12' 'pillow>=10' 'flask>=3'
  (cd "$VIDEO/engine" && ZUCKER_DATA_ROOT="$VIDEO/state" "$VIDEO/venv/bin/python" -c 'from core.stages.export import ExportStage')
  echo "$SHA" > "$VIDEO/ENGINE_COMMIT"
  rm -f "$VIDEO/INSTALLING"
  say "Original-quality video renderer ready (editor ${SHA:0:7})"
fi

say "installed in $DIR · next time just type:  montara-companion"
echo
exec "$PY" "$DIR/companion.py"
