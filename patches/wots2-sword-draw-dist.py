#!/usr/bin/env python3
"""
patches/wots2-sword-draw-dist.py   (v1, neu geschrieben)

Zeichnet die Schwerter ferner Charaktere nicht mehr. Das spart pro Frame
einige Draw-Calls in belebten Szenen (Stadt: 350-450 Draws pro Frame).

Steuerung zur Laufzeit ueber die Umgebungsvariable
  WOTS2_SWORD_DRAW_DIST   Kamera-Distanz in Spieleinheiten
                          nicht gesetzt, 0 oder >= 999  ->  aus (Original)
Der Launcher WOTS2.sh setzt sie auf 8. Die Distanz ist die gleiche
'cameraDistance', die Chara_Draw auch fuer die Modell-LOD-Wahl benutzt.

Was gepatcht wird (nur in src/game/chara.cpp, nur in Chara_Draw):
  * Der Aufruf CharaSwords_Draw(P(self->swords), Body(self)) wird mit einer
    Distanzpruefung umgeben.
  * Der Schatten/Streifen der Klinge (CharaSwords_DrawShadow) bleibt
    absichtlich unangetastet. Den behandelt wots2-no-sword-shadow.py.
  * Ein kleiner Helfer wots2_sword_draw_dist() liest die Variable einmal.

Idempotent: Marker 'wots2_sword_draw_dist_v1'.

Zieldatei: src/game/chara.cpp
Aufruf:    python3 patches/wots2-sword-draw-dist.py src/game/chara.cpp
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wots2_patchlib as pl  # noqa: E402

MARKER = "wots2_sword_draw_dist_v1"

HELPER = '''// wots2_sword_draw_dist_v1 (wots2-sword-draw-dist.py)
// Schwerter ferner Charaktere nicht zeichnen. WOTS2_SWORD_DRAW_DIST ist die
// Kamera-Distanz; nicht gesetzt, 0 oder >= 999 bedeutet aus (Originalverhalten).
static inline float wots2_sword_draw_dist() {
    static const float dist = []() -> float {
        const char* e = getenv("WOTS2_SWORD_DRAW_DIST");
        if (e == nullptr || *e == '\\0')
            return 1.0e9f;
        const float v = (float)atof(e);
        return (v > 0.0f && v < 999.0f) ? v : 1.0e9f;
    }();
    return dist;
}

'''

CALL = 'CharaSwords_Draw(P(self->swords), Body(self));'

NEW_CALL = '''{
                if (self->cameraDistance < wots2_sword_draw_dist())
                    CharaSwords_Draw(P(self->swords), Body(self));
            }'''

SIG = (r'^static\s+int\s+Chara_Draw\s*\(\s*Chara\s*\*\s*self\s*,\s*int\s+shown\s*,'
       r'\s*const\s+float\s*\*\s*wind\s*\)')


def insertion_point(t, func_start):
    """Zeilenanfang oberhalb eines direkt vor der Funktion stehenden
    Kommentarblocks (damit der Kommentar bei der Funktion bleibt)."""
    pos = func_start
    while True:
        prev_end = pos - 1                      # das '\n' vor pos
        if prev_end < 0:
            break
        prev_start = t.rfind('\n', 0, prev_end) + 1
        line = t[prev_start:prev_end]
        if line.lstrip().startswith('//'):
            pos = prev_start
        else:
            break
    return pos


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()

    if MARKER in t:
        print('  Sword-Draw-Dist bereits vorhanden (Marker: %s).' % MARKER)
        return

    if 'cstdlib' not in t and '<stdlib.h>' not in t:
        pl.fail('<cstdlib> fehlt - getenv/atof koennten nicht deklariert sein')

    hit = pl.find_function(t, SIG)
    if hit is None:
        pl.fail('Chara_Draw nicht gefunden (Signatur geaendert oder Funktion umbenannt?)')
        return
    start, body_open, end = hit
    body = t[body_open:end]

    pat = re.compile(pl.flex(CALL))
    calls = list(pat.finditer(body))
    if len(calls) != 1:
        pl.fail('CharaSwords_Draw-Aufruf in Chara_Draw: %d Treffer statt genau 1 '
                '(hat ein frueherer Patch die Zeile veraendert?)' % len(calls))
        return
    m = calls[0]
    new_body = body[:m.start()] + NEW_CALL + body[m.end():]

    ins = insertion_point(t, start)
    t = t[:ins] + HELPER + t[ins:start] + t[start:body_open] + new_body + t[end:]
    p.write_text(t)

    print('  Sword-Draw-Dist eingebaut:')
    print('    Helfer wots2_sword_draw_dist(): OK')
    print('    Distanzpruefung um CharaSwords_Draw in Chara_Draw: OK')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/game/chara.cpp'
    print('Patche %s' % target)
    patch(target)
    pl.finish()
    print('Fertig.')
