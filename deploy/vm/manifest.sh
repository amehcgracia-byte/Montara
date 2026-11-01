#!/usr/bin/env bash
# Print a hardware/version manifest (JSON) to attach to every benchmark. No secrets, no paths.
set -euo pipefail
root=${1:-$HOME/montara}
md() { curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/$1" 2>/dev/null || true; }
jq -n \
  --arg montara "$(git -C "$root" rev-parse HEAD)" \
  --arg branch "$(git -C "$root" rev-parse --abbrev-ref HEAD)" \
  --arg dirty "$(git -C "$root" status --porcelain | wc -l)" \
  --arg engine "$(git -C "$root/engine" rev-parse HEAD)" \
  --arg mixer "$(git -C "$root/mixer" rev-parse HEAD)" \
  --arg ffmpeg "$(ffmpeg -version | head -1)" \
  --arg python "$("$root/.venv/bin/python" -V 2>&1)" \
  --arg os "$(. /etc/os-release; echo "$PRETTY_NAME")" --arg kernel "$(uname -r)" --arg arch "$(uname -m)" \
  --arg cpu "$(lscpu | sed -n 's/^Model name: *//p')" --arg vcpus "$(nproc)" \
  --arg mem_gib "$(awk '/MemTotal/ {printf "%.1f", $2/1048576}' /proc/meminfo)" \
  --arg disk_free_gib "$(df -BG --output=avail "$HOME" | tail -1 | tr -dc 0-9)" \
  --arg machine_type "$(md machine-type | sed 's#.*/##')" --arg zone "$(md zone | sed 's#.*/##')" \
  --arg utc "$(date -u +%FT%TZ)" \
  '{utc:$utc, montara:$montara, branch:$branch, dirty_files:($dirty|tonumber), engine:$engine, mixer:$mixer,
    ffmpeg:$ffmpeg, python:$python, os:$os, kernel:$kernel, arch:$arch, cpu:$cpu, vcpus:($vcpus|tonumber),
    mem_gib:($mem_gib|tonumber), disk_free_gib:($disk_free_gib|tonumber), gcp_machine_type:$machine_type, gcp_zone:$zone}'
