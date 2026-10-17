#!/usr/bin/env python3
# wots2-skeleton-swing-skip.py (v1)
# Chara_Draw: only run Skeleton_Swing (hair/cloth physics) when the character
# is actually shown. For culled NPCs the swinging bones' world matrices are
# never read this frame — and Skeleton_UpdateWorld in Chara_StepMap recomputes
# them next frame anyway, so no cross-frame effect.
# Always-on (no env-var needed — it's a pure no-op for shown characters).
# Idempotent: marker /* WOTS2_SKELETON_SWING_SKIP */.
# Fails loudly if anchor is missing.

import sys
from pathlib import Path

PATH   = Path("src/game/chara.cpp")
MARKER = "/* WOTS2_SKELETON_SWING_SKIP */"

OLD = '''    Skeleton_Swing(Bones(self), (Body(self)->flags & kBodyDead) ? kStill : wind);
    if (shown) {
'''

NEW = '''    if (shown) { /* WOTS2_SKELETON_SWING_SKIP */
        Skeleton_Swing(Bones(self), (Body(self)->flags & kBodyDead) ? kStill : wind);
'''

def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)

def main():
    if not PATH.exists():
        fail(f"{PATH} not found")
    src = PATH.read_text()
    if MARKER in src:
        print(f"Already patched ({MARKER} present), skipping")
        return 0

    c = src.count(OLD)
    if c != 1:
        fail(f'anchor count={c}, expected 1')
    src = src.replace(OLD, NEW, 1)
    PATH.write_text(src)
    print(f"Patched {PATH}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
