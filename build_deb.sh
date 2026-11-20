#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

PKG="opencartazero"
VER="1.1.0"
ARCH="arm64"
STAGE="build/staging-${PKG}"
DEB_OUT="build/${PKG}_${VER}_${ARCH}.deb"

rm -rf "$STAGE"
mkdir -p \
  "$STAGE/DEBIAN" \
  "$STAGE/usr/share/APPLaunch/applications" \
  "$STAGE/usr/share/APPLaunch/bin" \
  "$STAGE/usr/share/APPLaunch/share/images" \
  "$STAGE/usr/share/APPLaunch/apps/${PKG}"

cat > "$STAGE/DEBIAN/control" <<'EOF'
Package: opencartazero
Version: 1.1.0
Architecture: arm64
Maintainer: Gurkenwerfer <stefan@gurk.dev>
Section: utils
Priority: optional
Depends: python3, python3-pygame, python3-gi, bluez
Homepage: https://github.com/stefexec/OpenCartaZero
Description: Focus V Carta Sport & Carta 2 BLE controller for Cardputer Zero
 Native Focus V Carta Sport and Carta 2 Bluetooth LE controller for the
 M5Stack Cardputer Zero using BlueZ D-Bus GATT, evdev, and pygame framebuffer.
EOF

install -m 0644 opencartazero.desktop "$STAGE/usr/share/APPLaunch/applications/opencartazero.desktop"
install -m 0755 opencartazero "$STAGE/usr/share/APPLaunch/bin/opencartazero"
install -m 0644 opencartazero.png "$STAGE/usr/share/APPLaunch/share/images/opencartazero.png"
install -m 0755 opencartazero.py "$STAGE/usr/share/APPLaunch/apps/${PKG}/opencartazero.py"

dpkg-deb --root-owner-group -b "$STAGE" "$DEB_OUT"
rm -rf "$STAGE"
echo "Built $DEB_OUT"
