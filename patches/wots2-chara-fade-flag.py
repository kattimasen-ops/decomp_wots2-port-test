#!/usr/bin/env python3
"""
patches/wots2-chara-fade-flag.py   (v1)

Markiert in src/native/hle_chara.cpp die 3D-Ansichten von Figuren, damit
wots2-gs-npc-fade.py sie am Ende der Sichtweite ausblenden kann.

Vor jedem hal::gs::begin_3d(..., who_of(g_drawing, ...)) (Koerper und
Ausruestung einer Figur) wird wots2_mark_chara() aufgerufen, als Komma-
Ausdruck: Der Aufruf bleibt ein einzelnes Statement, auch wenn er ohne
Klammern unter einem if steht.

Schatten-Ansichten und Props (who_of((u32)matrix, ...)) bleiben unmarkiert.

Die Variable g_wots2_chara_view ist hier ein SCHWACHES Symbol: Wird gs.cpp
nicht vom Gegenstueck gepatcht, gibt es kein Linker-Problem, es passiert dann
einfach nichts.

Idempotent: Marker 'wots2_mark_chara'.
Zieldatei: src/native/hle_chara.cpp
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wots2_patchlib as pl  # noqa: E402

MARKER = "wots2_mark_chara"

HELPER = '''
// wots2_mark_chara (wots2-chara-fade-flag.py): Gegenstueck in gs.cpp (wots2-gs-npc-fade.py)
extern "C" __attribute__((weak)) int g_wots2_chara_view;
static inline void wots2_mark_chara() {
    if (&g_wots2_chara_view != nullptr)
        g_wots2_chara_view = 1;
}
'''

CALL_RE = re.compile(r'hal::gs::begin_3d\s*\(\s*mvp\s*,\s*hal::gs::View::Model\s*,\s*who_of\s*\(\s*g_drawing\s*,')


def find_call_end(t, open_paren):
    """Index hinter der schliessenden Klammer des Aufrufs, dessen '(' bei open_paren steht."""
    depth = 0
    i = open_paren
    n = len(t)
    while i < n:
        c = t[i]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def patch(path):
    p = pathlib.Path(path)
    if not p.exists():
        pl.fail('Zieldatei %s existiert nicht' % path)
        return
    t = p.read_text()
    if MARKER in t:
        print('  Chara-Fade-Flag bereits vorhanden.')
        return

    hits = list(CALL_RE.finditer(t))
    if len(hits) < 1:
        pl.fail('kein begin_3d(mvp, View::Model, who_of(g_drawing, ...)) gefunden')
        return
    if len(hits) > 4:
        pl.fail('%d Treffer, erwartet 1 bis 4 - zu viele, bitte pruefen' % len(hits))
        return

    # von hinten nach vorn ersetzen
    for m in reversed(hits):
        start = m.start()
        paren = t.index('(', start + len('hal::gs::begin_3d') - 1)
        end = find_call_end(t, paren)
        if end < 0:
            pl.fail('Klammer des begin_3d-Aufrufs nicht abgeschlossen')
            return
        call = t[start:end]
        t = t[:start] + '(wots2_mark_chara(), ' + call + ')' + t[end:]

    inc = pl.last_include_end(t)
    if inc < 0:
        pl.fail('kein #include gefunden')
        return
    t = t[:inc] + HELPER + t[inc:]
    p.write_text(t)
    print('  %d Figuren-Ansichten markiert.' % len(hits))


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/native/hle_chara.cpp'
    print('Patche %s' % target)
    patch(target)
    pl.finish()
    print('Fertig.')
