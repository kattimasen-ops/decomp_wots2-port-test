#!/usr/bin/env python3
"""
Fügt glInvalidateFramebuffer für Depth/Stencil am Frame-Ende ein.

Hintergrund (Mali-G31 MP2):
  Die GPU ist tile-basiert. Während der Rasterisierung liegt der Depth-
  Buffer in Tile-Speicher; nur wenn ein Shader ihn als Textur liest
  (das tut der Post-Pass: uDepthT), schreibt der Treiber ihn zurück
  in DDR3. Nach dem Blit nach s_lastFbo braucht ihn niemand mehr — die
  nächste FrameBegin räumt ihn ohnehin per glClear. Auf einem 1-GB-System,
  in dem CPU und GPU sich die 333-MHz-DDR3 teilen, spart das den
  kompletten Write-Back der Tiefe pro Frame.

Sicher: ES 3.0 Core-Funktion, in GLES 3.2 auf Mali-G31 verfügbar.
Idempotent über Marker-Kommentar.

Python 3.6+ kompatibel.
"""
import re
import sys
import pathlib


HELPER = r'''
// ── Framebuffer-Invalidierung (Mali-G31) ─────────────────────────────
// Nach dem Blit am Frame-Ende: Depth und Stencil werden in dieser Frame
// nicht mehr gelesen. Die nächste FrameBegin räumt sie per glClear.
// Auf tile-basierten GPUs (Mali) spart das den Write-Back der Tiefe
// in DDR3. Siehe patches/wots2-gs-invalidate.py.
static void wots2_invalidate_depth_stencil(void) {
    const GLenum attachments[2] = {GL_DEPTH, GL_STENCIL};
    glInvalidateFramebuffer(GL_FRAMEBUFFER, 2, attachments);
}
'''


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()

    if 'wots2_invalidate_depth_stencil' in t:
        print('  Invalidierungs-Helper bereits vorhanden.')
        return

    # 1. Helper nach dem letzten #include einfügen.
    last_inc = list(re.finditer(r'^#include [<"][^\n]+[>\"]\n', t, re.M))
    if not last_inc:
        print('  FEHLER: kein #include gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t[:last_inc[-1].end()] + HELPER + t[last_inc[-1].end():]

    # 2. In end_frame() den Aufruf nach dem Blit nach s_lastFbo einfügen.
    #    Anker: die Blit-Zeile mit s_lastFbo.
    anchor = re.compile(
        r'([ \t]*)glBlitFramebuffer\(0,\s*0,\s*s_physW,\s*s_physH,\s*'
        r'0,\s*0,\s*s_physW,\s*s_physH,\s*GL_COLOR_BUFFER_BIT,\s*GL_NEAREST\);\s*\n'
        r'([ \t]*)present\(\);',
        re.MULTILINE)
    m = anchor.search(t)
    if not m:
        print('  WARNUNG: end_frame-Anker (Blit nach s_lastFbo) nicht gefunden.')
        print('  Helper wurde eingefuegt, aber kein Aufruf. Manuell pruefen.')
        p.write_text(t)
        return

    insertion = (
        m.group(1) + 'glBlitFramebuffer(0, 0, s_physW, s_physH, 0, 0, s_physW, s_physH, GL_COLOR_BUFFER_BIT, GL_NEAREST);\n'
        + m.group(1) + 'wots2_invalidate_depth_stencil();\n'
        + m.group(2) + 'present();'
    )
    t = t[:m.start()] + insertion + t[m.end():]

    p.write_text(t)
    print('  glInvalidateFramebuffer in end_frame() eingefuegt.')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
