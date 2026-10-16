#!/usr/bin/env python3
"""
Setzt die GLSL-Shader in src/hal/gs.cpp auf GLSL ES 3.2 um und
übersetzt Desktop-GL-Aufrufe in ihre ES-Äquivalente.

Enthaltene Übersetzungen:
  1. Shader-Version:      #version 330 core        → #version 320 es
  2. Precision-Qualifier: precision highp ...      (ergänzt)
  3. glDrawBuffer:        glDrawBuffer(GL_NONE)    → glDrawBuffers(1, &none)
                          (Desktop-GL-Funktion, in ES 3.x nicht vorhanden;
                           glDrawBuffers ist die ES-3.0-Entsprechung)

Idempotent: prüft Marker, überspringt bereits gepatchte Stellen.
Python 3.6+ kompatibel (keine PEP-585-Typhinweise).
"""
import re
import sys
import pathlib


# WICHTIG: '\n' (echter Zeilenumbruch), nicht '\\n' (Backslash + n).
# Die Precision-Zeilen landen in einem C++-Raw-String-Literal R"(...)".
# In einem Raw-String ist '\n' NICHT ein Escape — ein '\\n' im Python-
# Quelltext wird zu zwei Zeichen im Shader und der Mali-Compiler wirft
# dann P0007 "Unexpected text found after #version directive".
PRECISION = (
    '#version 320 es\n'
    'precision highp float;\n'
    'precision highp int;\n'
    'precision highp sampler2D;\n'
    'precision highp sampler2DShadow;\n'
    'precision highp sampler2DArrayShadow;\n'
    'precision highp sampler3D;\n'
    'precision highp samplerCube;\n'
)

DRAW_BUFFER_HELPER = r'''
// ── OpenGL ES 3.2 Kompatibilität ─────────────────────────────────────
// glDrawBuffer ist eine Desktop-GL-Funktion und existiert in OpenGL ES
// nicht. Die ES-Entsprechung heißt glDrawBuffers (Plural) und ist seit
// ES 3.0 Core.
static inline void wots2_draw_buffer_none(void) {
    const GLenum none = GL_NONE;
    glDrawBuffers(1, &none);
}
'''


def patch_glsl(t):
    """Ersetzt die Shader-Version in allen eingebetteten Shadern."""
    n = [0]
    def repl(m):
        n[0] += 1
        return 'R"(' + PRECISION
    t = re.sub(r'R"\(#version 330 core', repl, t)
    return t, n[0]


def patch_draw_buffer(t):
    """Ersetzt alle glDrawBuffer(GL_NONE)-Aufrufe durch die ES-Variante."""
    if 'wots2_draw_buffer_none' in t:
        return t, 0

    pattern = re.compile(r'glDrawBuffer\s*\(\s*GL_NONE\s*\)\s*;')
    matches = pattern.findall(t)
    if not matches:
        return t, 0

    last_inc = list(re.finditer(r'^#include [<"][^\n]+[>\"]\n', t, re.M))
    if last_inc:
        insert_at = last_inc[-1].end()
        t = t[:insert_at] + DRAW_BUFFER_HELPER + t[insert_at:]

    t = pattern.sub('wots2_draw_buffer_none();', t)
    return t, len(matches)


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()

    t, shader_count = patch_glsl(t)
    print('  Shader umgestellt: %d' % shader_count)

    t, gl_count = patch_draw_buffer(t)
    print('  glDrawBuffer-Fix: %d Aufruf(e) ersetzt' % gl_count)

    if 'gl_FragDepth' in t:
        print('  WARNUNG: gl_FragDepth verwendet; erfordert ES 3.2')

    p.write_text(t)


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
