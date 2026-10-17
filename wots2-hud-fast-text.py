#!/usr/bin/env python3
# wots2-hud-fast-text.py (v1)
# hud.cpp: Removes the 4 shadow passes for enemy names and talk prompts.
# Saves ~100-200 draw calls per frame when enemies are on screen.
import sys
from pathlib import Path

PATH   = Path("src/game/hud.cpp")
MARKER = "/* WOTS2_HUD_FAST_TEXT */"

OLD_ENEMY = '''    Font_SetColor(font, 0x80000000u);
    Font_DrawStringPlain(font, name, tx + 0x10, ty + 0x10, 0xFFF000u);
    Font_DrawStringPlain(font, name, tx + 0x10, ty - 0x10, 0xFFF000u);
    Font_DrawStringPlain(font, name, tx - 0x10, ty + 0x10, 0xFFF000u);
    Font_DrawStringPlain(font, name, tx - 0x10, ty - 0x10, 0xFFF000u);
    Font_SetColor(font, 0x808A8A8Au);
    Font_DrawStringPlain(font, name, tx, ty, 0xFFF000u);'''

NEW_ENEMY = '''    /* WOTS2_HUD_FAST_TEXT */
    Font_SetColor(font, 0x808A8A8Au);
    Font_DrawStringPlain(font, name, tx, ty, 0xFFF000u);'''

OLD_TALK = '''    const u32 old = Font_SetColor(font, 0x80222222u);
    const s32 left = x - (width >> 1);
    Font_DrawStringPlain(font, name, left + 0x10, y - 0x2B0, 0xFFFFF0u);
    Font_SetColor(font, 0x80BEBEBEu);
    Font_DrawStringPlain(font, name, left, y - 0x2C0, 0xFFFFF0u);
    Font_SetColor(font, old);'''

NEW_TALK = '''    const u32 old = Font_SetColor(font, 0x80BEBEBEu);
    const s32 left = x - (width >> 1);
    Font_DrawStringPlain(font, name, left, y - 0x2C0, 0xFFFFF0u);
    Font_SetColor(font, old);'''

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

    for name, old in [("enemy", OLD_ENEMY), ("talk", OLD_TALK)]:
        c = src.count(old)
        if c != 1:
            fail(f'{name}: anchor count={c}, expected 1')

    src = src.replace(OLD_ENEMY, NEW_ENEMY, 1)
    src = src.replace(OLD_TALK, NEW_TALK, 1)
    PATH.write_text(src)
    print(f"Patched {PATH}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
