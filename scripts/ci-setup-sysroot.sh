#!/usr/bin/env bash
set -euo pipefail

mkdir -p /usr/aarch64-linux-gnu/lib
for pair in \
    "libdrm.so.2:libdrm.so" \
    "libgbm.so.1:libgbm.so" \
    "libEGL.so.1:libEGL.so" \
    "libGLESv2.so.2:libGLESv2.so"
do
    tgt="/usr/lib/aarch64-linux-gnu/${pair%%:*}"
    lnk="/usr/aarch64-linux-gnu/lib/${pair##*:}"
    if [ -e "$tgt" ]; then
        ln -sf "$tgt" "$lnk"
    else
        echo "FEHLT: $tgt"
        exit 1
    fi
done

PC_DIR="${SYSROOT_LIB}/pkgconfig"
mkdir -p "$PC_DIR"

cat > "$PC_DIR/egl.pc" <<'PC'
prefix=/usr
libdir=/usr/aarch64-linux-gnu/lib
includedir=/usr/include
Name: egl
Description: EGL
Version: 1.5
Libs: -L${libdir} -lEGL
Cflags: -I${includedir}
PC

cat > "$PC_DIR/glesv2.pc" <<'PC'
prefix=/usr
libdir=/usr/aarch64-linux-gnu/lib
includedir=/usr/include
Name: glesv2
Description: OpenGL ES
Version: 3.2
Libs: -L${libdir} -lGLESv2
Cflags: -I${includedir}
PC

cat > "$PC_DIR/libdrm.pc" <<'PC'
prefix=/usr
libdir=/usr/aarch64-linux-gnu/lib
includedir=/usr/include/libdrm
Name: libdrm
Description: libdrm
Version: 2.4.110
Libs: -L${libdir} -ldrm
Cflags: -I${includedir}
PC

cat > "$PC_DIR/gbm.pc" <<'PC'
prefix=/usr
libdir=/usr/aarch64-linux-gnu/lib
includedir=/usr/include
Name: gbm
Description: gbm
Version: 21.2.6
Libs: -L${libdir} -lgbm
Cflags: -I${includedir}
PC

for m in libdrm gbm egl glesv2; do
    if pkg-config --exists "$m"; then
        echo "OK: $m $(pkg-config --modversion "$m")"
    else
        echo "FEHLT: $m"
        exit 1
    fi
done
