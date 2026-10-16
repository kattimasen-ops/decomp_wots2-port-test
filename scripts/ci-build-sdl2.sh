#!/usr/bin/env bash
set -euo pipefail

SDL2_TAG=release-2.30.10
SRC=/tmp/SDL2-src
BUILD=/tmp/sdl2-build

rm -rf "$SRC" "$BUILD"
mkdir -p "$SRC"
curl -fL --retry 3 -o /tmp/sdl2.tar.gz \
    "https://github.com/libsdl-org/SDL/archive/refs/tags/${SDL2_TAG}.tar.gz"
tar -xzf /tmp/sdl2.tar.gz -C "$SRC" --strip-components=1

# ── KMSDRM-Check erzwingen ────────────────────────────────────────────
python3 "$GITHUB_WORKSPACE/patches/sdl2-force-kmsdrm.py" \
    "$SRC/cmake/sdlchecks.cmake"

# ── KMSDRM Window-Flag-Patch (NEU) ────────────────────────────────────
# Muss VOR dem Pageflip-Patch laufen, weil beide dieselbe Datei-Gruppe
# betreffen. Der Window-Flag-Patch zielt auf SDL_kmsdrmvideo.c, der
# Pageflip-Patch auf SDL_kmsdrmopengles.c — kein Konflikt, aber
# Reihenfolge bleibt deterministisch.
echo "== SDL2 KMSDRM Window-Flag-Patch =="
python3 "$GITHUB_WORKSPACE/patches/sdl2-kmsdrm-window.py" "$SRC"

# ── Diagnose: relevanter Ausschnitt aus SDL_kmsdrmvideo.c ─────────────
echo "== Diagnose: KMSDRM_CreateWindow (erste 80 Zeilen ab Signatur) =="
if [ -f "$SRC/src/video/kmsdrm/SDL_kmsdrmvideo.c" ]; then
    awk '
        /KMSDRM_CreateWindow[[:space:]]*\(/ { found=1 }
        found { print; count++ }
        count >= 80 { exit }
    ' "$SRC/src/video/kmsdrm/SDL_kmsdrmvideo.c" || true
else
    echo "WARNUNG: SDL_kmsdrmvideo.c nicht gefunden."
fi
echo "== Ende Diagnose =="

# ── Pageflip-Patch anwenden ──────────────────────────────────────────
python3 "$GITHUB_WORKSPACE/patches/sdl2-pageflip.py" \
    "$SRC/src/video/kmsdrm/SDL_kmsdrmopengles.c"

# ── Verifikation Pageflip-Patch im Quellcode ─────────────────────────
if ! grep -q "Async pageflip rejected" \
     "$SRC/src/video/kmsdrm/SDL_kmsdrmopengles.c"; then
    echo "FEHLER: Pageflip-Patch nicht im Quellcode."
    exit 1
fi
echo "OK: Pageflip-Patch im Quellcode."

# ── Verifikation Window-Flag-Patch im Quellcode ──────────────────────
if grep -q "WOTS2-KMSDRM-WINDOW-FLAG" \
     "$SRC/src/video/kmsdrm/SDL_kmsdrmvideo.c"; then
    echo "OK: Window-Flag-Patch im Quellcode."
else
    echo "FEHLER: Window-Flag-Patch nicht im Quellcode."
    exit 1
fi

# ── CMake konfigurieren ───────────────────────────────────────────────
cmake -S "$SRC" -B "$BUILD" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$GITHUB_WORKSPACE/cmake/aarch64-arkos.cmake" \
    -DSDL2_INSTALL_DIR="$SDL2_INSTALL" \
    -DCMAKE_INSTALL_PREFIX="$SDL2_INSTALL" \
    -DCMAKE_BUILD_TYPE=Release \
    -DSDL_SHARED=ON -DSDL_STATIC=OFF -DSDL_TESTS=OFF \
    -DSDL_X11=OFF -DSDL_WAYLAND=OFF -DSDL_KMSDRM=ON \
    -DSDL_OPENGL=OFF -DSDL_OPENGLES=ON \
    -DSDL_PULSEAUDIO=OFF -DSDL_ALSA=ON

cmake --build "$BUILD" -j "${JOBS:-4}"
cmake --install "$BUILD"

echo "== SDL2 lib-Verzeichnis:"
ls -la "$SDL2_INSTALL/lib/"

# ── Robuster Finder ───────────────────────────────────────────────────
SDL2_LIB=$(find "$SDL2_INSTALL/lib" -maxdepth 1 \( -name "libSDL2*.so*" \) | head -n 1)
if [ -z "$SDL2_LIB" ]; then
    echo "FEHLER: keine libSDL2*.so*-Datei gefunden."
    exit 1
fi
echo "Gefunden: $SDL2_LIB"

# ── Verifikation Pageflip-Patch im Binary ────────────────────────────
COUNT=$(aarch64-linux-gnu-strings "$SDL2_LIB" | grep -c "Async pageflip rejected" || true)
if [ "$COUNT" -gt 0 ]; then
    echo "OK: Pageflip-Patch im Binary."
else
    echo "FEHLER: Pageflip-Patch nicht im Binary."
    echo "== pageflip-Strings:"
    aarch64-linux-gnu-strings "$SDL2_LIB" | grep -i pageflip || true
    exit 1
fi

# ── Verifikation Window-Flag-Patch im Binary ─────────────────────────
# Der Marker-Kommentar landet nicht im Binary, aber wir koennen
# pruefen, ob die Funktion KMSDRM_CreateWindow SDL_WINDOW_OPENGL setzt
# — indirekt ueber Symbole. Fallback: kein Hard-Fail.
echo "== Hinweis: Window-Flag-Patch ist im Quellcode verifiziert,"
echo "   nicht im Binary. Das ist erwartet."
