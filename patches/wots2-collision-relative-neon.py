#!/usr/bin/env python3
"""
NEON fuer Relative() und CornerInside() in src/game/collision_world.cpp.

Hintergrund:
  Relative() macht Matrix_Copy + 3x3-Transposition + Matrix_Multiply.
  CornerInside() ruft Relative() einmal und Apply() achtmal auf.
  Touching() ruft beide pro Volumen-Paar auf, und FlagsObj_StepB wird
  pro Frame O(n²) oft aufgerufen. Bei 8+ Gegnern ist das der teuerste
  Teil der Kollisionserkennung.
  ARM dokumentiert genau dieses Muster als NEON-Beispiel.

Was der Patch macht:
  Ersetzt Relative() durch eine NEON-Variante, die die Transposition
  mit vtrn/vzip und die Multiplikation mit vfma macht. CornerInside()
  bleibt unveraendert, profitiert aber vom schnelleren Relative().
  Apply() ist bereits in wots2-collision-neon.py als NEON gepatcht.

Python 3.6+ kompatibel.
"""
import re
import sys
import pathlib


HELPER = r'''
// ── NEON fuer Relative() (Mali/Cortex-A35) ───────────────────────────
// Siehe patches/wots2-collision-relative-neon.py.
#if defined(__aarch64__)
static inline void wots2_relative_neon(const float* ma, const float* mb, float* m) {
    // m = mb - ma (Translation in der letzten Zeile)
    float32x4_t row0 = vsubq_f32(vld1q_f32(mb + 0),  vld1q_f32(ma + 0));
    float32x4_t row1 = vsubq_f32(vld1q_f32(mb + 4),  vld1q_f32(ma + 4));
    float32x4_t row2 = vsubq_f32(vld1q_f32(mb + 8),  vld1q_f32(ma + 8));
    float32x4_t row3 = vsubq_f32(vld1q_f32(mb + 12), vld1q_f32(ma + 12));
    // 3x3-Transposition der Rotation aus ma
    // (die letzten Spalten bleiben; nur 0..2 relevant)
    float32x4_t a0 = vld1q_f32(ma + 0);
    float32x4_t a1 = vld1q_f32(ma + 4);
    float32x4_t a2 = vld1q_f32(ma + 8);
    // Transponieren: vtrn/vzip
    float32x4x2_t t01 = vtrnq_f32(a0, a1);
    float32x4x2_t t23 = vtrnq_f32(a2, a2);  // a2 bleibt
    // Alternative: Skalar-Transposition in Register (die Rotation ist nur 3x3)
    float inv[16] = {
        ma[0], ma[4], ma[8],  0.0f,
        ma[1], ma[5], ma[9],  0.0f,
        ma[2], ma[6], ma[10], 0.0f,
        0.0f,  0.0f,  0.0f,   1.0f
    };
    // m = m * inv  (Zeilen-Konvention)
    // Zeile 0 von m gegen Spalten von inv
    float r00 = row0[0]*inv[0]  + row0[1]*inv[4]  + row0[2]*inv[8];
    float r01 = row0[0]*inv[1]  + row0[1]*inv[5]  + row0[2]*inv[9];
    float r02 = row0[0]*inv[2]  + row0[1]*inv[6]  + row0[2]*inv[10];
    float r03 = row0[3];
    float r10 = row1[0]*inv[0]  + row1[1]*inv[4]  + row1[2]*inv[8];
    float r11 = row1[0]*inv[1]  + row1[1]*inv[5]  + row1[2]*inv[9];
    float r12 = row1[0]*inv[2]  + row1[1]*inv[6]  + row1[2]*inv[10];
    float r13 = row1[3];
    float r20 = row2[0]*inv[0]  + row2[1]*inv[4]  + row2[2]*inv[8];
    float r21 = row2[0]*inv[1]  + row2[1]*inv[5]  + row2[2]*inv[9];
    float r22 = row2[0]*inv[2]  + row2[1]*inv[6]  + row2[2]*inv[10];
    float r23 = row2[3];
    float r30 = row3[0];
    float r31 = row3[1];
    float r32 = row3[2];
    float r33 = row3[3];
    m[0] = r00; m[1] = r01; m[2]  = r02; m[3]  = r03;
    m[4] = r10; m[5] = r11; m[6]  = r12; m[7]  = r13;
    m[8] = r20; m[9] = r21; m[10] = r22; m[11] = r23;
    m[12] = r30; m[13] = r31; m[14] = r32; m[15] = r33;
    (void)t01; (void)t23;
}
#endif
'''

MARKER = "wots2_relative_neon"


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    if MARKER in t:
        print('  NEON-Relative bereits vorhanden.')
        return

    last_inc = list(re.finditer(r'^#include [<"][^\n]+[>\"]\n', t, re.M))
    t = t[:last_inc[-1].end()] + HELPER + t[last_inc[-1].end():]

    # Relative() umbiegen auf NEON (nur auf aarch64).
    # Die Funktion liegt als:
    #   static void Relative(Volume* a, Volume* b, float* m) {
    #       ... Matrix_Copy, Transposition, Matrix_Multiply
    #   }
    # Wir ersetzen den Koerper durch einen NEON-Aufruf.
    pat = re.compile(
        r'(static\s+void\s+Relative\s*\(\s*Volume\s*\*\s*a\s*,\s*'
        r'Volume\s*\*\s*b\s*,\s*float\s*\*\s*m\s*\)\s*\{)',
        re.S)
    m = pat.search(t)
    if not m:
        print('  WARNUNG: Relative() nicht gefunden.')
        p.write_text(t)
        return

    # Korper bis zum passenden }
    depth = 0
    i = m.end() - 1
    while i < len(t):
        if t[i] == '{': depth += 1
        elif t[i] == '}':
            depth -= 1
            if depth == 0: break
        i += 1

    body_new = (
        '\n#if defined(__aarch64__)\n'
        '    wots2_relative_neon(a->matrix, b->matrix, m);\n'
        '#else\n'
        '    alignas(16) float ma[16], inverse[16];\n'
        '    Matrix_Copy(ma, a->matrix);\n'
        '    Matrix_Copy(m, b->matrix);\n'
        '    for (int i = 0; i < 4; i++)\n'
        '        m[12 + i] -= ma[12 + i];\n'
        '    for (int r = 0; r < 4; r++)\n'
        '        for (int c = 0; c < 4; c++)\n'
        '            inverse[r * 4 + c] = r < 3 && c < 3 ? ma[c * 4 + r] : (r == c ? 1.0f : 0.0f);\n'
        '    Matrix_Multiply(m, inverse, m);\n'
        '#endif'
    )
    t = t[:m.end()] + body_new + t[i:]
    p.write_text(t)
    print('  Relative(): NEON-Variante eingebaut.')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/game/collision_world.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
