#!/usr/bin/env python3
"""
patches/wots2-npc-lod-closer.py

Verschiebt die LOD-2-Umschaltschwelle in Chara_Draw (src/game/chara.cpp)
von 12.0 auf 8.0 Weltunits (Default).

Hintergrund:
  Chara_Draw waehlt das Modell nach self->cameraDistance: unter 12.0
  das detaillierte, ab 12.0 das niedrigste (LOD 2). In der Stadt stehen
  viele NPCs innerhalb von 12 Units — die Mali-G31 hat fuer deren hohe
  Vertex-Zahlen keinen Durchsatz.

  WOTS2_NPC_LOD_DIST=N setzt die Schwelle in Units. 12 = Original,
  0 = immer LOD 2, 100 = nie LOD 2.

Idempotent ueber Marker 'wots2-npc-lod-closer.py'.

Zieldatei: src/game/chara.cpp
Aufruf:    python3 patches/wots2-npc-lod-closer.py src/game/chara.cpp

Python 3.6+ kompatibel.
"""
import sys
import pathlib


MARKER = "wots2-npc-lod-closer.py"

OLD = '''        CharaModels_Draw(self, self->cameraDistance < 12.0f ? (self->bodyType == 1 ? 0 : self->_b0) : 2);
'''

NEW = '''        // wots2-npc-lod-closer.py
        // Native: die LOD-2-Umschaltschwelle ist konfigurierbar, Default 8.0
        // (das Original nimmt 12.0). WOTS2_NPC_LOD_DIST=N setzt sie in
        // Weltunits; 0 = immer LOD 2, 12 = wie im Original, 100 = nie.
        {
            static const float s_wots2_lod_dist = getenv("WOTS2_NPC_LOD_DIST")
                ? (float)atof(getenv("WOTS2_NPC_LOD_DIST")) : 8.0f;
            CharaModels_Draw(self, self->cameraDistance < s_wots2_lod_dist
                ? (self->bodyType == 1 ? 0 : self->_b0) : 2);
        }
'''


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    if MARKER in t:
        print('  NPC-LOD-Closer bereits vorhanden.')
        return
    if OLD not in t:
        print('  FEHLER: CharaModels_Draw-Aufruf nicht gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t.replace(OLD, NEW, 1)
    p.write_text(t)
    print('  NPC-LOD-Closer eingebaut (Default 8.0 statt 12.0).')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/game/chara.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
