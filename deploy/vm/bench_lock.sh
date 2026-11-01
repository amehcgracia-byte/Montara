#!/usr/bin/env bash
# Run a heavy command (render, E2E, benchmark) holding the shared lab lock.
# Usage: montara-bench <experiment_id> <command...>
# A second researcher waits instead of running at the same time; the holder is shown.
set -euo pipefail
id=${1:?experiment_id, e.g. MTLAB-20261030-001-jm-gcp}; shift
lock=/var/lock/montara/bench.lock
exec 9>>"$lock"
if ! flock -n 9; then
  echo "Lab busy: $(cat /var/lock/montara/holder 2>/dev/null || echo unknown). Waiting…"
  flock 9
fi
echo "$id $(whoami) since $(date -u +%FT%TZ)" > /var/lock/montara/holder
trap 'rm -f /var/lock/montara/holder' EXIT
"$@"
