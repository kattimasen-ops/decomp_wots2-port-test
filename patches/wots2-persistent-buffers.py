#!/usr/bin/env python3
"""
Opt-in: Persistente gemappte Buffer statt glBufferData.
Nur aktiv mit WOTS2_PERSISTENT_BUFFERS=1.

Python 3.6+ kompatibel.
"""
import re
import sys
import pathlib


HELPER = r'''
// ── Persistente Buffer (opt-in) ─────────────────────────────────────
static bool wots2_persistent_buffers_enabled(void) {
    static int enabled = -1;
    if (enabled < 0)
        enabled = (getenv("WOTS2_PERSISTENT_BUFFERS") != nullptr) ? 1 : 0;
    return enabled != 0;
}
'''


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()

    if 'wots2_persistent_buffers_enabled' in t:
        print('  Persistent-Buffer-Helper bereits vorhanden.')
        return

    last_inc = list(re.finditer(r'^#include [<"][^\n]+[>\"]\n', t, re.M))[-1]
    t = t[:last_inc.end()] + HELPER + t[last_inc.end():]

    pattern = re.compile(
        r'glBufferData\s*\(\s*GL_ARRAY_BUFFER\s*,\s*'
        r'\(GLsizeiptr\)\(\(size_t\)c\.count\s*\*\s*sizeof\(Vertex3?\)\)\s*,\s*'
        r'v\s*,\s*GL_STREAM_DRAW\s*\)\s*;')
    matches = pattern.findall(t)
    print('  glBufferData-Aufrufe gefunden: %d' % len(matches))

    if not matches:
        p.write_text(t)
        return

    def repl(match):
        return (
            'if (wots2_persistent_buffers_enabled()) {\n'
            '        void* _map = glMapBufferRange(GL_ARRAY_BUFFER, 0, '
            '(GLsizeiptr)((size_t)c.count * sizeof(Vertex3)), '
            'GL_MAP_WRITE_BIT | GL_MAP_UNSYNCHRONIZED_BIT);\n'
            '        if (_map) { memcpy(_map, v, (size_t)c.count * sizeof(Vertex3)); '
            'glUnmapBuffer(GL_ARRAY_BUFFER); }\n'
            '    } else {\n'
            '        glBufferData(GL_ARRAY_BUFFER, '
            '(GLsizeiptr)((size_t)c.count * sizeof(Vertex3)), v, GL_STREAM_DRAW);\n'
            '    }')
    t = pattern.sub(repl, t)
    p.write_text(t)
    print('  Persistent-Buffer-Pfad eingefügt (opt-in).')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
