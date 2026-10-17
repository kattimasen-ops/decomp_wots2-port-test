#!/usr/bin/env python3
import sys
from pathlib import Path

PATH   = Path("src/game/chara.cpp")
MARKER = "/* WOTS2_CHARA_DRAW_CULL */"

OLD = """static int Chara_Draw(Chara* self, int shown, const float* wind) {
    if (self->loaded == 0)
        return 0;
    alignas(16) float matrix[16];"""

NEW = """static int Chara_Draw(Chara* self, int shown, const float* wind) {
    if (self->loaded == 0)
        return 0;
    if (!shown) return self->loaded; /* WOTS2_CHARA_DRAW_CULL */
    alignas(16) float matrix[16];"""

def main():
    if not PATH.exists(): sys.exit(1)
    src = PATH.read_text()
    if MARKER in src: return
    if src.count(OLD) != 1: sys.exit(1)
    PATH.write_text(src.replace(OLD, NEW, 1))
