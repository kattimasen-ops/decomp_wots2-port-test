#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$SYSROOT_LIB"

aarch64-linux-gnu-gcc -shared -fPIC \
    -Wl,-soname,libmali.so.0 \
    -o "$SYSROOT_LIB/libmali.so.0" -x c - <<'STUB'
/* Linker-Stub fuer libmali.so.0. Kein Code, keine Symbole. */
STUB

aarch64-linux-gnu-gcc -shared -fPIC \
    -Wl,-soname,libdecor-0.so.0 \
    -o "$SYSROOT_LIB/libdecor-0.so.0" -x c - <<'STUB'
void libdecor_new(void) {}
void libdecor_unref(void) {}
STUB

echo "OK: Stubs gebaut."
