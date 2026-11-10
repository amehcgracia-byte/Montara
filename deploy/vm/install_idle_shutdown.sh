#!/usr/bin/env bash
# Run with sudo on the lab VM. A check every 20 min; 120 min of real inactivity.
#   sudo bash deploy/vm/install_idle_shutdown.sh [idle_minutes=120]
# Existing SSH sessions and running engine/benchmark work block shutdown.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
install -d -m 700 /var/lib/montara-idle
install -m 755 "$here/idle_shutdown.sh" /usr/local/bin/montara-idle-shutdown
cat > /etc/systemd/system/montara-idle.service <<UNIT
[Unit]
Description=Power Montara lab VM off after inactivity
[Service]
Type=oneshot
Environment=MONTARA_IDLE_MINUTES=${1:-120}
Environment=MONTARA_IDLE_GRACE_MINUTES=120
ExecStart=/usr/local/bin/montara-idle-shutdown
UNIT
cat > /etc/systemd/system/montara-idle.timer <<UNIT
[Unit]
Description=Check Montara inactivity every 20 minutes
[Timer]
OnBootSec=20min
OnUnitActiveSec=20min
AccuracySec=1min
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now montara-idle.timer
systemctl restart montara-idle.timer
echo "Idle watchdog: 20 min checks; ${1:-120} min inactive; 120 min boot grace; active SSH/engine prevents poweroff."
echo "Logs: journalctl -u montara-idle"
