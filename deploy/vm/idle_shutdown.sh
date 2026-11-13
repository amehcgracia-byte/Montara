#!/usr/bin/env bash
# Montara lab auto-stop: protect real SSH connections, web activity and engine work.
# Runs via systemd every 20 min; requires 120 min idle and 120 min boot grace.
set -euo pipefail
IDLE_MIN="${MONTARA_IDLE_MINUTES:-120}"
GRACE_MIN="${MONTARA_IDLE_GRACE_MINUTES:-120}"
now=$(date +%s)
up=$(cut -d. -f1 /proc/uptime)
boot=$((now - up))
state_dir=/var/lib/montara-idle
state_file="$state_dir/last-active"
mkdir -p -m 700 "$state_dir"
remember_activity() {
  printf '%s\n' "$now" > "$state_file.tmp.$$"
  mv -f "$state_file.tmp.$$" "$state_file"
}
keep() { echo "$1: keep"; exit 0; }
if (( up < GRACE_MIN * 60 )); then keep "boot grace $((up / 60)) min of $GRACE_MIN"; fi

# Private per-owner Engine jobs are transient systemd units, not necessarily
# ffmpeg processes. A quiet worker can still hold an owner project/session.
# Never stop the VM while even one such unit is active: only the authorized
# broker may prove it is safe to release that owner-bound worker.
# Do not "remember activity" for this guard: an idle-only worker can be
# released later without restarting the full two-hour inactivity clock.
if ! units=$(systemctl --system list-units \
  --type=service --state=active --no-legend --plain \
  'montara-i*-job-*.service' 2>/dev/null); then
  keep "private worker unit status unavailable (fail safe)"
fi
if [[ -n "$units" ]]; then
  keep "private owner worker active; broker must release it before shutdown"
fi

# Real engine work or a held lab benchmark lock must never be interrupted.
if pgrep -x ffmpeg >/dev/null || pgrep -x ffprobe >/dev/null || pgrep -f "mixer_adapter.session" >/dev/null; then
  remember_activity
  keep "engine active"
fi
if [[ -e /var/lock/montara/bench.lock ]] && ! flock -n /var/lock/montara/bench.lock true; then
  remember_activity
  keep "benchmark lock held"
fi

# Connected SSH sessions count as activity even when nobody is typing.
# If the query fails, retain the VM (fail safe).
if ! ssh_sessions=$(ss -H -tn state established '( sport = :22 )'); then
  keep "SSH status unavailable (fail safe)"
fi
if [[ -n "$ssh_sessions" ]]; then
  remember_activity
  keep "SSH connection established"
fi

# Remember the last moment of SSH or engine activity across checks, but
# never use an activity timestamp older than the present boot.
latest=$boot
if [[ -f "$state_file" ]]; then
  last=$(cat "$state_file" 2>/dev/null || echo 0)
  if [[ "$last" =~ ^[0-9]+$ ]] && (( last > latest )); then latest=$last; fi
fi

# Each Montara instance writes its own .last-activity marker.
# New layouts include /home/montara-main/data and *-data, not just montara-data.
web_paths=0
while IFS= read -r -d '' f; do
  web_paths=$((web_paths+1))
  stamp=$(cat "$f" 2>/dev/null || echo 0)
  if [[ ! "$stamp" =~ ^[0-9]+$ ]]; then
    stamp=$(stat -c %Y "$f" 2>/dev/null || echo 0)
  fi
  if [[ "$stamp" =~ ^[0-9]+$ ]] && (( stamp > latest )); then latest=$stamp; fi
done < <(find /home -mindepth 2 -maxdepth 4 -type f -name .last-activity -print0 2>/dev/null)
if (( latest > now )); then latest=$now; fi
inactive=$(((now - latest) / 60))
if (( inactive < IDLE_MIN )); then
  keep "no SSH/engine; last activity $inactive min ago (<$IDLE_MIN); web markers $web_paths"
fi
echo "inactive $inactive min (>=$IDLE_MIN), no SSH, engine or benchmark: poweroff"
if [[ "${MONTARA_IDLE_DRY_RUN:-0}" == "1" ]]; then
  echo "DRY RUN: no poweroff"
  exit 0
fi
logger -t montara-idle "powering off after $inactive min of total inactivity"
systemctl poweroff
