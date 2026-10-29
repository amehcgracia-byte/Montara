#!/usr/bin/env bash
# Native (no Docker) Montara install for ONE lab user: own checkout, venv, data, caches, port.
# Usage, as that user:  bash user_install.sh <branch> <port>
#   jm:  bash user_install.sh main 8101
#   fer: bash user_install.sh fernando/continuacion-montara 8102
# Needs GitHub access to the private repo with the user's OWN account (gh auth login, or an
# SSH key / token of that user). Never share credentials between the two accounts.
# Without GitHub on the VM: copy a checkout (with submodules) to ~/montara first and run with
# MONTARA_OFFLINE=1. MONTARA_GENERATE_PASSWORD=1 creates the private password and shows it once.
set -euo pipefail
branch=${1:?branch}; port=${2:?port}
root="$HOME/montara"; data="$HOME/montara-data"; conf="$HOME/.config/montara"
export XDG_CACHE_HOME="$HOME/.cache" UV_CACHE_DIR="$HOME/.cache/uv"
mkdir -p "$data" "$conf" "$HOME/.config/systemd/user"; chmod 700 "$conf"

# Python 3.11: the lock is compiled for 3.11 (Ubuntu 24.04 ships 3.12).
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv python install 3.11

if [ "${MONTARA_OFFLINE:-0}" = 1 ]; then
  [ -f "$root/app.py" ] && [ -f "$root/engine/server/api.py" ] || { echo "Copy the checkout with submodules to $root first"; exit 1; }
elif [ -d "$root/.git" ]; then
  git -C "$root" fetch origin "$branch" && git -C "$root" checkout "$branch" && git -C "$root" pull --ff-only
else
  git clone --branch "$branch" https://github.com/amehcgracia-byte/Montara.git "$root"
fi
[ "${MONTARA_OFFLINE:-0}" = 1 ] || git -C "$root" submodule update --init --recursive   # pinned engine/mixer, never moved here

uv venv --python 3.11 "$root/.venv"
uv pip install --python "$root/.venv/bin/python" -r "$root/deploy/requirements-linux.lock"
npm install --prefix "$data/Runtime" --no-audit --no-fund deno@2.5.6

# Private settings: password stays in a 600 file, never in Git, URLs or reports.
if [ ! -f "$conf/env" ]; then
  if [ "${MONTARA_GENERATE_PASSWORD:-0}" = 1 ]; then
    pw=$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)
    echo "Private Montara login for $(whoami): user 'montara', password: $pw  (shown once; stored in $conf/env)"
  else
    read -r -s -p "Private Montara password for $(whoami) (16+ chars): " pw; echo
  fi
  [ ${#pw} -ge 16 ] || { echo "Too short"; exit 1; }
  umask 077
  printf 'MONTARA_PREVIEW_PASSWORD=%s\nMONTARA_DATA=%s\nPATH=%s\nXDG_CACHE_HOME=%s\nTMPDIR=%s\n' \
    "$pw" "$data" "$data/Runtime/node_modules/.bin:$root/.venv/bin:/usr/bin:/bin" "$HOME/.cache" "$data/tmp" > "$conf/env"
  mkdir -p "$data/tmp"
fi

cat > "$HOME/.config/systemd/user/montara.service" <<UNIT
[Unit]
Description=Montara ($(whoami), $branch) on 127.0.0.1:$port
[Service]
WorkingDirectory=$root
EnvironmentFile=$conf/env
ExecStart=$root/.venv/bin/gunicorn --bind 127.0.0.1:$port --workers 1 --threads 8 --timeout 1800 deploy.entry:app
Restart=on-failure
[Install]
WantedBy=default.target
UNIT

cd "$root"   # deploy.* modules are imported from the checkout
set -a; . "$conf/env"; set +a
"$root/.venv/bin/python" -m deploy.preflight --server --data "$data" --smoke --output "$data/server-check.json"
"$root/.venv/bin/python" -m deploy.warmup --data "$data"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
systemctl --user daemon-reload && systemctl --user enable --now montara.service
echo "Montara for $(whoami) on 127.0.0.1:$port. From your computer:"
echo "  gcloud compute ssh $(whoami)@<vm> --zone <zone> -- -L $port:127.0.0.1:$port   then open http://127.0.0.1:$port"
