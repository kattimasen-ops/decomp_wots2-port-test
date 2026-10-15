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

Quellen:
  - Khronos GLSL ES 3.2 Spec
  - Khronos OpenGL ES 3.2 Reference: glDrawBuffers
  - ARM Mali Best Practices

Idempotent: prüft Marker, überspringt bereits gepatchte Stellen.
"""
import re
import sys
import pathlib


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

# Hilfsfunktion für glDrawBuffer-Ersatz. Wird nach den Includes eingefügt.
DRAW_BUFFER_HELPER = r'''
// ── OpenGL ES 3.2 Kompatibilität ─────────────────────────────────────
// glDrawBuffer ist eine Desktop-GL-Funktion und existiert in OpenGL ES
// nicht. Die ES-Entsprechung heißt glDrawBuffers (Plural) und ist seit
// ES 3.0 Core. Alle unsere Verwendungen setzen GL_NONE (kein Color-
// Attachment beim Shadow-/Depth-Pass), daher genügt ein einzelner
// Eintrag.
static inline void wots2_draw_buffer_none(void) {
    const GLenum none = GL_NONE;
    glDrawBuffers(1, &none);
}
'''


def patch_glsl(t: str) -> tuple[str, int]:
    """Ersetzt die Shader-Version in allen eingebetteten Shadern."""
    n = 0
    def repl(m):
        nonlocal n
        n += 1
        return 'R"(' + PRECISION
    t = re.sub(r'R"\(#version 330 core', repl, t)
    return t, n


def patch_draw_buffer(t: str) -> tuple[str, int]:
    """Ersetzt alle glDrawBuffer(GL_NONE)-Aufrufe durch die ES-Variante."""
    if 'wots2_draw_buffer_none' in t:
        return t, 0

    # Alle glDrawBuffer(GL_NONE) finden — egal ob als eigenständige Zeile
    # oder mit Whitespace-Varianten.
    pattern = re.compile(r'glDrawBuffer\s*\(\s*GL_NONE\s*\)\s*;')

    matches = pattern.findall(t)
    if not matches:
        return t, 0

    # Helper-Funktion nach dem letzten #include einfügen.
    last_inc = list(re.finditer(r'^#include [<"][^\n]+[>\"]\n', t, re.M))
    if last_inc:
        insert_at = last_inc[-1].end()
        t = t[:insert_at] + DRAW_BUFFER_HELPER + t[insert_at:]

    # Ersetzen.
    t = pattern.sub('wots2_draw_buffer_none();', t)
    return t, len(matches)


def patch(path: str) -> None:
    p = pathlib.Path(path)
    t = p.read_text()

    # 1. Shader auf ES 3.2 umstellen
    t, shader_count = patch_glsl(t)
    print(f'  Shader umgestellt: {shader_count}')

    # 2. glDrawBuffer → glDrawBuffers
    t, gl_count = patch_draw_buffer(t)
    print(f'  glDrawBuffer-Fix: {gl_count} Aufruf(e) ersetzt')

    # 3. Warnung bei gl_FragDepth (auf ES 3.2 verfügbar, aber prüfen)
    if 'gl_FragDepth' in t:
        print('  WARNUNG: gl_FragDepth verwendet; '
              'erfordert ES 3.2 (auf Mali-G31 vorhanden)')

    p.write_text(t)


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print(f'Patche {target}')
    patch(target)
    print('Fertig.')
