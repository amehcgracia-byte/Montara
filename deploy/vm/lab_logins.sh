#!/usr/bin/env bash
# One-off admin step (sudo) on the lab VM, offline (no GitHub on the VM):
#  1. copies the updated deploy/*.py (login name via MONTARA_PREVIEW_USER) into jm's checkout,
#     sets jm's login name to "Chema Gracia" and restarts his service;
#  2. creates fer's install from a copy of jm's checkout (port 8102, login "Fer", new password,
#     printed once in ~fer/install.log).
# Usage from a fresh checkout copied to the VM:  sudo bash <copy>/deploy/vm/lab_logins.sh <copy>
set -euo pipefail
src=${1:?path of the copied checkout}
for f in entry.py healthcheck.py restart_check.py vm/user_install.sh; do
  install -o jm -g jm -m 644 "$src/deploy/$f" "/home/jm/montara/deploy/$f"
done
envf=/home/jm/.config/montara/env
sed -i '/^MONTARA_PREVIEW_USER=/d' "$envf"
echo 'MONTARA_PREVIEW_USER="Chema Gracia"' >> "$envf"
sudo -u jm XDG_RUNTIME_DIR="/run/user/$(id -u jm)" systemctl --user restart montara.service
echo "jm restarted"

if [ ! -d /home/fer/montara ]; then
  cp -a /home/jm/montara /home/fer/montara && rm -rf /home/fer/montara/.venv
  chown -R fer:fer /home/fer/montara
fi
sudo -u fer -H bash -c 'cd ~ && nohup env MONTARA_OFFLINE=1 MONTARA_GENERATE_PASSWORD=1 MONTARA_LOGIN_USER=Fer bash montara/deploy/vm/user_install.sh claude/jupiter-gcp-vm 8102 > install.log 2>&1 &'
echo "fer install started (log: /home/fer/install.log)"
