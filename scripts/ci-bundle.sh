#!/usr/bin/env bash
set -euo pipefail

mkdir -p dist/libs.aarch64
cp -L build/wots2 dist/wots2
aarch64-linux-gnu-strip dist/wots2 || true

# SDL2
SDL2_LIB=$(find "$SDL2_INSTALL/lib" -maxdepth 1 \( -name "libSDL2*.so*" \) | head -n 1)
if [ -n "$SDL2_LIB" ]; then
    cp -L "$SDL2_LIB" dist/libs.aarch64/libSDL2-2.0.so.0
fi

for lib in libarchive.so.13 libz.so.1 libzstd.so.1 liblzma.so.5 libbz2.so.1.0 liblz4.so.1 libasound.so.2 libudev.so.1; do
    f=$(find /usr/lib/aarch64-linux-gnu -maxdepth 1 -name "${lib}*" | head -n 1)
    if [ -n "$f" ]; then
        cp -L "$f" dist/libs.aarch64/
    fi
done

cat > dist/WOTS2.sh <<'LAUNCHER'
#!/bin/sh
DIR=$(dirname "$(readlink -f "$0")")
export LD_LIBRARY_PATH="$DIR/libs.aarch64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export SDL_VIDEODRIVER=kmsdrm
export SDL_AUDIODRIVER=alsa
if [ -w /sys/devices/system/cpu/cpufreq/policy0/scaling_governor ]; then
    echo performance > /sys/devices/system/cpu/cpufreq/policy0/scaling_governor 2>/dev/null || true
fi
exec "$DIR/wots2" "$@"
LAUNCHER
chmod +x dist/WOTS2.sh

file dist/wots2
aarch64-linux-gnu-readelf -d dist/wots2 | grep NEEDED || true
