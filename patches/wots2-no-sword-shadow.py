#!/usr/bin/env python3
import sys
from pathlib import Path

PATH   = Path("src/game/chara.cpp")
MARKER = "/* WOTS2_NO_SWORD_SHADOW */"

OLD = """        if (self->swords != 0)
            CharaSwords_DrawShadow(P(self->swords), Body(self));     // 0x245880: the blade's trail"""

NEW = """        if (self->swords != 0 && self->id == 0) /* WOTS2_NO_SWORD_SHADOW */
            CharaSwords_DrawShadow(P(self->swords), Body(self));     // 0x245880: the blade's trail"""

def main():
    if not PATH.exists(): sys.exit(1)
    src = PATH.read_text()
    if MARKER in src: return
    if src.count(OLD) != 1: sys.exit(1)
    PATH.write_text(src.replace(OLD, NEW, 1))
