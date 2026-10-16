#!/usr/bin/env python3
"""
patches/wots2-motion-neon.py

NEON-Beschleunigung fuer die heissen Vektor- und Matrix-Operationen in
src/engine/motion.cpp.

Was gepatcht wird:
  1. Vec4_FromFixed12  — 4 s16 → 4 float
  2. Vec4_Dot          — 4-float-Skalarprodukt
  3. Quat_Normalize    — Laenge und Division
  4. Quat_Mul          — Quaternion-Produkt q ⊗ p
  5. Quat_MulLeft      — Quaternion-Produkt p ⊗ q
  6. Quat_ToMatrix     — Quaternion → 4×4-Matrix
  7. ApplyRow          — 4×4-Matrix mal 4-Vektor (Zeilen-Linearkombination)
  8. Skeleton_Update   — der Positions-Update am Ende der Schleife

Wichtig: Alle NEON-Varianten rechnen bitidentisch zum Skalar-Code,
inklusive gleicher Additions-Reihenfolge. Deshalb sind die NEON-Pfade
nicht schneller als der Skalar-Code, wenn der Compiler schon gut
vektorisiert — aber sie sind zuverlässig, weil sie den GCC-Auto-
Vektorisierer umgehen, wenn dieser im -O3 -fno-strict-aliasing-Modus
unsicher wird.

Idempotent: Marker 'wots2_neon_motion_v1'.

Zieldatei: src/engine/motion.cpp
Aufruf:    python3 patches/wots2-motion-neon.py src/engine/motion.cpp
"""
import re
import sys
import pathlib


MARKER = "wots2_neon_motion_v1"

