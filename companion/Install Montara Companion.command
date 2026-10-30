#!/bin/bash
# Double-click: installs the Montara companion and starts it in this window.
# Run it again any time to start the companion. Nothing else to do.
cd "$(dirname "$0")" || exit 1
DIR="$HOME/.montara-companion"
pause() { echo; read -r -p "Press Enter to close this window…" _; }
echo "Montara companion"
echo

PY=""
for c in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    PY="$(command -v "$c")"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Your Mac needs Apple's command line tools once. A window will ask to install them:"
  echo "accept, wait until they finish, then double-click this file again."
  xcode-select --install 2>/dev/null
  pause; exit 1
fi

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if ! command -v ffmpeg >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "Installing FFmpeg (the first time takes a few minutes)…"
    brew install ffmpeg || { echo "FFmpeg could not be installed."; pause; exit 1; }
  else
    echo "Montara needs FFmpeg, which installs with Homebrew."
    echo "1. Paste this in this window and press Enter (it asks for your Mac password):"
    echo '   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    echo "2. Then double-click this file again."
    pause; exit 1
  fi
fi

mkdir -p "$DIR/bin"
[ "$(pwd)" = "$DIR" ] || cp companion.py "$DIR/companion.py"
mkdir -p "$HOME/Applications"
if [ "$(cd "$(dirname "$0")" && pwd)" != "$HOME/Applications" ]; then
  sed 's#^cd "$(dirname "$0")" || exit 1#cd "$HOME/.montara-companion" || exit 1#' "$0" > "$HOME/Applications/Montara Companion.command"
fi
chmod +x "$HOME/Applications/Montara Companion.command"
cat > "$DIR/bin/montara-companion" <<EOF
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:\$PATH"
exec "$PY" "$DIR/companion.py" "\$@"
EOF
chmod +x "$DIR/bin/montara-companion"
grep -q 'montara-companion/bin' "$HOME/.zshrc" 2>/dev/null || echo 'export PATH="$HOME/.montara-companion/bin:$PATH"' >> "$HOME/.zshrc"

echo "Installed. Next time open 'Montara Companion' with Spotlight (Cmd+Space) or type: montara-companion"
echo
exec "$PY" "$DIR/companion.py"
