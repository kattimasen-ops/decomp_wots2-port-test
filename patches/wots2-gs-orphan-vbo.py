#!/usr/bin/env python3
"""
patches/wots2-gs-orphan-vbo.py — VBO einmal pro play() orphänen, pro Mesh
glBufferSubData mit Offset. Patcht src/hal/gs.cpp.
Idempotent ueber Marker "wots2_orphan_vbo".
"""
import sys
import pathlib

MARKER = "wots2_orphan_vbo"

OLD_LOOP = '''    s_inTarget = false;
    for (const Cmd& c : f.cmds) {
'''

NEW_LOOP = '''    s_inTarget = false;
    // wots2_orphan_vbo
    static size_t wots2_vbo_capacity = 0;
    static size_t wots2_vbo_offset = 0;
    {
        const size_t wots2_need =
            (size_t)f.v3.size() * sizeof(Vertex3) + (size_t)f.v2.size() * sizeof(Vertex) + 4096;
        glBindBuffer(GL_ARRAY_BUFFER, s_vbo3d);
        if (wots2_need > wots2_vbo_capacity) {
            glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)wots2_need, nullptr, GL_STREAM_DRAW);
            wots2_vbo_capacity = wots2_need;
        } else {
            glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)wots2_vbo_capacity, nullptr, GL_STREAM_DRAW);
        }
        wots2_vbo_offset = 0;
    }
    for (const Cmd& c : f.cmds) {
'''

OLD_MESH = '''            glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)((size_t)c.count * sizeof(Vertex3)), v, GL_STREAM_DRAW);
            glDrawArrays(gl_prim(c.prim), 0, c.count);
            if (cutout) {
'''

NEW_MESH = '''            {
                const size_t wots2_bytes = (size_t)c.count * sizeof(Vertex3);
                glBindVertexArray(s_vao3d);
                glBindBuffer(GL_ARRAY_BUFFER, s_vbo3d);
                glBufferSubData(GL_ARRAY_BUFFER, (GLintptr)wots2_vbo_offset,
                                (GLsizeiptr)wots2_bytes, v);
                glDrawArrays(gl_prim(c.prim),
                             (GLint)(wots2_vbo_offset / sizeof(Vertex3)), c.count);
                wots2_vbo_offset += wots2_bytes;
            }
            if (cutout) {
'''

def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    if MARKER in t:
        print('  Orphan-VBO bereits vorhanden.')
        return
    if OLD_LOOP not in t:
        print('  FEHLER: play()-Loop-Anker nicht gefunden.', file=sys.stderr)
        sys.exit(1)
    if OLD_MESH not in t:
        print('  FEHLER: glBufferData im Op::Mesh nicht gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t.replace(OLD_LOOP, NEW_LOOP, 1)
    t = t.replace(OLD_MESH, NEW_MESH, 1)
    p.write_text(t)
    print('  Orphan-VBO eingebaut.')

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
