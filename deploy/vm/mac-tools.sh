#!/usr/bin/env bash
# Two commands for the Mac that drives the lab VM, so nobody pastes long lines again:
#   montara-update   update Montara on the VM to the latest main and restart it
#   montara-tunnel   open a public https address to Montara (keep the window open)
#   montara-disk     disk use on the VM; 'montara-disk clean ...' prints what it would remove (--apply removes)
#   montara-runs     timing record of every finished job on the VM (~/montara-runs.jsonl)
#   montara-start    switch the VM on if needed, wait for Montara, connect and open http://127.0.0.1:8101 (--public: Cloudflare address)
#   montara-stop     switch the VM off now
#   montara-autostop once: the VM switches itself off after 1 h without web use and 2 h without SSH typing
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

cat > "$BIN/montara-diagnose" <<SCRIPT
#!/bin/bash
# What the server is doing right now (latest session, processes, last log lines). Paste it to Claude.
gcloud compute ssh $VM --zone $ZONE --project $PROJECT --command 'sudo -u jm -H bash -c "cd ~/montara && python3 deploy/vm/diagnose.py"'
SCRIPT
chmod +x "$BIN/montara-diagnose"

cat > "$BIN/montara-disk" <<SCRIPT
#!/bin/bash
# Disk use of Montara on the VM (montara-disk report), or a cleanup that only prints what it
# would remove until you add --apply:  montara-disk clean --session ID --mixer-days 2
ARGS="\${*:-report}"
gcloud compute ssh $VM --zone $ZONE --project $PROJECT --command "sudo -u jm -H python3 /home/jm/montara/deploy/vm/disk.py \$ARGS"
SCRIPT
chmod +x "$BIN/montara-disk"

cat > "$BIN/montara-runs" <<SCRIPT
#!/bin/bash
# Timing record of every finished Montara job on the VM, saved in ~/montara-runs.jsonl.
# Paste the file to Claude (or attach it) to add it to docs/lab/RUNS.md in main.
gcloud compute ssh $VM --zone $ZONE --project $PROJECT --command 'sudo -u jm -H bash -c "cd ~/montara && python3 deploy/vm/run_history.py --data ~/montara-data --root ~/montara"' > "\$HOME/montara-runs.jsonl"
python3 - "\$HOME/montara-runs.jsonl" <<'PY'
import json, sys
for line in open(sys.argv[1]):
    r = json.loads(line); s = r.get("stages_s", {})
    if r.get('mode') == 'Session':
        print(f"{(r.get('date') or '')[:16]}  Session  {r.get('songs')} songs ({r.get('audio_min')} min of music, {r.get('tracks')} tracks): detect {s.get('detect')} s · export {s.get('render')} s")
        continue
    print(f"{(r.get('date') or '')[:16]}  {r.get('mode')}  {r.get('project')}: ingest {s.get('ingest')} s · sync {s.get('sync')} s · edit {s.get('edit')} s · export {s.get('export')} s · total {r.get('engine_total_s')} s")
PY
echo; echo "Saved in ~/montara-runs.jsonl. Attach it to Claude to add it to docs/lab/RUNS.md."
SCRIPT

cat > "$BIN/montara-start" <<SCRIPT
#!/bin/bash
# Switches the lab VM on (if it is off), waits for Montara, connects this computer and opens it in the browser.
state=\$(gcloud compute instances describe $VM --zone $ZONE --project $PROJECT --format="value(status)")
if [ "\$state" != "RUNNING" ]; then
  echo "Switching the lab machine on…"
  gcloud compute instances start $VM --zone $ZONE --project $PROJECT --quiet || exit 1
  echo "Waiting for Montara to start (about a minute)…"
  for i in \$(seq 40); do
    gcloud compute ssh $VM --zone $ZONE --project $PROJECT --quiet --command 'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8101/' 2>/dev/null | grep -q 401 && break
    sleep 5
  done
fi
# Public address only when asked (montara-start --public); otherwise this computer only.
[ "\${1:-}" = "--public" ] && exec "$BIN/montara-tunnel"
# Another window already holds the connection: a second one could only fail again and again.
connected() { lsof -nP -iTCP:8101 -sTCP:LISTEN >/dev/null 2>&1; }
if connected; then
  echo "Montara is already connected in another window: http://127.0.0.1:8101"
  open "http://127.0.0.1:8101" 2>/dev/null
  exit 0
fi
echo "Montara: http://127.0.0.1:8101  (keep this window open; Ctrl+C closes the connection)"
(sleep 4; open "http://127.0.0.1:8101" 2>/dev/null) &
trap 'echo; echo "Connection closed."; exit 0' INT
while true; do   # a dropped connection comes back by itself
  gcloud compute ssh $VM --zone $ZONE --project $PROJECT -- -N -L 8101:127.0.0.1:8101 \
    -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes
  connected && { echo "Montara is already connected in another window; closing this one."; exit 0; }
  echo "Connection lost; reconnecting in 3 s (Ctrl+C to stop)…"; sleep 3
done
SCRIPT

cat > "$BIN/montara-stop" <<SCRIPT
#!/bin/bash
# Switches the lab VM off now (it also switches itself off when nobody uses it).
gcloud compute instances stop $VM --zone $ZONE --project $PROJECT --quiet && echo "Lab machine off. Start it again with: montara-start"
SCRIPT

cat > "$BIN/montara-autostop" <<SCRIPT
#!/bin/bash
# Once: the lab VM switches itself off after WEB minutes without Montara use (60) and SSH minutes without typing (120).
gcloud compute ssh $VM --zone $ZONE --project $PROJECT --command "sudo bash /home/jm/montara/deploy/vm/install_idle_shutdown.sh \${1:-60} \${2:-120}"
SCRIPT

chmod +x "$BIN/montara-update" "$BIN/montara-tunnel" "$BIN/montara-runs" "$BIN/montara-start" "$BIN/montara-stop" "$BIN/montara-autostop"
grep -q 'montara-tools/bin' "$HOME/.zshrc" 2>/dev/null || echo 'export PATH="$HOME/.montara-tools/bin:$PATH"' >> "$HOME/.zshrc"
echo "Installed: montara-start, montara-stop, montara-update, montara-tunnel, montara-runs, montara-autostop."
echo "Close this Terminal window and open a new one, then type one of them."
