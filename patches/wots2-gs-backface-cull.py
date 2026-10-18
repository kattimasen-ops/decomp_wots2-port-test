#!/usr/bin/env python3
"""
patches/wots2-gs-backface-cull.py   (v2, nur auf Wunsch aktiv)

Backface-Culling fuer die 3D-Ansichten Map und Model in src/hal/gs.cpp.

Warum v2: Der alte Patch schaltete GL_CULL_FACE in state_3d() EIN und nie
wieder aus. Danach liefen auch die 2D-Draws (HUD, Menues) und die
Bildschirm-Quads (DrawDepth) mit Culling, und je nach Windungsrichtung
verschwaenden sie. Ausserdem ist die Windungsrichtung der PS2-Meshes nicht
bekannt: Der 3D-Vertex-Shader dreht y um, und viele PS2-Modelle
(Haare, Stoff, Gras, Fahnen) sind absichtlich zweiseitig. Deshalb ist das
Culling standardmaessig AUS und per Umgebungsvariable zuschaltbar:

  WOTS2_BACKFACE_CULL=0 (Standard)  kein Culling (Originalverhalten)
  WOTS2_BACKFACE_CULL=1             Rueckseiten (GL_BACK) weglassen
  WOTS2_BACKFACE_CULL=2             Vorderseiten (GL_FRONT) weglassen

Fehlen bei Modus 1 die Aussenseiten der Figuren, nimm Modus 2. Fehlen in
beiden Modi Teile (Haare, Gras), dann bringt Culling hier nichts.

Eingriffe:
  * Helfer wots2_cull_3d(kind) vor state_3d(): schaltet nur fuer View::Map
    und View::Model ein, sonst aus.
  * state_3d() ruft ihn am Ende auf.
  * state_2d() schaltet das Culling immer wieder aus.

Idempotent: Marker 'wots2_gs_backface_cull_v2'.
Zieldatei: src/hal/gs.cpp
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wots2_patchlib as pl  # noqa: E402

MARKER = "wots2_gs_backface_cull_v2"

HELPER = '''// wots2_gs_backface_cull_v2 (wots2-gs-backface-cull.py)
static inline int wots2_cull_mode() {
    static const int mode = []() -> int {
        const char* e = getenv("WOTS2_BACKFACE_CULL");
        return e != nullptr ? atoi(e) : 0;
    }();
    return mode;
}
static bool s_wots2CullOn = false;
static inline void wots2_cull_set(bool on, GLenum face = GL_BACK) {
    if (on) {
        glCullFace(face);
        if (!s_wots2CullOn) {
            glEnable(GL_CULL_FACE);
            s_wots2CullOn = true;
        }
    } else if (s_wots2CullOn) {
        glDisable(GL_CULL_FACE);
        s_wots2CullOn = false;
    }
}
static inline void wots2_cull_3d(int kind) {
    const int mode = wots2_cull_mode();
    const bool want = mode != 0 && (kind == (int)hal::gs::View::Map || kind == (int)hal::gs::View::Model);
    wots2_cull_set(want, mode == 2 ? GL_FRONT : GL_BACK);
}

'''

STATE3D_SIG = r'static\s+void\s+state_3d\s*\(\s*const\s+float\s*\*\s*mvp\s*,\s*float\s+xscale\s*,\s*int\s+kind\s*=\s*0\s*\)'
STATE2D_SIG = r'static\s+void\s+state_2d\s*\(\s*\)'


def patch(path):
    p = pathlib.Path(path)
    if not p.exists():
        pl.fail('Zieldatei %s existiert nicht' % path)
        return
    t = p.read_text()
    if MARKER in t:
        print('  Backface-Cull bereits vorhanden (Marker: %s).' % MARKER)
        return

    h3 = pl.find_function(t, STATE3D_SIG)
    if h3 is None:
        pl.fail('state_3d(const float*, float, int kind = 0) nicht gefunden')
        return
    s3, b3, e3 = h3
    body3 = t[b3:e3]
    mdepth = list(re.finditer(pl.flex('glDepthMask(GL_TRUE);'), body3))
    if len(mdepth) < 1:
        pl.fail('state_3d: glDepthMask(GL_TRUE); nicht gefunden')
        return
    last = mdepth[-1]
    new_body3 = body3[:last.end()] + '\n    wots2_cull_3d(kind);' + body3[last.end():]
    t = t[:b3] + new_body3 + t[e3:]

    # state_2d (liegt hinter state_3d, Positionen neu bestimmen)
    h2 = pl.find_function(t, STATE2D_SIG)
    if h2 is None:
        pl.fail('state_2d() nicht gefunden (Definition mit Rumpf)')
        return
    s2, b2, e2 = h2
    body2 = t[b2:e2]
    dis = list(re.finditer(pl.flex('glDisable(GL_DEPTH_TEST);'), body2))
    if len(dis) != 1:
        pl.fail('state_2d: glDisable(GL_DEPTH_TEST); %d Treffer statt 1' % len(dis))
        return
    d = dis[0]
    new_body2 = body2[:d.end()] + '\n    wots2_cull_set(false);' + body2[d.end():]
    t = t[:b2] + new_body2 + t[e2:]

    # Helfer vor state_3d (Position erneut bestimmen)
    h3 = pl.find_function(t, STATE3D_SIG)
    ins = h3[0]
    t = t[:ins] + HELPER + t[ins:]

    p.write_text(t)
    print('  Backface-Cull-Schalter eingebaut (Standard AUS).')
    print('  Test: WOTS2_BACKFACE_CULL=1 oder =2')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    pl.finish()
    print('Fertig.')
