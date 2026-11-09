#!/bin/bash
# Downloaded with the exact installer for this Montara build.
set -eu
cd "$(dirname "$0")"
pause() { echo; read -r -p "Press Enter to close this window…" _ || true; }
trap pause EXIT
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

read -r MONTARA_REF < SOURCE_COMMIT
read -r MONTARA_EXPECTED_ENGINE < EDITOR_COMMIT
if [[ ! "$MONTARA_REF" =~ ^[0-9a-f]{40}$ || ! "$MONTARA_EXPECTED_ENGINE" =~ ^[0-9a-f]{40}$ ]]; then
  echo "This download is incomplete. Download Companion again from Montara."
  exit 1
fi
export MONTARA_REF MONTARA_EXPECTED_ENGINE MONTARA_NO_SHELL_SETUP=1 MONTARA_REQUIRE_CLOSED=1
bash ./install.sh --video

# The installer starts Companion in this window. Its launcher also makes
# reopening it possible via Spotlight without reinstalling or using commands.
