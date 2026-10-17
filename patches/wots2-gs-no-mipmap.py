#!/usr/bin/env python3
import sys
from pathlib import Path

PATH   = Path("src/hal/gs.cpp")
MARKER = "/* WOTS2_GS_NO_MIPMAP */"

OLD = """    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, count > 1 ? GL_LINEAR_MIPMAP_LINEAR : GL_LINEAR);"""

NEW = """    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR); /* WOTS2_GS_NO_MIPMAP */"""

def main():
    if not PATH.exists(): sys.exit(1)
    src = PATH.read_text()
    if MARKER in src: return
    if src.count(OLD) != 1: sys.exit(1)
    PATH.write_text(src.replace(OLD, NEW, 1))
