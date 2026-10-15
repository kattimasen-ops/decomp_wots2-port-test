#!/usr/bin/env bash
set -euo pipefail

chmod +x patches/wots2-gles.py \
         patches/wots2-gles-precision.py \
         patches/wots2-neon.py

python3 patches/wots2-gles.py           src/hal/gs.cpp
python3 patches/wots2-gles-precision.py src/hal/gs.cpp
python3 patches/wots2-neon.py           src/hal/gs.cpp

count=$(grep -c '#version 320 es' src/hal/gs.cpp || true)
echo "Shader auf ES 3.2 umgestellt: $count"
if [ "$count" -lt 7 ]; then
    echo "FEHLER: zu wenige Shader umgestellt."
    exit 1
fi

grep -q 'wots2_lerp_vertex3' src/hal/gs.cpp || {
    echo "FEHLER: NEON-Patch fehlt."
    exit 1
}
grep -q 'wots2_draw_buffer_none' src/hal/gs.cpp || {
    echo "FEHLER: glDrawBuffer-Fix fehlt."
    exit 1
}

echo "OK: Patches angewendet."
