#!/usr/bin/env python3
"""
patches/wots2-gs-tex-cache.py   (v2)

Ueberspringt glBindTexture-Aufrufe, die dieselbe Textur noch einmal binden.

Warum v2: Die alte Version legte eine 'static GLuint last_bound_tex' in die
3D-Zeichenschleife. Das ist unsicher: Jede andere Stelle in gs.cpp, die eine
Textur bindet (Upload, Post-Process, Overlay, 2D-Batch), ueberholt den Cache,
und der naechste Aufruf mit derselben ID wuerde das Binden faelschlich
auslassen. Folge waeren falsche Texturen.

v2 setzt den Cache an der richtigen Stelle ein, in gs.cpp selbst, und
verfolgt dabei:
  * ALLE glBindTexture-Aufrufe der Datei (per Wrapper-Makro),
  * die aktive Textureinheit (glActiveTexture),
  * geloeschte Texturen (glDeleteTextures).
Nur GL_TEXTURE_2D wird gecacht, alles andere geht unveraendert durch.

Notausschalter zur Laufzeit: WOTS2_NO_TEXCACHE=1 (Originalverhalten).

Grenze: Wenn eine ANDERE .cpp-Datei GL-Texturen bindet, kennt der Cache
das nicht. Dann bitte den Schalter benutzen und mir Bescheid geben.

Idempotent: Marker 'wots2_gs_tex_cache_v2'.
Zieldatei: src/hal/gs.cpp
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wots2_patchlib as pl  # noqa: E402

MARKER = "wots2_gs_tex_cache_v2"

BLOCK = '''
// wots2_gs_tex_cache_v2 (wots2-gs-tex-cache.py)
#include <cstdint>
#include <cstdlib>
static inline bool wots2_texcache_on() {
    static const bool on = (getenv("WOTS2_NO_TEXCACHE") == nullptr);
    return on;
}
static uint32_t wots2_tex_bound[32];     // gebundene GL_TEXTURE_2D-ID + 1 je Einheit, 0 = unbekannt
static unsigned wots2_tex_unit = 0;      // aktive Einheit (32 = ausserhalb, nicht gecacht)
static inline void wots2_glBindTexture(GLenum target, GLuint tex) {
    if (target == GL_TEXTURE_2D && wots2_tex_unit < 32 && wots2_texcache_on()) {
        if (wots2_tex_bound[wots2_tex_unit] == (uint32_t)tex + 1u)
            return;
        wots2_tex_bound[wots2_tex_unit] = (uint32_t)tex + 1u;
    }
    glBindTexture(target, tex);
}
static inline void wots2_glActiveTexture(GLenum unit) {
    wots2_tex_unit = (unit >= GL_TEXTURE0 && unit < GL_TEXTURE0 + 32u) ? (unsigned)(unit - GL_TEXTURE0) : 32u;
    glActiveTexture(unit);
}
static inline void wots2_glDeleteTextures(GLsizei n, const GLuint* tex) {
    for (GLsizei i = 0; i < n; i++)
        for (unsigned u = 0; u < 32; u++)
            if (wots2_tex_bound[u] == (uint32_t)tex[i] + 1u)
                wots2_tex_bound[u] = 0;
    glDeleteTextures(n, tex);
}
#undef glBindTexture
#undef glActiveTexture
#undef glDeleteTextures
#define glBindTexture wots2_glBindTexture
#define glActiveTexture wots2_glActiveTexture
#define glDeleteTextures wots2_glDeleteTextures
'''


def patch(path):
    p = pathlib.Path(path)
    if not p.exists():
        pl.fail('Zieldatei %s existiert nicht' % path)
        return
    t = p.read_text()
    if MARKER in t:
        print('  Tex-Cache bereits vorhanden (Marker: %s).' % MARKER)
        return

    n_bind = len(re.findall(r'\bglBindTexture\s*\(', t))
    if n_bind == 0:
        pl.fail('kein glBindTexture in %s gefunden - Cache waere wirkungslos' % path)
        return
    if not re.search(r'\bGLuint\b', t) and not re.search(r'#\s*include\s*[<"][^>"]*(GL|gl)', t):
        pl.fail('keine GL-Typen/Header erkennbar - Wrapper koennte nicht kompilieren')
        return

    ins = pl.last_include_end(t)
    if ins < 0:
        pl.fail('kein #include gefunden')
        return
    t = t[:ins] + BLOCK + t[ins:]
    p.write_text(t)
    print('  Tex-Cache eingebaut (%d glBindTexture-Aufrufe laufen jetzt durch den Wrapper).' % n_bind)
    print('  Notausschalter: WOTS2_NO_TEXCACHE=1')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    pl.finish()
    print('Fertig.')
