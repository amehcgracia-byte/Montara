#!/usr/bin/env bash
# Run once with sudo on the lab VM: installs the idle watchdog as a systemd timer (every 5 min).
#   sudo bash deploy/vm/install_idle_shutdown.sh [web_idle_minutes=60] [ssh_idle_minutes=120]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
install -m 755 "$here/idle_shutdown.sh" /usr/local/bin/montara-idle-shutdown
cat > /etc/systemd/system/montara-idle.service <<UNIT
[Unit]
Description=Power the Montara lab VM off when nobody uses it
[Service]
Type=oneshot
Environment=MONTARA_IDLE_MINUTES=${1:-60}
Environment=MONTARA_SSH_IDLE_MINUTES=${2:-120}
ExecStart=/usr/local/bin/montara-idle-shutdown
UNIT
cat > /etc/systemd/system/montara-idle.timer <<UNIT
[Unit]
Description=Check every 5 minutes whether Montara is idle
[Timer]
OnBootSec=15min
OnUnitActiveSec=5min
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now montara-idle.timer
echo "Idle watchdog on: the VM powers off after ${1:-60} min without Montara use and ${2:-120} min without typing in SSH. Logs: journalctl -u montara-idle"