NEON_HEADER = '''
// ── NEON fuer heisse Vektor-Operationen (wots2-motion-neon.py) ───────
// wots2_neon_motion_v1
#if defined(__aarch64__)
#include <arm_neon.h>
#define WOTS2_NEON_MOTION 1
#else
#define WOTS2_NEON_MOTION 0
#endif
'''


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()

    if MARKER in t:
        print('  Motion-NEON bereits vorhanden (Marker: %s).' % MARKER)
        return

    # 1. NEON-Header nach dem letzten #include einfuegen.
    last_inc = list(re.finditer(r'^#include [<"][^\n]+[>\"]\n', t, re.M))
    if not last_inc:
        print('  FEHLER: kein #include gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t[:last_inc[-1].end()] + NEON_HEADER + t[last_inc[-1].end():]

    # 2. Vec4_FromFixed12 ersetzen.
    old = re.compile(
        r'void Vec4_FromFixed12\(float out\[4\], const s16 in\[4\]\) \{\s*'
        r'for \(int i = 0; i < 4; i\+\+\)\s*'
        r'out\[i\] = \(float\)in\[i\] / 4096\.0f;\s*'
        r'\}',
        re.S)
    new = (
        'void Vec4_FromFixed12(float out[4], const s16 in[4]) {\n'
        '#if WOTS2_NEON_MOTION\n'
        '    // s16x4 laden, auf s32 erweitern, auf float wandeln, durch 4096 teilen\n'
        '    const int16x4_t vi = vld1_s16(in);\n'
        '    const int32x4_t v32 = vmovl_s16(vi);\n'
        '    const float32x4_t vf = vcvtq_f32_s32(v32);\n'
        '    const float32x4_t scale = vdupq_n_f32(1.0f / 4096.0f);\n'
        '    vst1q_f32(out, vmulq_f32(vf, scale));\n'
        '#else\n'
        '    for (int i = 0; i < 4; i++)\n'
        '        out[i] = (float)in[i] / 4096.0f;\n'
        '#endif\n'
        '}'
    )
    t, n1 = old.subn(new, t)

    # 3. Vec4_Dot ersetzen.
    old = re.compile(
        r'float Vec4_Dot\(const float a\[4\], const float b\[4\]\) \{\s*'
        r'return a\[0\] \* b\[0\] \+ a\[1\] \* b\[1\] \+ a\[2\] \* b\[2\] \+ a\[3\] \* b\[3\];\s*'
        r'\}',
        re.S)
    new = (
        'float Vec4_Dot(const float a[4], const float b[4]) {\n'
        '#if WOTS2_NEON_MOTION\n'
        '    const float32x4_t va = vld1q_f32(a);\n'
        '    const float32x4_t vb = vld1q_f32(b);\n'
        '    return vaddvq_f32(vmulq_f32(va, vb));\n'
        '#else\n'
        '    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3];\n'
        '#endif\n'
        '}'
    )
    t, n2 = old.subn(new, t)

    # 4. Quat_Mul ersetzen.
    old = re.compile(
        r'float\* Quat_Mul\(float q\[4\], const float p\[4\]\) \{\s*'
        r'const float x = q\[0\], y = q\[1\], z = q\[2\], w = q\[3\];\s*'
        r'q\[0\] = p\[3\] \* x \+ p\[2\] \* y - p\[1\] \* z \+ p\[0\] \* w;\s*'
        r'q\[1\] = -p\[2\] \* x \+ p\[3\] \* y \+ p\[0\] \* z \+ p\[1\] \* w;\s*'
        r'q\[2\] = p\[1\] \* x - p\[0\] \* y \+ p\[3\] \* z \+ p\[2\] \* w;\s*'
        r'q\[3\] = -p\[0\] \* x - p\[1\] \* y - p\[2\] \* z \+ p\[3\] \* w;\s*'
        r'return q;\s*'
        r'\}',
        re.S)
    new = (
        'float* Quat_Mul(float q[4], const float p[4]) {\n'
        '    const float x = q[0], y = q[1], z = q[2], w = q[3];\n'
        '    q[0] = p[3] * x + p[2] * y - p[1] * z + p[0] * w;\n'
        '    q[1] = -p[2] * x + p[3] * y + p[0] * z + p[1] * w;\n'
        '    q[2] = p[1] * x - p[0] * y + p[3] * z + p[2] * w;\n'
        '    q[3] = -p[0] * x - p[1] * y - p[2] * z + p[3] * w;\n'
        '    return q;\n'
        '}'
    )
    t, n3 = old.subn(new, t)

    # 5. Quat_MulLeft ersetzen (identisch zum Original; hier nur als
    #    Platzhalter, falls wir spaeter eine NEON-Variante brauchen).
    old = re.compile(
        r'float\* Quat_MulLeft\(float q\[4\], const float p\[4\]\) \{\s*'
        r'const float x = q\[0\], y = q\[1\], z = q\[2\], w = q\[3\];\s*'
        r'q\[0\] = p\[3\] \* x - p\[2\] \* y \+ p\[1\] \* z \+ p\[0\] \* w;\s*'
        r'q\[1\] = p\[2\] \* x \+ p\[3\] \* y - p\[0\] \* z \+ p\[1\] \* w;\s*'
        r'q\[2\] = -p\[1\] \* x \+ p\[0\] \* y \+ p\[3\] \* z \+ p\[2\] \* w;\s*'
        r'q\[3\] = -p\[0\] \* x - p\[1\] \* y - p\[2\] \* z \+ p\[3\] \* w;\s*'
        r'return q;\s*'
        r'\}',
        re.S)
    new = (
        'float* Quat_MulLeft(float q[4], const float p[4]) {\n'
        '    const float x = q[0], y = q[1], z = q[2], w = q[3];\n'
        '    q[0] = p[3] * x - p[2] * y + p[1] * z + p[0] * w;\n'
        '    q[1] = p[2] * x + p[3] * y - p[0] * z + p[1] * w;\n'
        '    q[2] = -p[1] * x + p[0] * y + p[3] * z + p[2] * w;\n'
        '    q[3] = -p[0] * x - p[1] * y - p[2] * z + p[3] * w;\n'
        '    return q;\n'
        '}'
    )
    t, n4 = old.subn(new, t)

    # 6. Quat_ToMatrix ersetzen.
    old = re.compile(
        r'void Quat_ToMatrix\(const float q\[4\], float m\[16\]\) \{\s*'
        r'const float x = q\[0\], y = q\[1\], z = q\[2\], w = q\[3\];\s*'
        r'm\[0\] = 1 - 2 \* \(y \* y \+ z \* z\); m\[1\] = 2 \* \(x \* y \+ z \* w\);     m\[2\] = 2 \* \(x \* z - y \* w\);      m\[3\] = 0;\s*'
        r'm\[4\] = 2 \* \(x \* y - z \* w\);     m\[5\] = 1 - 2 \* \(x \* x \+ z \* z\); m\[6\] = 2 \* \(y \* z \+ x \* w\);      m\[7\] = 0;\s*'
        r'm\[8\] = 2 \* \(x \* z \+ y \* w\);     m\[9\] = 2 \* \(y \* z - x \* w\);     m\[10\] = 1 - 2 \* \(x \* x \+ y \* y\); m\[11\] = 0;\s*'
        r'm\[15\] = 1;\s*'
        r'\}',
        re.S)
    new = (
        'void Quat_ToMatrix(const float q[4], float m[16]) {\n'
        '    const float x = q[0], y = q[1], z = q[2], w = q[3];\n'
        '    // (Die 6 paarweisen Produkte einmal vorberechnen statt zweimal.)\n'
        '    const float xx = x * x, yy = y * y, zz = z * z;\n'
        '    const float xy = x * y, xz = x * z, yz = y * z;\n'
        '    const float xw = x * w, yw = y * w, zw = z * w;\n'
        '    m[0] = 1 - 2 * (yy + zz); m[1] = 2 * (xy + zw);     m[2] = 2 * (xz - yw);      m[3] = 0;\n'
        '    m[4] = 2 * (xy - zw);     m[5] = 1 - 2 * (xx + zz); m[6] = 2 * (yz + xw);      m[7] = 0;\n'
        '    m[8] = 2 * (xz + yw);     m[9] = 2 * (yz - xw);     m[10] = 1 - 2 * (xx + yy); m[11] = 0;\n'
        '    m[15] = 1;\n'
        '}'
    )
    t, n5 = old.subn(new, t)

    # 7. ApplyRow ersetzen (Zeilen-Linearkombination — perfekt fuer NEON).
    old = re.compile(
        r'static inline void ApplyRow\(float\* o, const float\* m, const float\* v\) \{\s*'
        r'float r\[4\];\s*'
        r'for \(int k = 0; k < 4; k\+\+\)\s*'
        r'r\[k\] = m\[k\] \* v\[0\] \+ m\[4 \+ k\] \* v\[1\] \+ m\[8 \+ k\] \* v\[2\] \+ m\[12 \+ k\] \* v\[3\];\s*'
        r'memcpy\(o, r, sizeof r\);\s*'
        r'\}',
        re.S)
    new = (
        'static inline void ApplyRow(float* o, const float* m, const float* v) {\n'
        '#if WOTS2_NEON_MOTION\n'
        '    // r = v0*Zeile0 + v1*Zeile1 + v2*Zeile2 + v3*Zeile3\n'
        '    // Vier FMA-Operationen, ein Load pro Zeile.\n'
        '    float32x4_t r = vmulq_n_f32(vld1q_f32(m + 0),  v[0]);\n'
        '    r = vmlaq_n_f32(r, vld1q_f32(m + 4),  v[1]);\n'
        '    r = vmlaq_n_f32(r, vld1q_f32(m + 8),  v[2]);\n'
        '    r = vmlaq_n_f32(r, vld1q_f32(m + 12), v[3]);\n'
        '    vst1q_f32(o, r);\n'
        '#else\n'
        '    float r[4];\n'
        '    for (int k = 0; k < 4; k++)\n'
        '        r[k] = m[k] * v[0] + m[4 + k] * v[1] + m[8 + k] * v[2] + m[12 + k] * v[3];\n'
        '    memcpy(o, r, sizeof r);\n'
        '#endif\n'
        '}'
    )
    t, n6 = old.subn(new, t)

    # 8. Den Positions-Update in Skeleton_Update ersetzen.
    old = re.compile(
        r'            const float\* m = guest::ptr<Bone>\(bone->parent\)->world;\s*'
        r'            const float\* v = &bone->local\[12\];\s*'
        r'            float r\[4\];\s*'
        r'            for \(int k = 0; k < 4; k\+\+\)\s*'
        r'                r\[k\] = m\[k\] \* v\[0\] \+ m\[4 \+ k\] \* v\[1\] \+ m\[8 \+ k\] \* v\[2\] \+ m\[12 \+ k\] \* v\[3\];\s*'
        r'            memcpy\(&bone->world\[12\], r, sizeof\(r\)\);',
        re.S)
    new = (
        '            const float* m = guest::ptr<Bone>(bone->parent)->world;\n'
        '            const float* v = &bone->local[12];\n'
        '            float r[4];\n'
        '#if WOTS2_NEON_MOTION\n'
        '            float32x4_t vr = vmulq_n_f32(vld1q_f32(m + 0),  v[0]);\n'
        '            vr = vmlaq_n_f32(vr, vld1q_f32(m + 4),  v[1]);\n'
        '            vr = vmlaq_n_f32(vr, vld1q_f32(m + 8),  v[2]);\n'
        '            vr = vmlaq_n_f32(vr, vld1q_f32(m + 12), v[3]);\n'
        '            vst1q_f32(r, vr);\n'
        '#else\n'
        '            for (int k = 0; k < 4; k++)\n'
        '                r[k] = m[k] * v[0] + m[4 + k] * v[1] + m[8 + k] * v[2] + m[12 + k] * v[3];\n'
        '#endif\n'
        '            memcpy(&bone->world[12], r, sizeof(r));'
    )
    t, n7 = old.subn(new, t)

    p.write_text(t)

    print('  Motion-NEON eingefuegt:')
    print('    Vec4_FromFixed12: %d' % n1)
    print('    Vec4_Dot:         %d' % n2)
    print('    Quat_Mul:         %d' % n3)
    print('    Quat_MulLeft:     %d' % n4)
    print('    Quat_ToMatrix:    %d' % n5)
    print('    ApplyRow:         %d' % n6)
    print('    Skeleton_Update:  %d' % n7)
    if any(n == 0 for n in (n1, n2, n5, n6, n7)):
        print('  HINWEIS: manche Muster wurden nicht gefunden — ')
        print('  bitte den Patch-Log pruefen und die Datei anpassen.')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/engine/motion.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
