#!/usr/bin/env python3
"""Setzt Farb-/Combiner-Berechnungen auf mediump (16-bit)."""
import re, sys, pathlib

def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()

    t = t.replace('precision highp sampler2D;', 'precision mediump sampler2D;', 1)
    t = t.replace('precision highp sampler3D;', 'precision mediump sampler3D;', 1)
    t = t.replace('precision highp samplerCube;', 'precision mediump samplerCube;', 1)

    t = t.replace('uniform vec4 ps_c0[8];', 'uniform mediump vec4 ps_c0[8];')
    t = t.replace('uniform vec4 ps_c1[8];', 'uniform mediump vec4 ps_c1[8];')
    t = t.replace('uniform vec4 ps_final_c0;', 'uniform mediump vec4 ps_final_c0;')
    t = t.replace('uniform vec4 ps_final_c1;', 'uniform mediump vec4 ps_final_c1;')
    t = t.replace('uniform vec3 uFogColor;', 'uniform mediump vec3 uFogColor;')

    t = t.replace('uniform vec4 bump_luminance[4];', 'uniform mediump vec4 bump_luminance[4];')
    t = t.replace('uniform vec4 texture_lod_bias;', 'uniform mediump vec4 texture_lod_bias;')

    t = t.replace('uniform float uAlphaRef;', 'uniform mediump float uAlphaRef;')

    t = t.replace('out vec4 vColor;', 'out mediump vec4 vColor;', 1)
    t = t.replace('out vec4 vColor;\nout float vDepth;\nout vec3 vWorld;',
                  'out mediump vec4 vColor;\nout highp float vDepth;\nout highp vec3 vWorld;')

    t = t.replace('in vec4 vColor;', 'in mediump vec4 vColor;')
    t = t.replace('in float vDepth;', 'in highp float vDepth;')
    t = t.replace('in vec3 vWorld;', 'in highp vec3 vWorld;')

    p.write_text(t)
    print('  Shader-Precision: mediump für Farben/Sampler, highp für Positionen/Tiefe')

if __name__ == '__main__':
    patch(sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp')
