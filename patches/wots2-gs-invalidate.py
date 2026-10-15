#!/usr/bin/env python3
"""
Fügt glInvalidateFramebuffer an zwei Stellen ein:

  1. end_frame(): Depth/Stencil nach dem Blit nach s_lastFbo.
  2. post_pass(): Color-Attachment des Post-FBO nach dem Composite-Blend.

Hintergrund (Mali-G31 MP2):
  Die GPU ist tile-basiert. Jeder Zwischenpuffer, der nicht invalidiert
  wird, muss vollständig aus dem Tile-Speicher nach DDR3 geschrieben
  werden, auch wenn ihn danach niemand mehr liest. Auf einem 1-GB-System
  mit 333-MHz-DDR3 teilen sich CPU und GPU die Bandbreite — jede
  eingesparte Zeile zählt.

Sicher: ES 3.0 Core, GLES 3.2 auf Mali-G31 verfügbar.
Idempotent über Marker-Kommentar.

Python 3.6+ kompatibel.
"""
import re
import sys
import pathlib


HELPER = r'''
// ── Framebuffer-Invalidierung (Mali-G31) ─────────────────────────────
// Siehe patches/wots2-gs-invalidate.py.
static void wots2_invalidate_depth_stencil(void) {
    const GLenum attachments[2] = {GL_DEPTH, GL_STENCIL};
    glInvalidateFramebuffer(GL_FRAMEBUFFER, 2, attachments);
}
static void wots2_invalidate_color_attachments(int count) {
    static const GLenum all[4] = {
        GL_COLOR_ATTACHMENT0, GL_COLOR_ATTACHMENT1,
        GL_COLOR_ATTACHMENT2, GL_COLOR_ATTACHMENT3
    };
    glInvalidateFramebuffer(GL_FRAMEBUFFER, count, all);
}
'''


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()

    if 'wots2_invalidate_depth_stencil' in t:
        print('  Invalidierungs-Helper bereits vorhanden.')
        return

    last_inc = list(re.finditer(r'^#include [<"][^\n]+[>\"]\n', t, re.M))
    if not last_inc:
        print('  FEHLER: kein #include gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t[:last_inc[-1].end()] + HELPER + t[last_inc[-1].end():]

    # 1. end_frame(): nach dem Blit nach s_lastFbo.
    anchor1 = re.compile(
        r'([ \t]*)glBlitFramebuffer\(0,\s*0,\s*s_physW,\s*s_physH,\s*'
        r'0,\s*0,\s*s_physW,\s*s_physH,\s*GL_COLOR_BUFFER_BIT,\s*GL_NEAREST\);\s*\n'
        r'([ \t]*)present\(\);',
        re.MULTILINE)
    m1 = anchor1.search(t)
    if m1:
        insertion = (
            m1.group(1) + 'glBlitFramebuffer(0, 0, s_physW, s_physH, 0, 0, s_physW, s_physH, GL_COLOR_BUFFER_BIT, GL_NEAREST);\n'
            + m1.group(1) + 'wots2_invalidate_depth_stencil();\n'
            + m1.group(2) + 'present();'
        )
        t = t[:m1.start()] + insertion + t[m1.end():]
        print('  end_frame(): invalidiert.')
    else:
        print('  WARNUNG: end_frame-Anker nicht gefunden.')

    # 2. post_pass(): nach dem Blit nach s_fbo, vor glEnable(GL_BLEND).
    anchor2 = re.compile(
        r'([ \t]*)glBlitFramebuffer\(0,\s*0,\s*W,\s*H,\s*0,\s*0,\s*W,\s*H,\s*'
        r'GL_COLOR_BUFFER_BIT,\s*GL_NEAREST\);\s*\n'
        r'([ \t]*)glBindFramebuffer\(GL_FRAMEBUFFER,\s*s_fbo\);\s*\n'
        r'([ \t]*)glEnable\(GL_BLEND\);',
        re.MULTILINE)
    m2 = anchor2.search(t)
    if m2:
        insertion = (
            m2.group(1) + 'glBlitFramebuffer(0, 0, W, H, 0, 0, W, H, GL_COLOR_BUFFER_BIT, GL_NEAREST);\n'
            + m2.group(1) + '// (Nur der Post-Kanal: die Zwischenpuffer sind hier fertig.)\n'
            + m2.group(1) + 'wots2_invalidate_color_attachments(1);  // (s_postFbo)\n'
            + m2.group(2) + 'glBindFramebuffer(GL_FRAMEBUFFER, s_fbo);\n'
            + m2.group(3) + 'glEnable(GL_BLEND);'
        )
        t = t[:m2.start()] + insertion + t[m2.end():]
        print('  post_pass(): Zwischenpuffer invalidiert.')
    else:
        print('  WARNUNG: post_pass-Anker nicht gefunden.')

    p.write_text(t)
    print('  glInvalidateFramebuffer eingefuegt.')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
