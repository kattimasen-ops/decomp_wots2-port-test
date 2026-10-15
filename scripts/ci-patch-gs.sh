#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== Patche gs.cpp (GLES, NEON, precision) =="
python3 patches/wots2-gles.py           src/hal/gs.cpp
python3 patches/wots2-gles-precision.py src/hal/gs.cpp
python3 patches/wots2-neon.py           src/hal/gs.cpp
python3 patches/wots2-persistent-buffers.py src/hal/gs.cpp

echo "== Patche collision_world.cpp (NEON) =="
python3 patches/wots2-collision-neon.py src/game/collision_world.cpp

echo "== Patche port_config.c (Defaults + config_changes) =="
python3 patch_config_defaults.py .
python3 patch_config_changes.py  .

echo "== Patches fertig =="
