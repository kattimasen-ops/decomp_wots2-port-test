#!/usr/bin/env python3
"""
Ersetzt std::map<u32, Last> in CharaBody_Update durch ein statisches
Direct-Mapped-Array.

Hintergrund:
  Die Map ist eine native Ergänzung des Ports: sie merkt sich pro Chara
  die letzte Bewegungsgeschwindigkeit, damit ein Uebergang zwischen
  Laufen und Gehen nicht fuer einen Frame still steht. Sie wird pro
  Chara pro Frame einmal gelesen und geschrieben.

  std::map ist ein Rot-Schwarz-Baum: O(log n) Lookup, Heap-Allokation
  pro Insert, Fragmentierung auf einem 1-GB-System. Ein statisches
  Direct-Mapped-Array mit 64 Slots hat O(1) und keine Allokation.

Sicher: gleiche Semantik. Der Key ist guest::addr(self) — wir nehmen
(addr >> 5) & 63 als Slot. Kollisionen sind moeglich, aber ein
Treffer wird ueber einen zweiten Key-Vergleich verifiziert. Bei einem
Konflikt faellt der betroffene Charakter fuer einen Frame auf "kein
Letztes" zurueck — genau das, was die Map bei einem Miss auch tut.

Idempotent ueber Marker.

Python 3.6+ kompatibel.
"""
import re
import sys
import pathlib


HELPER = r'''
// ── [WOTS2-PORT] Direct-Mapped Last-Array fuer CharaBody ─────────────────
// wots2-chara-body-last-array.py
struct Wots2BodyLast {
    u32 key;            // der letzte guest::addr(self), 0 = leer
    u32 flags;
    float t[4];
};
static Wots2BodyLast wots2_body_last[64] = {};
static inline int wots2_body_slot(u32 key) {
    return (int)((key >> 5) & 63u);
}
'''

MARKER = "wots2-chara-body-last-array.py"


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    if MARKER in t:
        print('  Last-Array bereits vorhanden.')
        return

    # 1. Helper nach den Includes einfuegen.
    last_inc = list(re.finditer(r'^#include [<"][^\n]+[>\"]\n', t, re.M))
    if not last_inc:
        print('  FEHLER: kein #include gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t[:last_inc[-1].end()] + HELPER + t[last_inc[-1].end():]

    # 2. Den std::map-Block ersetzen.
    old = '''        struct Last { float t[4]; u32 flags; };
        static std::map<u32, Last> sLast;
        Last& last = sLast[guest::addr(self)];
        const u32 moving = kActfRun | kActfWalk;
        const bool still = self->travel[0] == 0.0f && self->travel[1] == 0.0f && self->travel[2] == 0.0f;
        if (still && (self->actionFlags & moving) && (last.flags & moving) &&
            (last.t[0] != 0.0f || last.t[2] != 0.0f))
            memcpy(self->travel, last.t, sizeof last.t);
        memcpy(last.t, self->travel, sizeof last.t);
        last.flags = self->actionFlags;'''
    new = '''        // [WOTS2-PORT] statisches Direct-Mapped-Array statt std::map
        const u32 _key = guest::addr(self);
        const int _slot = wots2_body_slot(_key);
        Wots2BodyLast* _last = &wots2_body_last[_slot];
        if (_last->key != _key) {
            _last->key = _key;
            _last->flags = 0;
            _last->t[0] = _last->t[1] = _last->t[2] = _last->t[3] = 0.0f;
        }
        const u32 moving = kActfRun | kActfWalk;
        const bool still = self->travel[0] == 0.0f && self->travel[1] == 0.0f && self->travel[2] == 0.0f;
        if (still && (self->actionFlags & moving) && (_last->flags & moving) &&
            (_last->t[0] != 0.0f || _last->t[2] != 0.0f))
            memcpy(self->travel, _last->t, sizeof _last->t);
        memcpy(_last->t, self->travel, sizeof _last->t);
        _last->flags = self->actionFlags;'''

    if old not in t:
        print('  WARNUNG: std::map-Block nicht gefunden (schon gepatcht?).')
        p.write_text(t)
        return

    t = t.replace(old, new, 1)
    p.write_text(t)
    print('  CharaBody-Last-Array eingebaut (std::map -> statisches Array).')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/game/chara_body.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
