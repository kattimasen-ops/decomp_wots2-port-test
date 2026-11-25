#!/usr/bin/env python3
"""
patches/wots2-npc-max-dist.py   (v2)

Harte Zeichen-Grenze fuer NPCs in src/game/chara.cpp.
WOTS2_NPC_MAX_DIST=N (Kamera-Distanz). Default 0 = aus.

Warum v2: Die alte Version machte die Grenze in CharaOther_Cull(). Das ist aber
eine virtuelle Methode der Figur (vtable 0x269240), die auch die ORIGINALE
Spiel-Logik aufrufen kann, nicht nur das Zeichnen. Meldet sie fuer ferne
Figuren 0, sehen Skripte diese Figuren als 'nicht geladen/nicht da'. Eine
Skript-Szene, die auf eine entfernte Figur wartet, haengt dann fuer immer.
(Nach dem ersten Kampf blieb das Bild schwarz: der Ueberblend-Effekt hielt
voll gedeckt, und das Skript startete die naechste Szene nie.)

v2 aendert CharaOther_Cull NICHT mehr und schneidet stattdessen erst beim
Zeichnen: In Chara_Draw wird nur der ZEICHEN-Teil ('if (shown) {...}') fuer
ferne NPCs ausgelassen. Skelett-Update und Haar-Schwung laufen wie vorher, die
Spiel-Logik sieht nichts Neues. Der Spieler (id 0) ist ausgenommen.

Idempotent ueber Marker 'wots2_npc_max_dist_v2'.
Zieldatei: src/game/chara.cpp
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wots2_patchlib as pl  # noqa: E402

MARKER = "wots2_npc_max_dist_v2"

SIG = (r'^static\s+int\s+Chara_Draw\s*\(\s*Chara\s*\*\s*self\s*,\s*int\s+shown\s*,'
       r'\s*const\s+float\s*\*\s*wind\s*\)')
ANCHOR = pl.flex('if (shown) {')

INSERT = '''    // wots2_npc_max_dist_v2 (wots2-npc-max-dist.py): ferne NPCs nicht zeichnen. Die Spiel-Logik
    // (CharaOther_Cull, Skelett-Update) bleibt unberuehrt, damit Skripte entfernte Figuren weiter sehen.
    static const float wots2_max_dist = []() -> float {
        const char* e = getenv("WOTS2_NPC_MAX_DIST");
        return e != nullptr ? (float)atof(e) : 0.0f;
    }();
    const bool wots2_far = wots2_max_dist > 0.0f && self->id != 0 && self->cameraDistance > wots2_max_dist;
    if (shown && !wots2_far) {'''


def patch(path):
    p = pathlib.Path(path)
    if not p.exists():
        pl.fail('Zieldatei %s existiert nicht' % path)
        return
    t = p.read_text()
    if MARKER in t:
        print('  NPC-Max-Dist bereits vorhanden (v2).')
        return
    if 'wots2-npc-max-dist.py' in t and MARKER not in t:
        pl.fail('die alte Version (v1, CharaOther_Cull) steckt schon in der Datei - nicht doppelt anwenden')
        return
    hit = pl.find_function(t, SIG)
    if hit is None:
        pl.fail('Chara_Draw nicht gefunden')
        return
    s, b, e = hit
    body = t[b:e]
    ms = list(re.finditer(ANCHOR, body))
    if len(ms) != 1:
        pl.fail('"if (shown) {" in Chara_Draw: %d Treffer statt genau 1' % len(ms))
        return
    m = ms[0]
    new_body = body[:m.start()] + INSERT + body[m.end():]
    t = t[:b] + new_body + t[e:]
    if '<cstdlib>' not in t and '<stdlib.h>' not in t:
        inc = pl.last_include_end(t)
        if inc < 0:
            pl.fail('kein #include gefunden - <cstdlib> konnte nicht ergaenzt werden')
            return
        t = t[:inc] + '#include <cstdlib>\n' + t[inc:]
    p.write_text(t)
    print('  NPC-Max-Dist (v2): nur das Zeichnen in Chara_Draw wird bei fernen NPCs ausgelassen.')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/game/chara.cpp'
    print('Patche %s' % target)
    patch(target)
    pl.finish()
    print('Fertig.')
