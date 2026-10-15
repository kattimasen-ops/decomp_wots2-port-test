#!/usr/bin/env bash
set +e

{
    echo "================================================================"
    echo "WOTS2 RK3326 Build-Fehleranalyse"
    echo "Datum: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "================================================================"
    echo ""
    echo "== CMake:"
    cmake --version 2>/dev/null | head -n 1
    echo ""
    echo "== SDL2:"
    ls -la "$SDL2_INSTALL/lib/" 2>/dev/null || echo "  (kein lib-Verzeichnis)"
    SDL2_LIB=$(find "$SDL2_INSTALL/lib" -maxdepth 1 \( -name "libSDL2*.so*" \) 2>/dev/null | head -n 1)
    if [ -n "$SDL2_LIB" ]; then
        aarch64-linux-gnu-strings "$SDL2_LIB" | grep -q "Async pageflip rejected" \
            && echo "  OK: Pageflip-Patch" \
            || echo "  FEHLT: Pageflip-Patch"
    fi
    echo ""
    echo "== Build-Artefakt:"
    if [ -f dist/wots2 ]; then
        file dist/wots2
        aarch64-linux-gnu-readelf -d dist/wots2 | grep NEEDED || true
    else
        echo "  FEHLT: dist/wots2"
    fi
} > build-error-analysis.txt

cat build-error-analysis.txt
