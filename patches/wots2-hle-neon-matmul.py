#!/usr/bin/env python3
"""
patches/wots2-hle-neon-matmul.py

Ersetzt mat_mul() in src/native/hle.cpp durch eine NEON-Variante
(4 Zeilen-Linearkombinationen mit vmlaq_n_f32 statt 64 Skalar-Mults).

mat_mul wird von Matrix_Multiply und Matrix_Rotate gerufen, und
Matrix_Multiply ist die heisseste Funktion im Port: Skeleton_UpdateWorld
ruft sie pro Bone pro Charakter pro Frame.

Bitidentisch zum Skalar-Code (gleiche Additions-Reihenfolge pro
Ausgabe-Element), nur mit FMA statt Mult+Add. Kein Spielverhalten
aendert sich.

Idempotent ueber Marker 'wots2-hle-neon-matmul.py'.

Zieldatei: src/native/hle.cpp

Python 3.6+ kompatibel.
"""
import sys
import pathlib

MARKER = "wots2-hle-neon-matmul.py"

OLD = '''static void mat_mul(const float* a, const float* b, float* out) {      // out = a × b, row vectors
    float r[16];
    for (int i = 0; i < 4; i++)
        for (int j = 0; j < 4; j++)
            r[i * 4 + j] = a[i * 4] * b[j] + a[i * 4 + 1] * b[4 + j] + a[i * 4 + 2] * b[8 + j] + a[i * 4 + 3] * b[12 + j];
    memcpy(out, r, sizeof(r));
}
'''

NEW = '''static void mat_mul(const float* a, const float* b, float* out) {      // out = a × b, row vectors
    // wots2-hle-neon-matmul.py
    // out[i][j] = sum_k a[i][k] * b[k][j]  (row-major, row-vector convention)
    // Statt 64 Skalar-Mults + 48 Adds: vier Zeilen-Akkumulatoren mit
    // vmlaq_n_f32, je Zeile vier FMA auf 128 Bit. Bitidentisch zum
    // Skalar-Code, da die Summe in derselben Reihenfolge gebildet wird.
#if defined(__aarch64__)
    float r[16];
    for (int i = 0; i < 4; i++) {
        const float* ar = a + i * 4;
        float32x4_t acc = vmulq_n_f32(vld1q_f32(b + 0), ar[0]);
        acc = vmlaq_n_f32(acc, vld1q_f32(b + 4),  ar[1]);
        acc = vmlaq_n_f32(acc, vld1q_f32(b + 8),  ar[2]);
        acc = vmlaq_n_f32(acc, vld1q_f32(b + 12), ar[3]);
        vst1q_f32(r + i * 4, acc);
    }
    memcpy(out, r, sizeof(r));
#else
    float r[16];
    for (int i = 0; i < 4; i++)
        for (int j = 0; j < 4; j++)
            r[i * 4 + j] = a[i * 4] * b[j] + a[i * 4 + 1] * b[4 + j] + a[i * 4 + 2] * b[8 + j] + a[i * 4 + 3] * b[12 + j];
    memcpy(out, r, sizeof(r));
#endif
}
'''

def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    if MARKER in t:
        print('  HLE-NEON-Matmul bereits vorhanden.')
        return
    if OLD not in t:
        print('  FEHLER: mat_mul()-Block nicht gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t.replace(OLD, NEW, 1)
    p.write_text(t)
    print('  HLE-NEON-Matmul eingebaut (mat_mul, 1 Stelle).')

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/native/hle.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
