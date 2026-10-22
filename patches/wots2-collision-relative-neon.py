#!/usr/bin/env python3
"""
patches/wots2-collision-relative-neon.py   (v3 — 2026-10-22)

NEON fuer Relative() in src/game/collision_world.cpp.

Bug (v1/v2): Der eingefuegte Helper wots2_relative_neon() rechnete falsch:
  1. r0/r1/r2 = mb_row_i - ma_row_i. Das Original subtrahiert aber NUR
     die letzte Zeile (m[12..15] -= ma[12..15]); die oberen drei Zeilen
     bleiben = mb_row_i.
  2. Die Berechnung war r_i . R-Spalte_j (also r_i * R^T). Das ist an
     sich richtig fuer R^T — aber da r_i schon falsch war, kam Unsinn
     raus. Zusaetzlich wurde die letzte Zeile (Translation) NICHT mit
     R^T multipliziert, sondern unveraendert kopiert.

Original rechnet (Matrix_Multiply(m, inverse, m), d.h. m = m * inverse
mit inverse = [[R^T, 0], [0,1]]):
   C[i][j] = mb_row_i . ma_row_j           (i,j < 3)
   C[i][3] = mb_row_i[3]                    (i < 3)
   C[3][j] = (mb_last - ma_last) . ma_row_j (j < 3)
   C[3][3] = (mb_last - ma_last)[3]

v3 korrigiert den Helper. Der Patch erkennt den kaputten Zustand (in
deiner aktuellen collision_world.cpp) und migriert ihn — ohne die
Quelle anfassen zu muessen. Der Rest (Schnellspur in Relative(), Klammer-
Bilanzpruefung) bleibt wie im Original-Patch.

Idempotent: prueft auf 'b0[0]*R[0] + b0[1]*R[1] + b0[2]*R[2]' im Helper
(Korrekturmarker).

Voraussetzung: patches/wots2-collision-neon.py ist vorher gelaufen
(fuegt wots2_apply_neon() und #include <arm_neon.h> ein).

Zieldatei: src/game/collision_world.cpp
"""
import re
import sys
import pathlib


HELPER_FIXED = r'''
// ── NEON fuer Relative() (Cortex-A35) ────────────────────────────────
// patches/wots2-collision-relative-neon.py
#if defined(__aarch64__)
#include <arm_neon.h>

// (v3) Ersetzt das Original:
//   C = M * inverse(rotation(ma))
//   wobei M = mb mit letzter Zeile = mb_last - ma_last
//   inverse = [[R^T, 0], [0, 1]]
//
// Also:
//   C[i][j] = mb_row_i . ma_row_j           (i,j < 3)
//   C[i][3] = mb_row_i[3]                    (i < 3)
//   C[3][j] = (mb_last - ma_last) . ma_row_j (j < 3)
//   C[3][3] = (mb_last - ma_last)[3]
//
// row-major: ma[0..2]=Zeile 0, ma[4..6]=Zeile 1, ma[8..10]=Zeile 2.
static inline void wots2_relative_neon(const float* ma, const float* mb, float* m) {
    const float32x4_t b0 = vld1q_f32(mb + 0);
    const float32x4_t b1 = vld1q_f32(mb + 4);
    const float32x4_t b2 = vld1q_f32(mb + 8);
    const float32x4_t b3 = vld1q_f32(mb + 12);
    const float32x4_t r3 = vsubq_f32(b3, vld1q_f32(ma + 12));
    const float* R = ma;
    const float m00 = b0[0]*R[0] + b0[1]*R[1] + b0[2]*R[2];
    const float m01 = b0[0]*R[4] + b0[1]*R[5] + b0[2]*R[6];
    const float m02 = b0[0]*R[8] + b0[1]*R[9] + b0[2]*R[10];
    const float m03 = b0[3];
    const float m10 = b1[0]*R[0] + b1[1]*R[1] + b1[2]*R[2];
    const float m11 = b1[0]*R[4] + b1[1]*R[5] + b1[2]*R[6];
    const float m12 = b1[0]*R[8] + b1[1]*R[9] + b1[2]*R[10];
    const float m13 = b1[3];
    const float m20 = b2[0]*R[0] + b2[1]*R[1] + b2[2]*R[2];
    const float m21 = b2[0]*R[4] + b2[1]*R[5] + b2[2]*R[6];
    const float m22 = b2[0]*R[8] + b2[1]*R[9] + b2[2]*R[10];
    const float m23 = b2[3];
    const float m30 = r3[0]*R[0] + r3[1]*R[1] + r3[2]*R[2];
    const float m31 = r3[0]*R[4] + r3[1]*R[5] + r3[2]*R[6];
    const float m32 = r3[0]*R[8] + r3[1]*R[9] + r3[2]*R[10];
    const float m33 = r3[3];
    m[0]  = m00; m[1]  = m01; m[2]  = m02; m[3]  = m03;
    m[4]  = m10; m[5]  = m11; m[6]  = m12; m[7]  = m13;
    m[8]  = m20; m[9]  = m21; m[10] = m22; m[11] = m23;
    m[12] = m30; m[13] = m31; m[14] = m32; m[15] = m33;
}
#endif
'''

