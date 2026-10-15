#!/bin/bash
# Sammelt Build-Diagnose, auch bei Fehlern.
set -uo pipefail
cd "$(dirname "$0")/.."

OUT="build-error-analysis.txt"
{
    echo "=== WOTS2 Build-Analyse ==="
    echo "Datum: $(date)"
    echo "Host:  $(uname -a)"
    echo
    echo "=== Git-Stand ==="
    git log -1 --oneline 2>/dev/null || true
    git status --short 2>/dev/null || true
    echo
    echo "=== Toolchain ==="
    aarch64-linux-gnu-gcc --version 2>/dev/null | head -1
    cmake --version 2>/dev/null | head -1
    echo
    echo "=== Build-Verzeichnis ==="
    ls -la build/ 2>/dev/null | head -30 || echo "(kein build/)"
    echo
    echo "=== Ninja-Log (letzte 200 Zeilen) ==="
    [ -f build/.ninja_log ] && tail -200 build/.ninja_log
    echo
    echo "=== Kompilierte Patches ==="
    for f in patches/*.py; do
        echo "--- $f"
        head -5 "$f"
    done
} > "$OUT" 2>&1

echo "Fehleranalyse: $OUT"
