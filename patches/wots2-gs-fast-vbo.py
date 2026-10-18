#!/usr/bin/env python3
"""
patches/wots2-gs-fast-vbo.py   (v2, Ring-Puffer)

Warum v2: Der alte Patch ersetzte glBufferData(..., v, GL_STREAM_DRAW) durch
glBufferData(NULL) + glBufferSubData. Das macht pro Draw einen GL-Aufruf mehr
und spart nichts. Ausserdem trifft das Suchmuster 4-mal in gs.cpp (der Patch
bricht dann ab), und er hat nie gelaufen, weil main() nicht aufgerufen wurde.

Was jetzt passiert (nur im 3D-Mesh-Pfad, 'case Op::Mesh', ca. 400 Draws/Frame):
  Bisher legte jeder Draw per glBufferData einen NEUEN Speicherblock fuer den
  Vertex-Puffer an (Orphaning) und kopierte die Vertices hinein.
  Jetzt: ein grosser Puffer (4 MiB) wird wie ein Ring beschrieben. Jeder Draw
  haengt seine Vertices per glBufferSubData hinten an und zeichnet mit
  glDrawArrays(prim, first, count). Nur wenn der Puffer voll ist, wird er
  einmal neu angelegt. Das spart pro Frame mehrere hundert Speicher-
  Allokationen im Mali-Treiber.

Sicherheit:
  * Jedes ANDERE glBufferData(GL_ARRAY_BUFFER, ...) in gs.cpp (Schatten, 2D,
    DrawDepth, Quads) laeuft durch einen Wrapper und macht den Ring ungueltig.
    Der naechste Mesh-Draw legt den Puffer dann neu an.
  * Der Ring merkt sich, zu welchem Puffer (s_vbo3d) er gehoert.
  * Beide glDrawArrays im Mesh-Fall (Draw und Cutout-Saum) nutzen 'first'.
  * Notausschalter: WOTS2_NO_VBO_RING=1 -> Originalverhalten.

Idempotent: Marker 'wots2_gs_fast_vbo_v2'.
Zieldatei: src/hal/gs.cpp
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wots2_patchlib as pl  # noqa: E402

MARKER = "wots2_gs_fast_vbo_v2"

HELPER = '''
// wots2_gs_fast_vbo_v2 (wots2-gs-fast-vbo.py)
static inline bool wots2_vbo_ring_on() {
    static const bool on = (getenv("WOTS2_NO_VBO_RING") == nullptr);
    return on;
}
static GLuint wots2_ring_owner = 0;                 // zu welchem Puffer der Ring gehoert
static size_t wots2_ring_off = 0, wots2_ring_cap = 0;   // Schreibposition und Groesse in Bytes
static const size_t kWots2RingBytes = 4u << 20;

// Legt count Vertex3 in den Ring und gibt den Index des ersten Vertex zurueck
// (fuer glDrawArrays). Der Puffer 'owner' muss als GL_ARRAY_BUFFER gebunden sein.
static inline GLint wots2_vbo_upload(GLuint owner, const Vertex3* v, size_t count) {
    const size_t bytes = count * sizeof(Vertex3);
    if (!wots2_vbo_ring_on()) {
        glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)bytes, v, GL_STREAM_DRAW);
        wots2_ring_cap = 0;
        return 0;
    }
    if (wots2_ring_owner != owner || wots2_ring_cap == 0 || wots2_ring_off + bytes > wots2_ring_cap) {
        const size_t cap = bytes > kWots2RingBytes ? bytes : kWots2RingBytes;
        glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)cap, nullptr, GL_STREAM_DRAW);   // neuer Speicherblock
        wots2_ring_owner = owner;
        wots2_ring_cap = cap;
        wots2_ring_off = 0;
    }
    const size_t off = wots2_ring_off;      // immer ein Vielfaches von sizeof(Vertex3)
    glBufferSubData(GL_ARRAY_BUFFER, (GLintptr)off, (GLsizeiptr)bytes, v);
    wots2_ring_off = off + bytes;
    return (GLint)(off / sizeof(Vertex3));
}

// Jedes fremde glBufferData auf GL_ARRAY_BUFFER ersetzt den Pufferinhalt: Ring ungueltig.
static inline void wots2c_BufferData(GLenum target, GLsizeiptr size, const void* data, GLenum usage) {
    if (target == GL_ARRAY_BUFFER)
        wots2_ring_cap = 0;
    glBufferData(target, size, data, usage);
}
#undef glBufferData
#define glBufferData wots2c_BufferData
'''

UPLOAD = pl.flex('glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)((size_t)c.count * sizeof(Vertex3)), v, GL_STREAM_DRAW);')
DRAW = pl.flex('glDrawArrays(gl_prim(c.prim), 0, c.count);')


def patch(path):
    p = pathlib.Path(path)
    if not p.exists():
        pl.fail('Zieldatei %s existiert nicht' % path)
        return
    t = p.read_text()
    if MARKER in t:
        print('  Fast-VBO bereits vorhanden (Marker: %s).' % MARKER)
        return

    # 1. Mesh-Fall finden
    m = re.search(r'case\s+Op::Mesh\s*:\s*\{', t)
    if not m:
        pl.fail("'case Op::Mesh: {' nicht gefunden")
        return
    open_idx = m.end() - 1
    close_idx = pl.match_brace(t, open_idx)
    if close_idx < 0:
        pl.fail("Klammer des Mesh-Falls nicht abgeschlossen")
        return
    block = t[open_idx:close_idx + 1]

    ups = list(re.finditer(UPLOAD, block))
    draws = list(re.finditer(DRAW, block))
    if len(ups) != 1:
        pl.fail('Mesh-Fall: %d glBufferData-Treffer statt genau 1' % len(ups))
        return
    if len(draws) < 1:
        pl.fail('Mesh-Fall: kein glDrawArrays(... , 0, c.count) gefunden')
        return

    # 2. Block umschreiben (von hinten nach vorn, damit die Positionen stimmen)
    new_block = block
    for d in reversed(draws):
        new_block = (new_block[:d.start()] +
                     'glDrawArrays(gl_prim(c.prim), wots2_first, c.count);' +
                     new_block[d.end():])
    u = ups[0]
    new_block = (new_block[:u.start()] +
                 'const GLint wots2_first = wots2_vbo_upload(s_vbo3d, v, (size_t)c.count);' +
                 new_block[u.end():])

    # 3. Helfer direkt hinter 'struct Vertex3 {...};' einsetzen (vor allen glBufferData-Aufrufen)
    s3 = re.search(r'struct\s+Vertex3\s*\{[^}]*\}\s*;\s*\n', t)
    if not s3:
        pl.fail('struct Vertex3 nicht gefunden')
        return
    first_use = re.search(r'\bglBufferData\s*\(', t)
    if first_use and first_use.start() < s3.end():
        pl.fail('ein glBufferData steht VOR struct Vertex3 - Wrapper kann nicht davor liegen')
        return
    if 's_vbo3d' not in t[:s3.end()] and not re.search(r'\bs_vbo3d\b', t[:open_idx]):
        pl.fail('s_vbo3d ist vor dem Mesh-Fall nicht deklariert')
        return

    t = t[:open_idx] + new_block + t[close_idx + 1:]
    s3 = re.search(r'struct\s+Vertex3\s*\{[^}]*\}\s*;\s*\n', t)     # Position unveraendert (liegt davor)
    t = t[:s3.end()] + HELPER + t[s3.end():]
    p.write_text(t)

    print('  Fast-VBO (Ring-Puffer, 4 MiB) im Mesh-Fall eingebaut:')
    print('    Upload ersetzt: 1, glDrawArrays angepasst: %d' % len(draws))
    print('  Notausschalter: WOTS2_NO_VBO_RING=1')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    pl.finish()
    print('Fertig.')
