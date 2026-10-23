#!/bin/bash
# Double-click to run Montara on this Mac: http://127.0.0.1:8080
# First run installs its own Python environment in .venv-mac (a few minutes).
cd "$(dirname "$0")" || exit 1
pause() { echo; read -r -p "Press Enter to close…" _; }
PY=""
for c in python3.12 python3.11 python3.10 /usr/local/bin/python3 /opt/homebrew/bin/python3 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,12) else 1)' 2>/dev/null; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then echo "Montara needs Python 3.10, 3.11 or 3.12. Install it with:  brew install python@3.12"; pause; exit 1; fi
if ! command -v ffmpeg >/dev/null 2>&1; then echo "Montara needs FFmpeg. Install it with:  brew install ffmpeg"; pause; exit 1; fi
if [ ! -x .venv-mac/bin/python ] || [ requirements-mac.txt -nt .venv-mac/.installed ]; then
  echo "Installing Montara's Python environment with $PY (first time only)…"
  "$PY" -m venv .venv-mac && .venv-mac/bin/pip install -q -U pip && .venv-mac/bin/pip install -r requirements-mac.txt \
    && touch .venv-mac/.installed || { echo "Installation failed (see above)."; pause; exit 1; }
fi
# Use 8080, or the next free port if something else already uses it.
PORT=$(.venv-mac/bin/python -c 'import socket
for p in range(8080, 8100):
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", p)); print(p); break
    except OSError: pass
    finally: s.close()')
URL="http://127.0.0.1:$PORT"
(sleep 5; open "$URL") &
echo "Montara is running at $URL  ·  close this window to stop it."
.venv-mac/bin/python app.py --port "$PORT"
pause
