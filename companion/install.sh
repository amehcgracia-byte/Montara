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

mkdir -p "$DIR/bin"
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
say "installed in $DIR · next time just type:  montara-companion"
echo
exec "$PY" "$DIR/companion.py"
