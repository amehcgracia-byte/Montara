#!/bin/bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sha="$(git -C "$here" rev-parse HEAD:engine)"
bundle="/opt/montara/bundles/engine-$sha"
test -d "$bundle" || { echo "Pinned bundle missing" >&2; exit 1; }
if ! getent passwd montara-i26-client >/dev/null; then
  sudo -n useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin montara-i26-client
fi
uid="$(id -u montara-i26-client)"
webuid="$(id -u)"
test "$uid" -gt 0
test "$uid" != "$webuid"
sudo -n install -d -o root -g root -m 0755 /opt/montara /opt/montara/broker /opt/montara/broker/urano
for item in __init__.py project_catalog.py job_recovery_ledger.py restricted_systemd_broker.py restricted_broker_ipc.py; do
  sudo -n install -o root -g root -m 0644 "$here/urano/$item" "/opt/montara/broker/urano/$item"
done
for item in private_broker_service.py private_broker_worker.py private_broker_client.py; do
  sudo -n install -o root -g root -m 0644 "$here/urano/$item" "/opt/montara/broker/$item"
done
sudo -n install -d -o root -g root -m 0700 /var/lib/montara-i26-broker
unit="$(mktemp)"
trap 'rm -f "$unit"' EXIT
cat > "$unit" <<EOF
[Unit]
Description=Montara I26 private restricted Engine broker LAB (not public)
After=local-fs.target
ConditionPathIsDirectory=$bundle

[Service]
Type=simple
User=root
Group=montara-i26-client
UMask=0077
WorkingDirectory=/opt/montara/broker
ExecStart=/usr/bin/python3 /opt/montara/broker/private_broker_service.py --bundle=$bundle --trusted-uid=$uid --web-uid=$webuid
RuntimeDirectory=montara-i26-broker
RuntimeDirectoryMode=0750
StateDirectory=montara-i26-broker
StateDirectoryMode=0700
NoNewPrivileges=yes
ProtectHome=yes
ProtectSystem=strict
ReadWritePaths=/run/montara-i26-broker /var/lib/montara-i26-broker
PrivateTmp=yes
PrivateDevices=yes
RestrictSUIDSGID=yes
KillMode=control-group
TimeoutStopSec=5s
Restart=on-failure
RestartSec=2s

[Install]
WantedBy=multi-user.target
EOF
sudo -n install -o root -g root -m 0644 "$unit" /etc/systemd/system/montara-i26-broker.service
sudo -n systemctl daemon-reload
sudo -n systemctl enable --now montara-i26-broker.service
echo "I26_SERVICE=$(sudo -n systemctl is-active montara-i26-broker.service)"
echo "I26_TRUSTED_UID=$uid WEB_UID=$webuid"
sudo -n stat -c 'SOCKET %U %G %a %n' /run/montara-i26-broker/control.sock
sudo -n stat -c 'DBDIR %U %G %a %n' /var/lib/montara-i26-broker

