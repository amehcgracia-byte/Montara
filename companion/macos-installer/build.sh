#!/bin/bash
# Run on macOS with Xcode command line tools to produce a native Installer .pkg.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
SOURCE="$(git rev-parse HEAD)"
ENGINE="$(git ls-tree HEAD engine | awk '{print $3}')"
[[ "$SOURCE" =~ ^[a-f0-9]{40}$ && "$ENGINE" =~ ^[a-f0-9]{40}$ ]] || exit 1
TEMP="$(mktemp -d)"
trap 'rm -rf "$TEMP"' EXIT
mkdir -p "$TEMP/scripts" "$TEMP/out"
cp companion/install.sh "$TEMP/scripts/install.sh"
sed -e "s/__MONTARA_COMMIT__/$SOURCE/g" -e "s/__ENGINE_COMMIT__/$ENGINE/g" \
  companion/macos-installer/postinstall.in > "$TEMP/scripts/postinstall"
chmod 755 "$TEMP/scripts/postinstall"
pkgbuild --nopayload --identifier "website.talesforthetillerman.montara.companion" \
  --version "1.0.0" --install-location "/" --scripts "$TEMP/scripts" \
  "$TEMP/out/component.pkg"
mkdir -p dist
# productbuild produces a standard macOS Installer file, not a ZIP or script.
productbuild --package "$TEMP/out/component.pkg" "dist/Montara-Companion-${SOURCE:0:8}.pkg"
echo "dist/Montara-Companion-${SOURCE:0:8}.pkg"
