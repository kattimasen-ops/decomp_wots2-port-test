#!/usr/bin/env python3
import sys
from pathlib import Path

PATH   = Path("src/hal/gs.cpp")
MARKER = "/* WOTS2_GS_TEX_CACHE */"

OLD = """            s_drawn++;
            const Vertex3* v = verts3(f, c, before, t);
            glBindTexture(GL_TEXTURE_2D, c.tex);
            const bool cutout = !s_overlayOn && s_cutout.count(c.tex);"""

NEW = """            s_drawn++;
            const Vertex3* v = verts3(f, c, before, t);
            /* WOTS2_GS_TEX_CACHE */
            static GLuint last_bound_tex = 0;
            if (c.tex != last_bound_tex) {
                glBindTexture(GL_TEXTURE_2D, c.tex);
                last_bound_tex = c.tex;
            }
            const bool cutout = !s_overlayOn && s_cutout.count(c.tex);"""

def main():
    if not PATH.exists(): sys.exit(1)
    src = PATH.read_text()
    if MARKER in src: return
    if src.count(OLD) != 1: sys.exit(1)
    PATH.write_text(src.replace(OLD, NEW, 1))
