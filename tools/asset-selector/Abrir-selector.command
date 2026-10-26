#!/bin/zsh
cd "${0:A:h}"
repo_root="${0:A:h}/../.."
if ! curl -fsS http://127.0.0.1:8097/api/state >/dev/null; then
  "$repo_root/.venv/bin/python" server.py > /tmp/montara-selector.log 2>&1 &
  sleep 1
fi
open http://127.0.0.1:8097/
