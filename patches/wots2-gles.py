#!/usr/bin/env python3
"""Setzt die GLSL-Shader in src/hal/gs.cpp auf GLSL ES 3.2 um."""
import re, sys, pathlib

PRECISION = (
    '#version 320 es\\n'
    'precision highp float;\\n'
    'precision highp int;\\n'
    'precision highp sampler2D;\\n'
    'precision highp sampler2DShadow;\\n'
    'precision highp sampler2DArrayShadow;\\n'
    'precision highp sampler3D;\\n'
    'precision highp samplerCube;\\n'
)

def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    n = 0
    def repl(m):
        nonlocal n; n += 1
        return 'R"(' + PRECISION
    t = re.sub(r'R"\(#version 330 core', repl, t)
    if 'gl_FragDepth' in t:
        print('  WARNUNG: gl_FragDepth verwendet; Mali-G31 muss ES 3.2 liefern')
    p.write_text(t)
    print(f'  {n} Shader auf GLSL ES 3.2 umgestellt')

if __name__ == '__main__':
    patch(sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp')
