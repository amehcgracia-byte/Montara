#!/usr/bin/env bash
# Powers the lab VM off when nobody uses Montara (no compute charge while off; the disk stays).
# Runs every 5 minutes from a systemd timer (install_idle_shutdown.sh). It stops the VM only if:
#   - the machine has been up for at least GRACE minutes,
#   - no Montara of any lab user saw real activity for IDLE minutes (~/montara-data/.last-activity),
#   - no engine work is running (ffmpeg, ffprobe, the mixer worker),
#   - no benchmark holds the lab lock (montara-bench).
# Start it again from the Mac with: montara-start
set -u
IDLE_MIN="${MONTARA_IDLE_MINUTES:-30}"
GRACE_MIN="${MONTARA_IDLE_GRACE_MINUTES:-15}"
now=$(date +%s)
up=$(cut -d. -f1 /proc/uptime)
[ "$up" -ge $((GRACE_MIN * 60)) ] || { echo "just started (${up}s): keep"; exit 0; }
if pgrep -x ffmpeg >/dev/null || pgrep -x ffprobe >/dev/null || pgrep -f "mixer_adapter.session" >/dev/null; then
  echo "engine busy: keep"; exit 0
fi
if [ -e /var/lock/montara/bench.lock ] && ! flock -n /var/lock/montara/bench.lock true; then
  echo "benchmark running: keep"; exit 0
fi
latest=0
for f in ${MONTARA_IDLE_HOMES:-/home/*}/montara-data/.last-activity; do
  [ -f "$f" ] || continue
  t=$(cat "$f" 2>/dev/null || echo 0)
  [ "$t" -gt "$latest" ] 2>/dev/null && latest=$t
done
idle=$(( (now - latest) / 60 ))
if [ "$latest" -gt 0 ] && [ "$idle" -lt "$IDLE_MIN" ]; then
  echo "last activity ${idle} min ago: keep"; exit 0
fi
echo "idle ${idle} min (limit ${IDLE_MIN}), engine quiet: powering off"
logger -t montara-idle "powering off after ${idle} min without activity"
${MONTARA_IDLE_POWEROFF:-systemctl poweroff}
