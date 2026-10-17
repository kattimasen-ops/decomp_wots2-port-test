#!/usr/bin/env python3
import sys
from pathlib import Path

PATH   = Path("src/hal/gs.cpp")
MARKER = "/* WOTS2_GS_MEDIUMP */"

OLD = """static const char* kFragmentShader3d = R"(#version 330 core
in vec2 vUv;
in vec4 vColor;
in float vDepth;
in vec3 vWorld;"""

NEW = """static const char* kFragmentShader3d = R"(#version 330 core
/* WOTS2_GS_MEDIUMP */
in mediump vec2 vUv;
in mediump vec4 vColor;
in highp float vDepth;
in highp vec3 vWorld;"""

def main():
    if not PATH.exists(): sys.exit(1)
    src = PATH.read_text()
    if MARKER in src: return
    if src.count(OLD) != 1: sys.exit(1)
    PATH.write_text(src.replace(OLD, NEW, 1))
