#!/usr/bin/env python3
"""
FX-Skalierung fuer world_effects.cpp.

Hintergrund:
  Ein Kampf mit Schnitt-Bluteffekten, Funken und Schwertern, die Waffen
  verlieren, spawnt pro Treffer 10–40 einzelne Effekte. Jeder ist ein
  eigener Draw-Call ueber die PS2-Sprites, und die Mali-G31 erreicht
  ihre Draw-Call-Grenze deutlich vor der Fuellraten-Grenze.

  Der Patch fuehrt einen globalen Skalierungsfaktor ein, der die
  Spawn-Anzahl in fuenf konkreten Schleifen reduziert. Steuerung per
  Umgebungsvariable WOTS2_FX_SCALE:
    1.0  unveraendert (Default)
    0.5  halbiert
    0.0  keine Effekte

  Betroffen sind nur die Spawns, die mehrere Effekte auf einmal
  erzeugen. Einzel-Spawns (z. B. ein Schwerthieb, ein Aufprall) bleiben
  unveraendert — sonst wuerden Treffer ganz verschwinden.

Sicher: der Zaehler startet bei 0, die Schleifen sind reine
for-Schleifen ohne Abbruchbedingung. Ein Faktor von 0.0 ergibt leere
Schleifen, kein Fehlverhalten.

Idempotent ueber Marker.

Python 3.6+ kompatibel.
"""
import re
import sys
import pathlib


HELPER = r'''
// ── [WOTS2-PORT] FX-Skalierung ────────────────────────────────────────────
// wots2-fx-scale.py. Liesst WOTS2_FX_SCALE einmal, memoisiert das Ergebnis.
static float wots2_fx_scale_value(void) {
    static float s = -1.0f;
    if (s < 0.0f) {
        s = 1.0f;
        if (const char* e = getenv("WOTS2_FX_SCALE")) {
            const float v = (float)atof(e);
            s = v < 0.0f ? 0.0f : (v > 1.0f ? 1.0f : v);
        }
    }
    return s;
}
static inline int wots2_fx_count(int n) {
    const float s = wots2_fx_scale_value();
    if (s >= 0.999f)
        return n;
    const int r = (int)((float)n * s + 0.5f);
    return r < 0 ? 0 : r;
}
'''

MARKER = "wots2-fx-scale.py"


# Jeder Eintrag: (Ankertext, ersetzter Text)
# Anker sind eindeutig genug, um sie im Quelltext zu finden.
REPLACEMENTS = [
    # Fx_BreakBox: 10 dust + 10 splinters
    (
        '    for (int i = 0; i < 10; i++) {\n        Mote* dust = NewMote(0x2ED200u, 1);',
        '    for (int i = 0; i < wots2_fx_count(10); i++) {\n        Mote* dust = NewMote(0x2ED200u, 1);'
    ),
    # Shards_Start: 30 shards
    (
        '    for (int i = 0; i < 30; i++) {\n        Shard* shard = static_cast<Shard*>(MemAlloc(0x80));',
        '    for (int i = 0; i < wots2_fx_count(30); i++) {\n        Shard* shard = static_cast<Shard*>(MemAlloc(0x80));'
    ),
    # Flash_Start: 10 streaks (Eigenschatten des Charakters)
    (
        '    for (int i = 0; i < 10; i++) {\n        Streak* streak = static_cast<Streak*>(MemAlloc(0x40));\n        memset(streak, 0, 0x40);\n        Effect_Ctor(&streak->base);\n        streak->base.vtable = 0x2ECC00u;\n        streak->base.type = 0x12;\n        Streak_Start(streak, self->pos, self->rgb);',
        '    for (int i = 0; i < wots2_fx_count(10); i++) {\n        Streak* streak = static_cast<Streak*>(MemAlloc(0x40));\n        memset(streak, 0, 0x40);\n        Effect_Ctor(&streak->base);\n        streak->base.vtable = 0x2ECC00u;\n        streak->base.type = 0x12;\n        Streak_Start(streak, self->pos, self->rgb);'
    ),
    # CharaSounds_Play case 28: 10 streaks (Guard-Break)
    (
        '        for (int i = 0; i < 10; i++) {\n            Streak* streak = static_cast<Streak*>(MemAlloc(0x40));\n            memset(streak, 0, 0x40);\n            Effect_Ctor(&streak->base);\n            streak->base.vtable = 0x2ECC00u;\n            streak->base.type = 0x12;\n            Streak_Start(streak, at, 0x80709090u);',
        '        for (int i = 0; i < wots2_fx_count(10); i++) {\n            Streak* streak = static_cast<Streak*>(MemAlloc(0x40));\n            memset(streak, 0, 0x40);\n            Effect_Ctor(&streak->base);\n            streak->base.vtable = 0x2ECC00u;\n            streak->base.type = 0x12;\n            Streak_Start(streak, at, 0x80709090u);'
    ),
    # Fx_Burst kind 7 (Explosion): 10 particles of order 15
    (
        '        for (int i = 0; i < 10; i++)\n            RenderMgr_AddWorldEffect(Mgr(), 0x19, scratch, 0x0F);',
        '        for (int i = 0; i < wots2_fx_count(10); i++)\n            RenderMgr_AddWorldEffect(Mgr(), 0x19, scratch, 0x0F);'
    ),
]


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    if MARKER in t:
        print('  FX-Skalierung bereits vorhanden.')
        return

    # 1. Helper nach den Includes einfuegen.
    last_inc = list(re.finditer(r'^#include [<"][^\n]+[>\"]\n', t, re.M))
    if not last_inc:
        print('  FEHLER: kein #include gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t[:last_inc[-1].end()] + HELPER + t[last_inc[-1].end():]

    # 2. Die fuenf Spawn-Schleifen ersetzen.
    found = 0
    for old, new in REPLACEMENTS:
        if old not in t:
            print('  HINWEIS: Anker nicht gefunden (schon gepatcht?):')
            print('    %r' % old[:80])
            continue
        t = t.replace(old, new, 1)
        found += 1

    p.write_text(t)
    print('  FX-Spawn-Schleifen skaliert: %d von %d' % (found, len(REPLACEMENTS)))


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/game/world_effects.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
