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

if [ "${MONTARA_REQUIRE_CLOSED:-0}" = 1 ]; then
  if ! command -v lsof >/dev/null 2>&1; then
    say "Could not check whether Companion is running."; exit 1
  fi
  if lsof -t -iTCP:47820 -sTCP:LISTEN >/dev/null 2>&1; then
    say "Wait for Montara work to finish, quit Companion, then reopen this installer."
    exit 1
  fi
fi
if [ -n "${MONTARA_EXPECTED_ENGINE:-}" ]; then
  expected="$(curl -fsSL "https://api.github.com/repos/amehcgracia-byte/Montara/contents/engine?ref=$REF" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["sha"])')"
  if [ "$expected" != "$MONTARA_EXPECTED_ENGINE" ]; then
    say "The installer does not match the Editor version on this page."; exit 1
  fi
fi

# Do not replace code underneath a local mix, proxy or video render.
if command -v lsof >/dev/null 2>&1; then
  for listener in $(lsof -t -iTCP:47820 -sTCP:LISTEN 2>/dev/null || true); do
    if pgrep -P "$listener" >/dev/null 2>&1; then say "Wait for the current Montara work to finish, then run this installer again.";exit 1;fi
  done
  for listener in $(lsof -t -iTCP:47820 -sTCP:LISTEN 2>/dev/null || true); do
    process=$(ps -p "$listener" -o command=)
    case "$process" in
      *"$DIR/companion.py"*) ;;
      *) say "Port 47820 belongs to another application; nothing was replaced."; exit 1 ;;
    esac
    if [ "${MONTARA_REQUIRE_CLOSED:-0}" = 1 ]; then
      say "Companion started during setup. Wait for work to finish and quit it first."; exit 1
    fi
    say "Stopping the idle Companion before updating…"
    kill -TERM "$listener"
    for attempt in $(seq 50); do
      kill -0 "$listener" 2>/dev/null || break
      sleep .1
    done
    if kill -0 "$listener" 2>/dev/null; then say "Companion did not stop; nothing was replaced."; exit 1; fi
  done
fi
mkdir -p "$DIR/bin"
for f in video_recipe.py video_jobs.py windows_support.py; do
  curl -fsSL "$RAW/$f" -o "$DIR/$f.new"
  mv "$DIR/$f.new" "$DIR/$f"
done
for f in spherical_proxy.py spatialmedia/__init__.py spatialmedia/metadata_utils.py spatialmedia/LICENSE spatialmedia/mpeg/__init__.py spatialmedia/mpeg/box.py spatialmedia/mpeg/constants.py spatialmedia/mpeg/container.py spatialmedia/mpeg/mpeg4_container.py spatialmedia/mpeg/sa3d.py spatialmedia/mpeg/sv3d.py; do
  mkdir -p "$DIR/$(dirname "$f")"
  curl -fsSL "$RAW/$f" -o "$DIR/$f.new"
  mv "$DIR/$f.new" "$DIR/$f"
done
curl -fsSL "$RAW/companion.py" -o "$DIR/companion.py.new"
mv "$DIR/companion.py.new" "$DIR/companion.py"
cat > "$DIR/bin/montara-companion" <<EOF
#!/bin/bash
exec "$PY" "$DIR/companion.py" "\$@"
EOF
chmod +x "$DIR/bin/montara-companion"

if [ "${MONTARA_NO_SHELL_SETUP:-0}" != 1 ]; then
for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
  if [ -f "$rc" ] || [ "$rc" = "$HOME/.zshrc" ]; then
    grep -q 'montara-companion/bin' "$rc" 2>/dev/null || echo 'export PATH="$HOME/.montara-companion/bin:$PATH"' >> "$rc"
  fi
done
fi
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
  SHA="${expected:-$(curl -fsSL "https://api.github.com/repos/amehcgracia-byte/Montara/contents/engine?ref=$REF" | "$VPY" -c 'import json,sys; print(json.load(sys.stdin)["sha"])')}"
  [[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { say "Invalid Editor version."; exit 1; }
  mkdir -p "$VIDEO"
  stage=$(mktemp -d "$VIDEO/.update.XXXXXXXX")
  trap 'rm -rf "$stage"' EXIT
  mkdir -p "$stage/engine" "$stage/brand"
  curl -fsSL "https://codeload.github.com/amehcgracia-byte/zucker_videos/tar.gz/$SHA" | tar -xz -C "$stage/engine" --strip-components=1
  for f in local_video.py video_recipe.py; do curl -fsSL "$RAW/$f" -o "$stage/$f"; done
  for f in montara-logo.png montara-watermark.png; do curl -fsSL "$ROOT_RAW/web/brand/$f" -o "$stage/brand/$f"; done
  [ -x "$VIDEO/venv/bin/python" ] || "$VPY" -m venv "$VIDEO/venv"
  "$VIDEO/venv/bin/python" -m pip install -q 'numpy>=1.26,<2' 'scipy>=1.11,<1.15' 'opencv-python-headless>=4.9,<4.12' 'pillow>=10' 'flask>=3'
  (cd "$stage/engine" && ZUCKER_DATA_ROOT="$stage/smoke" "$VIDEO/venv/bin/python" -c 'from core.stages.export import ExportStage')
  printf '%s\n' "$SHA" > "$stage/ENGINE_COMMIT"
  if [ "${MONTARA_REQUIRE_CLOSED:-0}" = 1 ] && lsof -t -iTCP:47820 -sTCP:LISTEN >/dev/null 2>&1; then
    say "Companion started during setup. Wait for work to finish and quit it first."; exit 1
  fi
  touch "$VIDEO/INSTALLING"
  if [ -d "$VIDEO/engine" ] || [ -d "$VIDEO/brand" ]; then
    previous=$(mktemp -d "$VIDEO/.previous.XXXXXXXX")
    for f in engine ENGINE_COMMIT local_video.py video_recipe.py brand; do
      [ ! -e "$VIDEO/$f" ] || mv "$VIDEO/$f" "$previous/$f"
    done
  fi
  for f in engine local_video.py video_recipe.py brand ENGINE_COMMIT; do mv "$stage/$f" "$VIDEO/$f"; done
  rm -f "$VIDEO/INSTALLING"
  rm -rf "$stage"
  trap - EXIT
  say "Original-quality video renderer ready (editor ${SHA:0:7})"
fi

if [ "${MONTARA_REQUIRE_CLOSED:-0}" = 1 ]; then
  mkdir -p "$HOME/Applications"
  cat > "$HOME/Applications/Montara Companion.command" <<'EOF'
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
exec "$HOME/.montara-companion/bin/montara-companion"
EOF
  chmod +x "$HOME/Applications/Montara Companion.command"
  say "Installed. Next time, open Montara Companion from Spotlight."
else
  say "installed in $DIR · next time just type:  montara-companion"
fi
echo
if [ "${MONTARA_BACKGROUND:-0}" = 1 ]; then
  nohup "$PY" "$DIR/companion.py" > "$DIR/companion.log" 2>&1 < /dev/null &
  for attempt in $(seq 30); do
    if curl -fsS http://127.0.0.1:47820/health >/dev/null 2>&1; then exit 0; fi
    sleep 1
  done
  say "Companion did not become ready. Its log is in $DIR/companion.log"
  exit 1
else
  exec "$PY" "$DIR/companion.py"
fi
