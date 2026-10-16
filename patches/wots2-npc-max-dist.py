#!/usr/bin/env python3
"""
patches/wots2-npc-max-dist.py

Harte Distanz-Cull fuer NPCs in src/game/chara.cpp.

Hintergrund:
  CharaOther_Cull laesst bisher alle NPCs durch, deren cameraDistance
  groesser ist als `nearest` (der Abstand des naechsten Feindes). Bei
  vielen NPCs ist das kein wirksamer Filter.

  Diese Erweiterung fuegt eine optionale harte Obergrenze hinzu:
  WOTS2_NPC_MAX_DIST=N. Default 0 = aus (das Verhalten bleibt wie
  bisher). Ein Wert um 18-22 hilft in der Stadt, laesst aber Figuren
  aus dem Sichtfeld poppen.

Idempotent ueber Marker 'wots2-npc-max-dist.py'.

Zieldatei: src/game/chara.cpp
Aufruf:    python3 patches/wots2-npc-max-dist.py src/game/chara.cpp

Python 3.6+ kompatibel.
"""
import sys
import pathlib


MARKER = "wots2-npc-max-dist.py"

OLD = '''static int CharaOther_Cull(float nearest, Chara* self, int pass) {
    if (!self->visible)
        return 0;
    if (pass != 0 && nearest > self->cameraDistance)
        return 0;
    return self->loaded;
}
'''

NEW = '''static int CharaOther_Cull(float nearest, Chara* self, int pass) {
    if (!self->visible)
        return 0;
    // wots2-npc-max-dist.py
    // Native: harte Obergrenze fuer NPCs. 0 (Default) = aus.
    static const float s_wots2_npc_max_dist = getenv("WOTS2_NPC_MAX_DIST")
        ? (float)atof(getenv("WOTS2_NPC_MAX_DIST")) : 0.0f;
    if (s_wots2_npc_max_dist > 0.0f && self->cameraDistance > s_wots2_npc_max_dist)
        return 0;
    if (pass != 0 && nearest > self->cameraDistance)
        return 0;
    return self->loaded;
}
'''


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    if MARKER in t:
        print('  NPC-Max-Dist bereits vorhanden.')
        return
    if OLD not in t:
        print('  FEHLER: CharaOther_Cull() nicht gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t.replace(OLD, NEW, 1)
    p.write_text(t)
    print('  NPC-Max-Dist eingebaut (WOTS2_NPC_MAX_DIST, Default 0=aus).')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/game/chara.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
