#!/usr/bin/env bash
set -euo pipefail

# 1. GLES-Shader + glDrawBuffer-Fix
python3 patches/wots2-gles.py src/hal/gs.cpp

# 2. mediump für Farben
python3 patches/wots2-gles-precision.py src/hal/gs.cpp

# 3. NEON-Helper (mit Interleaving)
python3 patches/wots2-neon.py src/hal/gs.cpp

# 4. Persistente Buffer (opt-in, inaktiv ohne Env-Flag)
python3 patches/wots2-persistent-buffers.py src/hal/gs.cpp

# 5. Kollision: NEON-Apply + Distance-Optimierung
python3 patches/wots2-collision-neon.py src/game/collision_world.cpp

echo "== Verifikation =="
count=$(grep -c '#version 320 es' src/hal/gs.cpp || true)
echo "Shader auf ES 3.2: $count"
[ "$count" -ge 7 ] || { echo "FEHLER: zu wenige Shader"; exit 1; }

grep -q 'wots2_lerp_vertex3' src/hal/gs.cpp \
  || { echo "FEHLER: NEON-Patch fehlt"; exit 1; }

grep -q 'wots2_draw_buffer_none' src/hal/gs.cpp \
  || { echo "FEHLER: glDrawBuffer-Fix fehlt"; exit 1; }

grep -q 'wots2_apply_neon' src/game/collision_world.cpp \
  || { echo "FEHLER: NEON-Apply fehlt"; exit 1; }

grep -q 'DistanceSquared' src/game/collision_world.cpp \
  || { echo "FEHLER: Distance-Optimierung fehlt"; exit 1; }

echo "OK: Alle Patches angewendet."
