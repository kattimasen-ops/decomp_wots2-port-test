#!/usr/bin/env python3
"""
patches/wots2-gs-lazy-blit.py   (v1.1)  --  NICHT EMPFOHLEN, in der .yml deaktiviert

ACHTUNG, bekannter Konflikt: Dieser Patch geht davon aus, dass s_fbo nach
end_frame() das fertige Bild behaelt. Das stimmt nicht, sobald
wots2-gs-invalidate.py am Ende von end_frame() glInvalidateFramebuffer auf
s_fbo aufruft: Danach ist der Inhalt undefiniert (auf der Mali-G31 meist
schwarz). Die verzoegerte Kopie in read_frame() liefert dann ein schwarzes Bild.

Folge im Spiel: read_frame() wird von Effect.Monotone Modus 6 aufgerufen (hle.cpp,
Mono_Keep: das Standbild unter der Erzaehlung, zum Beispiel nach dem ersten Kampf).
Das Standbild ist dann schwarz, der Ton laeuft weiter, das Bild bleibt schwarz.

Der Patch prueft deshalb jetzt, ob end_frame() eine Invalidierung enthaelt, und
wendet sich in dem Fall NICHT an (PATCH-FEHLER). Zur Laufzeit stellt
WOTS2_NO_LAZYBLIT=1 das Original-Verhalten wieder her (Kopie in end_frame()).

Was der Patch macht (wenn er angewendet wird)
---------------------------------------------
end_frame() kopiert nach jedem Frame das fertige Bild per glBlitFramebuffer in
s_lastFbo. Gebraucht wird die Kopie nur von read_frame(). Der Patch verschiebt
die Kopie in read_frame(). Ersparnis: eine Vollbild-Kopie pro Frame, geschaetzt
1-2 ms; gemessen ist das nicht.

  * wots2_keep_frame(): der unveraenderte Original-Block (Anlegen + Blit).
  * end_frame():        ruft ihn nur noch mit WOTS2_NO_LAZYBLIT=1 auf.
  * read_frame():       ruft ihn selbst auf, NACH dem Sichern der Bindung.

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
    if re.search(r'nvalidate', body):
        pl.fail('end_frame() invalidiert Framebuffer (wots2-gs-invalidate.py): s_fbo ist danach nicht mehr '
                'lesbar, die verzoegerte Kopie waere schwarz (Standbild in Effect.Monotone Modus 6). '
                'Lazy-Blit wird NICHT angewendet.')
        return
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
