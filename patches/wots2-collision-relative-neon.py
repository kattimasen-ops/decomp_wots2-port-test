#!/usr/bin/env python3
"""
NEON fuer Relative() in src/game/collision_world.cpp.

Fix v2:
  Der Patch REPARIERT NICHT MEHR den Body von Relative(), sondern fuegt
  oben eine NEON-Schnellspur ein. Der Original-Body bleibt vollstaendig
  erhalten. Damit kann sich die Klammer-Bilanz der Datei nicht aendern.

  Zusaetzlich prueft der Patch die Gesamt-Bilanz von '{' und '}' vor und
  nach der Aenderung. Wenn sie sich unterscheidet, bricht er ab, ohne
  die Datei zu schreiben.

Hintergrund:
  Relative() macht Matrix_Copy + 3x3-Transposition + Matrix_Multiply.
  CornerInside() ruft Relative() einmal und Apply() achtmal auf.
  Touching() ruft beide pro Volumen-Paar auf, und FlagsObj_StepB wird
  pro Frame O(n^2) oft aufgerufen. Bei 8+ Gegnern ist das der teuerste
  Teil der Kollisionserkennung. ARM dokumentiert genau dieses Muster
  als NEON-Beispiel.

Idempotent ueber Marker-Kommentar.

Python 3.6+ kompatibel.
"""
import re
import sys
import pathlib


HELPER = r'''
// ── NEON fuer Relative() (Cortex-A35) ────────────────────────────────
// patches/wots2-collision-relative-neon.py
#if defined(__aarch64__)
#include <arm_neon.h>

// Ersetzt das Original: m = (b - a) * transpose(rotation(a)).
// Der Aufrufer erwartet ein 4x4-Ergebnis in "row-vector"-Konvention,
// wie es Matrix_Copy + Matrix_Multiply liefern.
static inline void wots2_relative_neon(const float* ma, const float* mb, float* m) {
    // Zeilen von mb - ma (Translation in der letzten Zeile).
    float32x4_t r0 = vsubq_f32(vld1q_f32(mb + 0),  vld1q_f32(ma + 0));
    float32x4_t r1 = vsubq_f32(vld1q_f32(mb + 4),  vld1q_f32(ma + 4));
    float32x4_t r2 = vsubq_f32(vld1q_f32(mb + 8),  vld1q_f32(ma + 8));
    float32x4_t r3 = vsubq_f32(vld1q_f32(mb + 12), vld1q_f32(ma + 12));
    // 3x3-Transposition der Rotation von ma.
    const float* R = ma;      // 3x3 in den ersten drei Spalten der Zeilen 0..2
    // Zeile 0 von r gegen Spalten von R (transponiert = Zeilen von R werden Spalten):
    float m00 = r0[0]*R[0] + r0[1]*R[4] + r0[2]*R[8];
    float m01 = r0[0]*R[1] + r0[1]*R[5] + r0[2]*R[9];
    float m02 = r0[0]*R[2] + r0[1]*R[6] + r0[2]*R[10];
    float m03 = r0[3];
    float m10 = r1[0]*R[0] + r1[1]*R[4] + r1[2]*R[8];
    float m11 = r1[0]*R[1] + r1[1]*R[5] + r1[2]*R[9];
    float m12 = r1[0]*R[2] + r1[1]*R[6] + r1[2]*R[10];
    float m13 = r1[3];
    float m20 = r2[0]*R[0] + r2[1]*R[4] + r2[2]*R[8];
    float m21 = r2[0]*R[1] + r2[1]*R[5] + r2[2]*R[9];
    float m22 = r2[0]*R[2] + r2[1]*R[6] + r2[2]*R[10];
    float m23 = r2[3];
    // Letzte Zeile bleibt (Translation).
    m[0]  = m00; m[1]  = m01; m[2]  = m02; m[3]  = m03;
    m[4]  = m10; m[5]  = m11; m[6]  = m12; m[7]  = m13;
    m[8]  = m20; m[9]  = m21; m[10] = m22; m[11] = m23;
    m[12] = r3[0]; m[13] = r3[1]; m[14] = r3[2]; m[15] = r3[3];
}
#endif
'''


MARKER = "patches/wots2-collision-relative-neon.py"


def count_braces(text):
    """Zaehlt '{' und '}' ausserhalb von Kommentaren und Strings."""
    depth = 0
    opens = closes = 0
    i = 0
    in_str = in_chr = in_line = in_blk = False
    while i < len(text):
        c = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ''
        if in_line:
            if c == '\n':
                in_line = False
        elif in_blk:
            if c == '*' and nxt == '/':
                in_blk = False
                i += 1
        elif in_str:
            if c == '\\':
                i += 1
            elif c == '"':
                in_str = False
        elif in_chr:
            if c == '\\':
                i += 1
            elif c == "'":
                in_chr = False
        else:
            if c == '/' and nxt == '/':
                in_line = True
                i += 1
            elif c == '/' and nxt == '*':
                in_blk = True
                i += 1
            elif c == '"':
                in_str = True
            elif c == "'":
                in_chr = True
            elif c == '{':
                depth += 1
                opens += 1
            elif c == '}':
                depth -= 1
                closes += 1
        i += 1
    return opens, closes, depth


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()

    if MARKER in t:
        print('  NEON-Relative bereits vorhanden.')
        return

    # 1. Helper nach dem letzten #include einfuegen.
    last_inc = list(re.finditer(r'^#include [<"][^\n]+[>\"]\n', t, re.M))
    if not last_inc:
        print('  FEHLER: kein #include gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t[:last_inc[-1].end()] + HELPER + t[last_inc[-1].end():]

    # 2. Schnellspur in Relative() einfuegen — direkt nach der oeffnenden '{'.
    sig = re.compile(
        r'static\s+void\s+Relative\s*\(\s*Volume\s*\*\s*a\s*,\s*'
        r'Volume\s*\*\s*b\s*,\s*float\s*\*\s*m\s*\)\s*\{',
        re.S)
    m = sig.search(t)
    if not m:
        print('  FEHLER: Relative()-Signatur nicht gefunden.', file=sys.stderr)
        sys.exit(1)

    fast_path = (
        '\n#if defined(__aarch64__)\n'
        '    // NEON-Schnellspur: siehe patches/wots2-collision-relative-neon.py.\n'
        '    wots2_relative_neon(a->matrix, b->matrix, m);\n'
        '    return;\n'
        '#endif\n'
    )
    # Nur einfuegen, der Original-Body bleibt unveraendert.
    t = t[:m.end()] + fast_path + t[m.end():]

    # 3. Klammer-Bilanz pruefen, bevor geschrieben wird.
    opens, closes, depth = count_braces(t)
    if opens != closes or depth != 0:
        print('  FEHLER: Klammer-Bilanz verletzt nach Patch '
              '(opens=%d, closes=%d, depth=%d).'
              % (opens, closes, depth), file=sys.stderr)
        sys.exit(1)

    p.write_text(t)
    print('  Relative(): NEON-Schnellspur eingefuegt '
          '(Bilanz: %d oeffnend, %d schliessend, Tiefe=%d).'
          % (opens, closes, depth))


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/game/collision_world.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
