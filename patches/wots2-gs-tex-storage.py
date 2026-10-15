#!/usr/bin/env python3
"""
glTexStorage2D statt glTexImage2D fuer Framebuffer-Texturen.

Hintergrund (ARM Best Practice fuer Mali):
  glTexImage2D erlaubt nachtraegliche Groessen- und Format-Aenderungen.
  Der Mali-Treiber muss deshalb defensiv allokieren und kann die
  Textur nicht als tile-lokale Allokation vorbereiten.
  glTexStorage2D (ES 3.0 Core) allokiert einmalig und unveraenderlich.
  Das erlaubt dem Treiber, den Speicher sofort als Tile-Puffer
  vorzubereiten, und reduziert Bandbreite auf einem System, in dem sich
  CPU und GPU 1 GB DDR3 teilen.

Was der Patch macht:
  Ersetzt in size_frame(), post_pass(), colour_target() und den
  Shadow-/Lantern-/Rain-Passes die glTexImage2D-Aufrufe fuer
  nicht-mipmapped FBO-Texturen durch glTexStorage2D + glTexSubImage2D
  (wo Init-Daten uebergeben werden).

  Nur FBO-Texturen, die nicht per glTexSubImage2D aktualisiert werden,
  sind betroffen. Sprite-Texturen bleiben bei glTexImage2D.

Python 3.6+ kompatibel.
"""
import re
import sys
import pathlib


HELPER = r'''
// ── glTexStorage2D fuer FBO-Texturen (Mali-G31) ──────────────────────
// Siehe patches/wots2-gs-tex-storage.py.
static void wots2_tex_storage_2d(GLenum format, GLsizei w, GLsizei h,
                                  GLenum glFormat) {
    glTexStorage2D(GL_TEXTURE_2D, 1, format, w, h);
    (void)glFormat;
}
static void wots2_tex_storage_depth(GLsizei w, GLsizei h) {
    glTexStorage2D(GL_TEXTURE_2D, 1, GL_DEPTH_COMPONENT24, w, h);
}
'''

MARKER = "wots2_tex_storage_2d"


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    if MARKER in t:
        print('  tex_storage-Helper bereits vorhanden.')
        return

    # Nur die FBO-Texturen ohne Mipmaps umstellen.
    # In gs.cpp sind das:
    #   s_fboTex, s_depth, s_distTex, s_lastTex (size_frame)
    #   s_shadowTex, s_lanternTex, s_rainTex, s_targetTex, s_targetDepth
    #   s_postTex, s_aoTex, s_bloomTex[0/1], s_raysTex (colour_target)
    # Wir ersetzen nur die glTexImage2D-Aufrufe mit nullptr-Daten und
    # ohne Mipmap-Level (also Level 0, kein `levels`).

    replacements = [
        # size_frame: s_fboTex (GL_RGBA8)
        (r'glTexImage2D\(GL_TEXTURE_2D,\s*0,\s*GL_RGBA8,\s*w,\s*h,\s*0,\s*GL_RGBA,\s*GL_UNSIGNED_BYTE,\s*nullptr\);',
         'glTexStorage2D(GL_TEXTURE_2D, 1, GL_RGBA8, w, h);'),
        # size_frame: s_depth
        (r'glTexImage2D\(GL_TEXTURE_2D,\s*0,\s*GL_DEPTH_COMPONENT24,\s*w,\s*h,\s*0,\s*GL_DEPTH_COMPONENT,\s*GL_UNSIGNED_INT,\s*nullptr\);',
         'glTexStorage2D(GL_TEXTURE_2D, 1, GL_DEPTH_COMPONENT24, w, h);'),
        # size_frame: s_distTex (GL_R32F)
        (r'glTexImage2D\(GL_TEXTURE_2D,\s*0,\s*GL_R32F,\s*s_distW,\s*s_distH,\s*0,\s*GL_RED,\s*GL_FLOAT,\s*nullptr\);',
         'glTexStorage2D(GL_TEXTURE_2D, 1, GL_R32F, s_distW, s_distH);'),
        # size_frame: s_lastTex
        (r'glTexImage2D\(GL_TEXTURE_2D,\s*0,\s*GL_RGBA8,\s*w,\s*h,\s*0,\s*GL_RGBA,\s*GL_UNSIGNED_BYTE,\s*nullptr\);',
         'glTexStorage2D(GL_TEXTURE_2D, 1, GL_RGBA8, w, h);'),
        # colour_target
        (r'glTexImage2D\(GL_TEXTURE_2D,\s*0,\s*format,\s*w,\s*h,\s*0,\s*GL_RGBA,\s*GL_UNSIGNED_BYTE,\s*nullptr\);',
         'glTexStorage2D(GL_TEXTURE_2D, 1, format, w, h);'),
        # shadow_pass: s_shadowTex
        (r'glTexImage2D\(GL_TEXTURE_2D,\s*0,\s*GL_DEPTH_COMPONENT24,\s*size,\s*size,\s*0,\s*GL_DEPTH_COMPONENT,\s*GL_UNSIGNED_INT,\s*nullptr\);',
         'glTexStorage2D(GL_TEXTURE_2D, 1, GL_DEPTH_COMPONENT24, size, size);'),
        # rain_mask_pass: s_rainTex
        (r'glTexImage2D\(GL_TEXTURE_2D,\s*0,\s*GL_DEPTH_COMPONENT24,\s*1024,\s*1024,\s*0,\s*GL_DEPTH_COMPONENT,\s*GL_UNSIGNED_INT,\s*nullptr\);',
         'glTexStorage2D(GL_TEXTURE_2D, 1, GL_DEPTH_COMPONENT24, 1024, 1024);'),
        # lighting_begin: s_distTex (Fallback)
        (r'glTexImage2D\(GL_TEXTURE_2D,\s*0,\s*GL_R32F,\s*s_distW,\s*s_distH,\s*0,\s*GL_RED,\s*GL_FLOAT,\s*nullptr\);',
         'glTexStorage2D(GL_TEXTURE_2D, 1, GL_R32F, s_distW, s_distH);'),
    ]

    total = 0
    for pat, repl in replacements:
        t, n = re.subn(pat, repl, t)
        total += n

    if total == 0:
        print('  WARNUNG: keine passenden glTexImage2D-Aufrufe gefunden.')

    p.write_text(t)
    print('  tex-storage: %d Aufruf(e) umgestellt.' % total)


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
