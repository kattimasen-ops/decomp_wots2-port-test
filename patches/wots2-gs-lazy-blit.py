#!/usr/bin/env python3
"""
patches/wots2-gs-lazy-blit.py   (v1)

Spart pro Frame eine Vollbild-Kopie in src/hal/gs.cpp.

end_frame() kopiert nach jedem Frame das fertige Bild per glBlitFramebuffer
in einen zweiten Framebuffer (s_lastFbo). Gebraucht wird diese Kopie nur von
read_frame() und damit nur von Mono_Keep (hle.cpp:1271), einem seltenen
Effekt. Auf einer Tile-basierten Mali-GPU bedeutet die Kopie jedes Mal einen
Render-Pass-Abschluss samt Lesen und Schreiben des ganzen Bildes.

Neu: Die Kopie entsteht erst in read_frame(). Das ist gleichwertig, weil s_fbo
nach end_frame() das fertige Bild behaelt, bis play() im naechsten Frame mit
FrameBegin loescht; read_frame() wird vom Spiel dazwischen aufgerufen (im
Update, vor dem naechsten play()).

  * wots2_keep_frame(): der unveraenderte Original-Block (Anlegen + Blit).
  * end_frame():        ruft ihn nur noch mit WOTS2_NO_LAZYBLIT=1 auf.
  * read_frame():       ruft ihn selbst auf (wenn schon ein Frame fertig ist),
                        NACH dem Sichern der Framebuffer-Bindung, damit die
                        Bindung danach wie vorher wiederhergestellt wird.

Notausschalter: WOTS2_NO_LAZYBLIT=1 (Originalverhalten).

Idempotent: Marker 'wots2_gs_lazy_blit_v1'.
Zieldatei: src/hal/gs.cpp
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wots2_patchlib as pl  # noqa: E402

MARKER = "wots2_gs_lazy_blit_v1"

KEEP_BLOCK = '''    if (s_lastFbo == 0) {
        s_lastTex = create_texture(nullptr, s_physW, s_physH);
        glGenFramebuffers(1, &s_lastFbo);
        glBindFramebuffer(GL_FRAMEBUFFER, s_lastFbo);
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, s_lastTex, 0);
    }
    glBindFramebuffer(GL_READ_FRAMEBUFFER, s_fbo);
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER, s_lastFbo);
    glBlitFramebuffer(0, 0, s_physW, s_physH, 0, 0, s_physW, s_physH, GL_COLOR_BUFFER_BIT, GL_NEAREST);'''

HELPER = '''// wots2_gs_lazy_blit_v1 (wots2-gs-lazy-blit.py)
static inline bool wots2_lazy_blit_on() {
    static const bool on = (getenv("WOTS2_NO_LAZYBLIT") == nullptr);
    return on;
}
// Das fertige Bild in s_lastFbo festhalten (der Block, den end_frame() frueher jedes Mal machte).
static void wots2_keep_frame() {
''' + KEEP_BLOCK + '''
}

'''

READ_OLD = '''if (s_lastFbo == 0)
        return;
    static GLuint small = 0, smallTex = 0;
    GLint was = 0;
    glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &was);'''

READ_NEW = '''if (wots2_lazy_blit_on() ? (s_frame == 0) : (s_lastFbo == 0))
        return;
    static GLuint small = 0, smallTex = 0;
    GLint was = 0;
    glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &was);
    if (wots2_lazy_blit_on())
        wots2_keep_frame();                 // Kopie erst jetzt, wo sie wirklich gebraucht wird'''

END_SIG = r'^void\s+end_frame\s*\(\s*\)'
READ_SIG = r'^void\s+read_frame\s*\(\s*std::vector<u8>\s*&\s*rgba\s*\)'


def patch(path):
    p = pathlib.Path(path)
    if not p.exists():
        pl.fail('Zieldatei %s existiert nicht' % path)
        return
    t = p.read_text()
    if MARKER in t:
        print('  Lazy-Blit bereits vorhanden (Marker: %s).' % MARKER)
        return

    # --- end_frame: den Block finden ---
    he = pl.find_function(t, END_SIG)
    if he is None:
        pl.fail('end_frame() nicht gefunden')
        return
    es, eb, ee = he
    body = t[eb:ee]
    ms = list(re.finditer(pl.flex(KEEP_BLOCK), body))
    if len(ms) != 1:
        pl.fail('end_frame: Blit-Block %d Treffer statt genau 1 (hat ein anderer Patch ihn geaendert?)' % len(ms))
        return
    m = ms[0]
    new_body = body[:m.start()] + 'if (!wots2_lazy_blit_on())\n        wots2_keep_frame();' + body[m.end():]
    t = t[:eb] + new_body + t[ee:]

    # --- read_frame ---
    hr = pl.find_function(t, READ_SIG)
    if hr is None:
        pl.fail('read_frame(std::vector<u8>&) nicht gefunden')
        return
    rs, rb, re_ = hr
    rbody = t[rb:re_]
    mr = list(re.finditer(pl.flex(READ_OLD), rbody))
    if len(mr) != 1:
        pl.fail('read_frame: Anfang %d Treffer statt genau 1' % len(mr))
        return
    r = mr[0]
    t = t[:rb] + rbody[:r.start()] + READ_NEW + rbody[r.end():] + t[re_:]

    # --- Helfer vor end_frame ---
    he = pl.find_function(t, END_SIG)
    ins = he[0]
    # Kommentarblock direkt vor der Funktion nicht auseinanderreissen
    while True:
        prev_end = ins - 1
        if prev_end < 0:
            break
        prev_start = t.rfind('\n', 0, prev_end) + 1
        if t[prev_start:prev_end].lstrip().startswith('//'):
            ins = prev_start
        else:
            break
    for name in ('s_lastFbo', 's_lastTex', 'create_texture', 's_frame', 's_physW'):
        if not re.search(r'\b%s\b' % name, t[:ins]):
            pl.fail('%s ist vor end_frame() nicht deklariert' % name)
            return
    t = t[:ins] + HELPER + t[ins:]
    p.write_text(t)
    print('  Lazy-Blit eingebaut: Vollbild-Kopie nur noch in read_frame().')
    print('  Notausschalter: WOTS2_NO_LAZYBLIT=1')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    pl.finish()
    print('Fertig.')
