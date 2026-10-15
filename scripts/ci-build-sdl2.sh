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

# KMSDRM-Check erzwingen
python3 "$GITHUB_WORKSPACE/patches/sdl2-force-kmsdrm.py" \
    "$SRC/cmake/sdlchecks.cmake"

# Pageflip-Patch anwenden
python3 "$GITHUB_WORKSPACE/patches/sdl2-pageflip.py" \
    "$SRC/src/video/kmsdrm/SDL_kmsdrmopengles.c"

# Verifikation im Quellcode (kein SIGPIPE-Problem, da Datei)
if ! grep -q "Async pageflip rejected" \
     "$SRC/src/video/kmsdrm/SDL_kmsdrmopengles.c"; then
    echo "FEHLER: Pageflip-Patch nicht im Quellcode."
    exit 1
fi
echo "OK: Patch im Quellcode."

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

# Robuster Finder
SDL2_LIB=$(find "$SDL2_INSTALL/lib" -maxdepth 1 \( -name "libSDL2*.so*" \) | head -n 1)
if [ -z "$SDL2_LIB" ]; then
    echo "FEHLER: keine libSDL2*.so*-Datei gefunden."
    exit 1
fi
echo "Gefunden: $SDL2_LIB"

# grep -c statt grep -q: liest die ganze Pipe, kein SIGPIPE an strings
COUNT=$(aarch64-linux-gnu-strings "$SDL2_LIB" | grep -c "Async pageflip rejected" || true)
if [ "$COUNT" -gt 0 ]; then
    echo "OK: Pageflip-Patch im Binary."
else
    echo "FEHLER: Pageflip-Patch nicht im Binary."
    echo "== pageflip-Strings:"
    aarch64-linux-gnu-strings "$SDL2_LIB" | grep -i pageflip || true
    exit 1
fi
