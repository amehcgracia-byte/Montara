#!/usr/bin/env bash
# Two commands for the Mac that drives the lab VM, so nobody pastes long lines again:
#   montara-update   update Montara on the VM to the latest main and restart it
#   montara-tunnel   open a public https address to Montara (keep the window open)
#   montara-runs     timing record of every finished job on the VM (~/montara-runs.jsonl)
# Install: curl -fsSL https://raw.githubusercontent.com/amehcgracia-byte/Montara/main/deploy/vm/mac-tools.sh | bash
set -euo pipefail
BIN="$HOME/.montara-tools/bin"
mkdir -p "$BIN"
VM="montara-test"; ZONE="europe-west3-a"; PROJECT="montara-pruebas-10292226"

cat > "$BIN/montara-update" <<SCRIPT
#!/bin/bash
# Updates the jm installation on the VM to origin/main and restarts it.
gcloud compute ssh $VM --zone $ZONE --project $PROJECT --command 'sudo -u jm -H bash -c "cd ~/montara && git fetch -q --no-recurse-submodules origin +refs/heads/main:refs/remotes/origin/main && git checkout -q -f -B main origin/main && git submodule update --init --recursive -q && MONTARA_OFFLINE=1 bash deploy/vm/user_install.sh main 8101 > ~/update.log 2>&1; tail -2 ~/update.log; echo; echo Montara now at: \\\$(git log --oneline -1)"'
echo "Reload Montara in Chrome with Cmd+Shift+R."
SCRIPT

cat > "$BIN/montara-tunnel" <<SCRIPT
#!/bin/bash
# Public https address to Montara on the VM. Keep this window open; Ctrl+C closes it.
PORT=\${1:-8101}
echo "Opening the tunnel… look below for a line with https://….trycloudflare.com"
gcloud compute ssh $VM --zone $ZONE --project $PROJECT -- "[ -x /tmp/cloudflared ] || curl -fsSL -o /tmp/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 && chmod +x /tmp/cloudflared; /tmp/cloudflared tunnel --url http://127.0.0.1:\$PORT 2>&1 | grep --line-buffered -E 'trycloudflare.com|ERR'"
SCRIPT

cat > "$BIN/montara-runs" <<SCRIPT
#!/bin/bash
# Timing record of every finished Montara job on the VM, saved in ~/montara-runs.jsonl.
# Paste the file to Claude (or attach it) to add it to docs/lab/RUNS.md in main.
gcloud compute ssh $VM --zone $ZONE --project $PROJECT --command 'sudo -u jm -H bash -c "cd ~/montara && python3 deploy/vm/run_history.py --data ~/montara-data --root ~/montara"' > "\$HOME/montara-runs.jsonl"
python3 - "\$HOME/montara-runs.jsonl" <<'PY'
import json, sys
for line in open(sys.argv[1]):
    r = json.loads(line); s = r.get("stages_s", {})
    print(f"{(r.get('date') or '')[:16]}  {r.get('mode')}  {r.get('project')}: ingest {s.get('ingest')} s · sync {s.get('sync')} s · edit {s.get('edit')} s · export {s.get('export')} s · total {r.get('engine_total_s')} s")
PY
echo; echo "Saved in ~/montara-runs.jsonl. Attach it to Claude to add it to docs/lab/RUNS.md."
SCRIPT

chmod +x "$BIN/montara-update" "$BIN/montara-tunnel" "$BIN/montara-runs"
grep -q 'montara-tools/bin' "$HOME/.zshrc" 2>/dev/null || echo 'export PATH="$HOME/.montara-tools/bin:$PATH"' >> "$HOME/.zshrc"
echo "Installed: montara-update, montara-tunnel and montara-runs."
echo "Close this Terminal window and open a new one, then type one of them."
