#!/usr/bin/env python3
"""
Cache fuer Collision_LoadCell: vermeidet wiederholtes memcpy derselben
Zelle.

Hintergrund:
  Collision_LineBlocked ruft in seiner zweiten Schleife pro Schritt
  CellAtIndex auf, und die Zelle wechselt nur, wenn (nx, nz) sich
  aendert. Bei einer Linie, die mehrere Schritte in derselben Zelle
  liegt, wird dieselbe Zelle 2-5 Mal hintereinander geladen.

  LoadCell macht pro Aufruf:
    - Header-Lookup (guest::ptr)
    - zwei Multiplikationen und zwei Divisionen
    - cell[1]-Lookup
    - GuestIntMap_Find (Map-Suche)
    - memcpy von 0x3C Bytes

  Der memcpy ist der teuerste Teil und laesst sich ueberspringen, wenn
  dieselbe Zelle bereits in self->current steht.

Sicher: der Cache speichert (x, z, clear40, cellIndex). Bei einem
Treffer mit passendem cellIndex und clear40 wird der memcpy
uebersprungen — self->current enthaelt bereits den richtigen Wert.
Sonst laeuft die Original-Logik.

Idempotent ueber Marker.

Python 3.6+ kompatibel.
"""
import re
import sys
import pathlib


HELPER = r'''
// ── [WOTS2-PORT] Cache fuer LoadCell ─────────────────────────────────────
// wots2-map-collision-cell-cache.py
// Speichert die letzte geladene Zelle (x, z, typeIndex, clear40).
// Bei einem Treffer sparen wir das memcpy der 0x3C-Byte-Zelle.
static u32 wots2_cell_last_x = 0xFFFFFFFFu;
static u32 wots2_cell_last_z = 0xFFFFFFFFu;
static s16 wots2_cell_last_type = -2;
static bool wots2_cell_last_clear = false;
'''

MARKER = "wots2-map-collision-cell-cache.py"


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    if MARKER in t:
        print('  Cell-Cache bereits vorhanden.')
        return

    last_inc = list(re.finditer(r'^#include [<"][^\n]+[>\"]\n', t, re.M))
    if not last_inc:
        print('  FEHLER: kein #include gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t[:last_inc[-1].end()] + HELPER + t[last_inc[-1].end():]

    # In LoadCell: nach dem type-Lookup einfuegen, vor memcpy.
    # Wir ersetzen den memcpy-Block:
    old = '''        GuestMapNode* node = GuestIntMap_Find(&self->types, cell[1]);
        if (node == GuestIntMap_End(&self->types))
            return;
        memcpy(&self->current, guest::ptr(node->value), sizeof(ColCellType));'''
    new = '''        GuestMapNode* node = GuestIntMap_Find(&self->types, cell[1]);
        if (node == GuestIntMap_End(&self->types))
            return;
        // [WOTS2-PORT] Cache-Treffer: derselbe Zelltyp, dieselbe
        // clear40-Behandlung, derselbe (x, z) wie zuletzt — der aktuelle
        // Zellwert in self->current ist bereits korrekt.
        if (x == wots2_cell_last_x && z == wots2_cell_last_z &&
            cell[1] == wots2_cell_last_type && clear40 == wots2_cell_last_clear) {
            return;
        }
        memcpy(&self->current, guest::ptr(node->value), sizeof(ColCellType));
        wots2_cell_last_x = x;
        wots2_cell_last_z = z;
        wots2_cell_last_type = cell[1];
        wots2_cell_last_clear = clear40;'''

    if old not in t:
        print('  WARNUNG: LoadCell-Anker nicht gefunden.')
        p.write_text(t)
        return

    t = t.replace(old, new, 1)

    # Wenn LoadCell in einen anderen Zweig geht (Zelle ausserhalb), Cache
    # invalidieren.
    old_off = '''    } else {                                        // off the grid
        self->current._16 = 0;
        self->current.flags |= kCellBlocked;
    }'''
    new_off = '''    } else {                                        // off the grid
        self->current._16 = 0;
        self->current.flags |= kCellBlocked;
        // [WOTS2-PORT] Cache invalidieren
        wots2_cell_last_x = 0xFFFFFFFFu;
        wots2_cell_last_z = 0xFFFFFFFFu;
    }'''
    if old_off in t:
        t = t.replace(old_off, new_off, 1)
    else:
        print('  HINWEIS: off-the-grid-Zweig nicht gefunden.')

    p.write_text(t)
    print('  Cell-Cache eingebaut.')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/game/map_collision.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
