#!/usr/bin/env python3
"""
patches/wots2-gs-combat.py

Reduziert die Zahl der Punktlichter, die der 3D-Fragment-Shader pro
Pixel durchrechnet, von 16 auf 8.

Hintergrund:
  In gs.cpp sammelt lighting_begin() die 16 naechsten Lichter der Welt
  (der Map und der Effekte) und setzt sie als Uniform-Arrays. Der
  Fragment-Shader (kFragmentShader3d) iteriert in zwei Schleifen
  ueber uLights:
    - im Map-Pfad (uKind == 2): pro Pixel und Licht eine Distanz-
      Falloff-Berechnung plus Farbmischung.
    - im Effekt-Pfad (uKind == 4/5): Staub und Regentropfen.
  Auf der Mali-G31 mit 512 Threads bei 450 MHz ist es praktisch nie
  sinnvoll, 16 Lichter pro Pixel durchzurechnen — die 8 naechsten
  decken den sichtbaren Bereich ab.

Idempotent: Marker 'wots2-gs-combat.py'.

Zieldatei: src/hal/gs.cpp
Aufruf:    python3 patches/wots2-gs-combat.py src/hal/gs.cpp
"""
import sys
import pathlib


MARKER = "wots2-gs-combat.py"


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()

    if MARKER in t:
        print('  Combat-Patch bereits vorhanden (Marker: %s).' % MARKER)
        return

    old_arrays = 'float pos[16][4], col[16][3];'
    new_arrays = 'float pos[8][4], col[8][3];  // ' + MARKER
    if old_arrays not in t:
        print('  FEHLER: pos[16][4]-Deklaration nicht gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t.replace(old_arrays, new_arrays, 1)

    old_loop = 'for (; n < 16 && n < (int)nearest.size(); n++) {'
    new_loop = 'for (; n < 8 && n < (int)nearest.size(); n++) {'
    if old_loop not in t:
        print('  FEHLER: Sammelschleife mit n<16 nicht gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t.replace(old_loop, new_loop, 1)

    p.write_text(t)
    print('  Combat-Patch angewendet: pos/col-Arrays [16]->[8], Sammelschleife n<16->n<8.')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
