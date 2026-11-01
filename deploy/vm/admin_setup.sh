#!/usr/bin/env bash
# Montara shared lab VM, one-time admin setup (Ubuntu 24.04 LTS x86_64, run with sudo).
# Installs system tools only; Montara itself is installed per user by user_install.sh.
# Creates two unprivileged accounts with separate HOME, data, caches and ports:
#   jm  -> main or his branch, port 8101
#   fer -> fernando/continuacion-montara, port 8102
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run with sudo"; exit 1; }
[ "$(uname -m)" = x86_64 ] || { echo "This setup is validated for x86_64 only"; exit 1; }

apt-get update
apt-get install -y --no-install-recommends \
  git ca-certificates curl ffmpeg fontconfig fonts-dejavu-core fonts-liberation2 \
  libgl1 libglib2.0-0 libgomp1 nodejs npm util-linux jq

for user in jm fer; do
  id "$user" >/dev/null 2>&1 || adduser --disabled-password --gecos "" "$user"
  chmod 750 "/home/$user"                 # one researcher cannot read the other's data
  loginctl enable-linger "$user"          # their systemd --user service survives logout
done

# One shared lock for heavy work: a 2 vCPU machine must not run two benchmarks at once.
install -d -m 1777 /var/lock/montara
touch /var/lock/montara/bench.lock && chmod 666 /var/lock/montara/bench.lock
install -m 755 "$(dirname "$0")/bench_lock.sh" /usr/local/bin/montara-bench
echo "Admin setup done. Next, as each user: bash deploy/vm/user_install.sh <branch> <port>"
