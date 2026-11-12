#!/bin/bash
# Disposable lab target: proves systemd kills both worker and a child process.
set -euo pipefail
[[ "${1-}" == --i17-lab && "$#" == 9 ]] || exit 64
shift
# Actual FFmpeg descendant: infinite tiny synthetic source, NO video files.
# Must share the same service cgroup as real Engine and be reaped on STOP.
/usr/bin/ffmpeg -nostdin -hide_banner -loglevel error -re \
  -threads 1 -filter_threads 1 -filter_complex_threads 1 \
  -f lavfi -i anullsrc=r=8000:cl=mono \
  -c:a pcm_s16le -f null - >/dev/null 2>&1 &
exec /usr/bin/unshare --user --map-root-user --mount --net --pid --fork -- "$@"
