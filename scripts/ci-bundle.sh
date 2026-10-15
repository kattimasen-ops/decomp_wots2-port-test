#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."

DIST="dist"
PORT="$DIST/wots2-rk3326"
rm -rf "$DIST"
mkdir -p "$PORT/wots2/libs.aarch64"

# Binary + Config
cp build/wots2              "$PORT/wots2/wots2"
[ -f port.ini ] && cp port.ini "$PORT/wots2/port.ini"

# Mitgelieferte Bibliotheken (falls dynamisch gelinkt)
for lib in build/libs.aarch64/*.so*; do
    [ -f "$lib" ] && cp -a "$lib" "$PORT/wots2/libs.aarch64/"
done

# Launcher
cp WOTS2.sh "$PORT/WOTS2.sh"
chmod +x "$PORT/WOTS2.sh" "$PORT/wots2/wots2"

# README in Bundle
cp README.md "$PORT/README.md" 2>/dev/null || true

# Extracted-Ordner leer anlegen (wird beim Erststart befüllt)
mkdir -p "$PORT/wots2/extracted"

# Rechte korrigieren
find "$PORT" -type d -exec chmod 755 {} \;
find "$PORT" -type f -exec chmod 644 {} \;
chmod +x "$PORT/WOTS2.sh" "$PORT/wots2/wots2"

cd "$DIST"
tar -czf "wots2-rk3326.tar.gz" "wots2-rk3326"
echo "Bundle: $DIST/wots2-rk3326.tar.gz"
