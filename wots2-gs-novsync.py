#!/usr/bin/env python3
# wots2-gs-novsync.py (v1)
# Makes src/hal/gs.cpp honour WOTS2_NO_VSYNC (previously read only WOTS2_FAST).
# WOTS2_NO_VSYNC=1 disables SDL_GL_SetSwapInterval(1) in both call sites.
# Idempotent: marker /* WOTS2_NOVSYNC */ in the patched lines.
# Fails loudly if either anchor is missing.

import sys
from pathlib import Path

PATH   = Path("src/hal/gs.cpp")
MARKER = "/* WOTS2_NOVSYNC */"

OLD_APPLY = 'SDL_GL_SetSwapInterval(getenv("WOTS2_FAST") || !s_video.vsync ? 0 : 1);'
NEW_APPLY = 'SDL_GL_SetSwapInterval(getenv("WOTS2_FAST") || getenv("WOTS2_NO_VSYNC") || !s_video.vsync ? 0 : 1); /* WOTS2_NOVSYNC */'

OLD_RATE = 'SDL_GL_SetSwapInterval(getenv("WOTS2_FAST") || !vsync ? 0 : 1);'
NEW_RATE = 'SDL_GL_SetSwapInterval(getenv("WOTS2_FAST") || getenv("WOTS2_NO_VSYNC") || !vsync ? 0 : 1); /* WOTS2_NOVSYNC */'

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

    for name, old in [("apply_window", OLD_APPLY), ("set_rate", OLD_RATE)]:
        c = src.count(old)
        if c != 1:
            fail(f'{name}: anchor count={c}, expected 1')

    src = src.replace(OLD_APPLY, NEW_APPLY, 1)
    src = src.replace(OLD_RATE,  NEW_RATE,  1)
    PATH.write_text(src)
    print(f"Patched {PATH}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