# Exakter kaputter Helper aus deiner aktuellen collision_world.cpp
HELPER_BROKEN = r'''
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

# Marker im Original-Patch (Steuerung der Schnellspur-Einfuegung)
MARKER = "patches/wots2-collision-relative-neon.py"
FAST_PATH_MARK = "NEON-Schnellspur: siehe patches/wots2-collision-relative-neon.py"


def count_braces(text):
    depth = 0; opens = closes = 0
    i = 0; in_str = in_chr = in_line = in_blk = False
    while i < len(text):
        c = text[i]; nxt = text[i + 1] if i + 1 < len(text) else ''
        if in_line:
            if c == '\n': in_line = False
        elif in_blk:
            if c == '*' and nxt == '/': in_blk = False; i += 1
        elif in_str:
            if c == '\\': i += 1
            elif c == '"': in_str = False
        elif in_chr:
            if c == '\\': i += 1
            elif c == "'": in_chr = False
        else:
            if c == '/' and nxt == '/': in_line = True; i += 1
            elif c == '/' and nxt == '*': in_blk = True; i += 1
            elif c == '"': in_str = True
            elif c == "'": in_chr = True
            elif c == '{': depth += 1; opens += 1
            elif c == '}': depth -= 1; closes += 1
        i += 1
    return opens, closes, depth


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()

    # 1. Korrekte Version schon da?
    if "b0[0]*R[0] + b0[1]*R[1] + b0[2]*R[2]" in t:
        print('  NEON-Relative bereits korrekt (v3-Marker) — skip')
        return

    # 2. Kaputte Version da? (aus altem Patch)
    if HELPER_BROKEN in t:
        print('  kaputten Helper gefunden — ersetze durch korrigierte Version')
        t = t.replace(HELPER_BROKEN, HELPER_FIXED, 1)
        # Schnellspur sollte in Relative() schon drin sein; pruefen
        if FAST_PATH_MARK not in t:
            print('  WARNUNG: Schnellspur fehlt trotz Helper — wird nachgezogen')
            sig = re.compile(
                r'static\s+void\s+Relative\s*\(\s*Volume\s*\*\s*a\s*,\s*'
                r'Volume\s*\*\s*b\s*,\s*float\s*\*\s*m\s*\)\s*\{', re.S)
            m = sig.search(t)
            if m:
                fast_path = ('\n#if defined(__aarch64__)\n'
                             '    // NEON-Schnellspur: siehe patches/wots2-collision-relative-neon.py.\n'
                             '    wots2_relative_neon(a->matrix, b->matrix, m);\n'
                             '    return;\n'
                             '#endif\n')
                t = t[:m.end()] + fast_path + t[m.end():]
        p.write_text(t)
        print('  collision_world.cpp migriert')
        return

    # 3. Original-Fall: Helper einfuegen + Schnellspur in Relative()
    last_inc = list(re.finditer(r'^#include [<"][^\n]+[>\"]\n', t, re.M))
    if not last_inc:
        print('  FEHLER: kein #include gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t[:last_inc[-1].end()] + HELPER_FIXED + t[last_inc[-1].end():]

    sig = re.compile(
        r'static\s+void\s+Relative\s*\(\s*Volume\s*\*\s*a\s*,\s*'
        r'Volume\s*\*\s*b\s*,\s*float\s*\*\s*m\s*\)\s*\{', re.S)
    m = sig.search(t)
    if not m:
        print('  FEHLER: Relative()-Signatur nicht gefunden.', file=sys.stderr)
        sys.exit(1)
    fast_path = ('\n#if defined(__aarch64__)\n'
                 '    // NEON-Schnellspur: siehe patches/wots2-collision-relative-neon.py.\n'
                 '    wots2_relative_neon(a->matrix, b->matrix, m);\n'
                 '    return;\n'
                 '#endif\n')
    t = t[:m.end()] + fast_path + t[m.end():]

    opens, closes, depth = count_braces(t)
    if opens != closes or depth != 0:
        print('  FEHLER: Klammer-Bilanz verletzt (opens=%d, closes=%d, depth=%d)'
              % (opens, closes, depth), file=sys.stderr)
        sys.exit(1)

    p.write_text(t)
    print('  Relative(): NEON-Schnellspur eingefuegt (Bilanz OK)')
    print('  Helper korrekt eingebaut')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/game/collision_world.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
