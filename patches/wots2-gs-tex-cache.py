#!/usr/bin/env python3
"""
patches/wots2-gs-tex-cache.py   (v3)

Texturzustands-Cache fuer src/hal/gs.cpp. Spart GL-Aufrufe, die nichts aendern:

  1. glBindTexture(GL_TEXTURE_2D, id) wird uebersprungen, wenn id auf der
     aktiven Textureinheit schon gebunden ist.
  2. glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S/T, ...) wird
     uebersprungen, wenn die Textur diesen Wert schon hat. Der Mesh-Pfad
     setzt WRAP_S und WRAP_T bei JEDEM Draw (2 x ~400 Aufrufe pro Frame),
     obwohl der Zustand an der Textur haengt und erhalten bleibt.

Warum v3 statt v2: Der alte Patch (v1) hatte eine 'static'-Variable in der
Zeichenschleife, die andere Bind-Stellen nicht kennt (falsche Texturen).
v2/v3 setzen den Cache in gs.cpp selbst ein und verfolgen dabei:
  * ALLE glBindTexture/glActiveTexture/glDeleteTextures der Datei (Wrapper),
  * die aktive Textureinheit (gs.cpp nutzt GL_TEXTURE0..4),
  * geloeschte Texturen (Cache-Eintraege werden verworfen).
Nur GL_TEXTURE_2D wird gecacht, alle anderen Ziele (zum Beispiel
GL_TEXTURE_2D_ARRAY) gehen unveraendert durch.

Notausschalter zur Laufzeit:
  WOTS2_NO_TEXCACHE=1    beides aus (Originalverhalten)
  WOTS2_NO_WRAPCACHE=1   nur die WRAP-Parameter-Pruefung aus

Grenze: Bindet eine ANDERE .cpp-Datei Texturen, kennt der Cache das nicht.
Die Wrapper heissen wots2c_* (nicht wots2_gl*), damit sie nicht mit Namen aus
hal/gl_loader.h kollidieren.

Idempotent: Marker 'wots2_gs_tex_cache_v3'.
Zieldatei: src/hal/gs.cpp
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wots2_patchlib as pl  # noqa: E402

MARKER = "wots2_gs_tex_cache_v3"

BLOCK = '''
// wots2_gs_tex_cache_v3 (wots2-gs-tex-cache.py)
#include <cstdint>
#include <cstdlib>
#include <vector>
static inline bool wots2_texcache_on() {
    static const bool on = (getenv("WOTS2_NO_TEXCACHE") == nullptr);
    return on;
}
static inline bool wots2_wrapcache_on() {
    static const bool on = (getenv("WOTS2_NO_WRAPCACHE") == nullptr);
    return on;
}
static uint32_t wots2_tex_bound[32];     // gebundene GL_TEXTURE_2D-ID + 1 je Einheit, 0 = unbekannt
static unsigned wots2_tex_unit = 0;      // aktive Einheit (32 = ausserhalb, nicht gecacht)
static std::vector<GLint> wots2_wrap_s, wots2_wrap_t;   // je Textur-ID: zuletzt gesetzter Wert, 0 = unbekannt

static inline void wots2c_BindTexture(GLenum target, GLuint tex) {
    if (target == GL_TEXTURE_2D && wots2_tex_unit < 32 && wots2_texcache_on()) {
        if (wots2_tex_bound[wots2_tex_unit] == (uint32_t)tex + 1u)
            return;
        wots2_tex_bound[wots2_tex_unit] = (uint32_t)tex + 1u;
    }
    glBindTexture(target, tex);
}
static inline void wots2c_ActiveTexture(GLenum unit) {
    wots2_tex_unit = (unit >= GL_TEXTURE0 && unit < GL_TEXTURE0 + 32u) ? (unsigned)(unit - GL_TEXTURE0) : 32u;
    glActiveTexture(unit);
}
static inline void wots2c_DeleteTextures(GLsizei n, const GLuint* tex) {
    for (GLsizei i = 0; i < n; i++) {
        for (unsigned u = 0; u < 32; u++)
            if (wots2_tex_bound[u] == (uint32_t)tex[i] + 1u)
                wots2_tex_bound[u] = 0;
        if (tex[i] < wots2_wrap_s.size()) wots2_wrap_s[tex[i]] = 0;
        if (tex[i] < wots2_wrap_t.size()) wots2_wrap_t[tex[i]] = 0;
    }
    glDeleteTextures(n, tex);
}
static inline void wots2c_TexParameteri(GLenum target, GLenum pname, GLint param) {
    if (target == GL_TEXTURE_2D && (pname == GL_TEXTURE_WRAP_S || pname == GL_TEXTURE_WRAP_T) &&
        wots2_tex_unit < 32 && wots2_texcache_on() && wots2_wrapcache_on()) {
        const uint32_t b = wots2_tex_bound[wots2_tex_unit];
        if (b > 1u && b - 1u < (1u << 20)) {          // bekannte Textur (ID 0 = Standardtextur: nicht cachen)
            const size_t id = (size_t)(b - 1u);
            std::vector<GLint>& vec = (pname == GL_TEXTURE_WRAP_S) ? wots2_wrap_s : wots2_wrap_t;
            if (vec.size() <= id)
                vec.resize(id + 256, 0);
            if (vec[id] == param)
                return;
            vec[id] = param;
        }
    }
    glTexParameteri(target, pname, param);
}
#undef glBindTexture
#undef glActiveTexture
#undef glDeleteTextures
#undef glTexParameteri
#define glBindTexture wots2c_BindTexture
#define glActiveTexture wots2c_ActiveTexture
#define glDeleteTextures wots2c_DeleteTextures
#define glTexParameteri wots2c_TexParameteri
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
    n_wrap = len(re.findall(r'glTexParameteri\s*\(\s*GL_TEXTURE_2D\s*,\s*GL_TEXTURE_WRAP_[ST]', t))
    if n_bind == 0:
        pl.fail('kein glBindTexture in %s gefunden - Cache waere wirkungslos' % path)
        return
    if re.search(r'\bglTexParameterf\s*\([^)]*WRAP|\bglTexParameteriv\s*\([^)]*WRAP', t):
        pl.fail('WRAP-Parameter werden auch ueber glTexParameterf/iv gesetzt - Wrap-Cache waere unsicher')
        return
    if not re.search(r'\bGLuint\b', t):
        pl.fail('keine GL-Typen erkennbar - Wrapper koennte nicht kompilieren')
        return

    ins = pl.last_include_end(t)
    if ins < 0:
        pl.fail('kein #include gefunden')
        return
    t = t[:ins] + BLOCK + t[ins:]
    p.write_text(t)
    print('  Tex-Cache eingebaut: %d glBindTexture, %d WRAP-glTexParameteri laufen durch Wrapper.' % (n_bind, n_wrap))
    print('  Notausschalter: WOTS2_NO_TEXCACHE=1 / WOTS2_NO_WRAPCACHE=1')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    pl.finish()
    print('Fertig.')
