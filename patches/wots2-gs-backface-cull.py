#!/usr/bin/env python3
import sys
from pathlib import Path

PATH   = Path("src/hal/gs.cpp")
MARKER = "/* WOTS2_GS_BACKFACE_CULL */"

OLD = """    glBindVertexArray(s_vao3d);
    glBindBuffer(GL_ARRAY_BUFFER, s_vbo3d);
    glEnable(GL_DEPTH_TEST);
    glDepthFunc(GL_LEQUAL);
    glDepthMask(GL_TRUE);"""

NEW = """    glBindVertexArray(s_vao3d);
    glBindBuffer(GL_ARRAY_BUFFER, s_vbo3d);
    glEnable(GL_DEPTH_TEST);
    glDepthFunc(GL_LEQUAL);
    glDepthMask(GL_TRUE);
    glEnable(GL_CULL_FACE); /* WOTS2_GS_BACKFACE_CULL */
    glCullFace(GL_BACK);"""

def main():
    if not PATH.exists(): sys.exit(1)
    src = PATH.read_text()
    if MARKER in src: return
    if src.count(OLD) != 1: sys.exit(1)
    PATH.write_text(src.replace(OLD, NEW, 1))
