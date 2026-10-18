#!/usr/bin/env python3
"""
patches/wots2-no-sword-shadow.py   (v2)

Zeichnet den Klingenschweif (CharaSwords_DrawShadow) nur noch fuer den
Spieler. In einer belebten Stadt sparen die Schweife aller NPCs pro Frame
einige Draws.

Der Spieler hat die Figuren-ID 0 (siehe Chara_BaseCtor: 'id == 0' ist der
Spieler). Der Patch aendert in Chara_Draw nur die Bedingung
    if (self->swords != 0)
zu
    if (self->swords != 0 && self->id == 0)
und laesst den Rest der Zeile samt Kommentar stehen.

v2: Der alte Patch lief nie (main() wurde nicht aufgerufen). Jetzt
whitespace-tolerant, nur innerhalb von Chara_Draw, mit Fehlermeldung.

Idempotent: Marker 'WOTS2_NO_SWORD_SHADOW'.
Zieldatei: src/game/chara.cpp
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wots2_patchlib as pl  # noqa: E402

MARKER = "WOTS2_NO_SWORD_SHADOW"

SIG = (r'^static\s+int\s+Chara_Draw\s*\(\s*Chara\s*\*\s*self\s*,\s*int\s+shown\s*,'
       r'\s*const\s+float\s*\*\s*wind\s*\)')

PAT = re.compile(
    r'if\s*\(\s*self->swords\s*!=\s*0\s*\)(\s*)'
    r'(CharaSwords_DrawShadow\s*\(\s*P\(self->swords\)\s*,\s*Body\(self\)\s*\)\s*;)')


def patch(path):
    p = pathlib.Path(path)
    if not p.exists():
        pl.fail('Zieldatei %s existiert nicht' % path)
        return
    t = p.read_text()
    if MARKER in t:
        print('  No-Sword-Shadow bereits vorhanden.')
        return

    hit = pl.find_function(t, SIG)
    if hit is None:
        pl.fail('Chara_Draw nicht gefunden')
        return
    s, b, e = hit
    body = t[b:e]
    ms = list(PAT.finditer(body))
    if len(ms) != 1:
        pl.fail('CharaSwords_DrawShadow-Aufruf in Chara_Draw: %d Treffer statt genau 1' % len(ms))
        return
    m = ms[0]
    new = 'if (self->swords != 0 && self->id == 0 /* %s */)%s%s' % (MARKER, m.group(1), m.group(2))
    body = body[:m.start()] + new + body[m.end():]
    p.write_text(t[:b] + body + t[e:])
    print('  Klingenschweif nur noch fuer den Spieler (id == 0).')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/game/chara.cpp'
    print('Patche %s' % target)
    patch(target)
    pl.finish()
    print('Fertig.')
