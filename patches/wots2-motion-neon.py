#!/usr/bin/env python3
"""
patches/wots2-motion-neon.py   (v2)

NEON-Beschleunigung fuer die heissen Vektor- und Matrix-Operationen in
src/engine/motion.cpp.

Was gepatcht wird:
  1. Vec4_FromFixed12  - 4 x s16 -> 4 x float (exakt: Teilung durch 2^12)
  2. Vec4_Dot          - 4-float-Skalarprodukt (Summationsreihenfolge
                         bleibt wie im Skalar-Code)
  3. Quat_ToMatrix     - die 9 paarweisen Produkte nur noch einmal rechnen
  4. ApplyRow          - 4x4-Matrix mal 4-Vektor als Zeilen-Linearkombination
  5. Skeleton_Update   - der Positions-Update (0x1395F0), nutzt denselben
                         NEON-Helfer wie ApplyRow

Aenderungen gegenueber v1:
  * Quat_ToMatrix wurde in v1 nie gefunden: Das Muster erwartete direkt
    nach 'm[15] = 1;' die schliessende Klammer, im Quelltext steht dort
    aber ein Kommentar. Jetzt wird die Funktion ueber ihre Signatur und
    Klammer-Zaehlung gefunden, unabhaengig von Kommentaren/Leerzeichen.
  * Quat_Mul und Quat_MulLeft wurden in v1 durch ihren eigenen, unveraen-
    derten Text ersetzt (reine Platzhalter) und sind entfallen. Quat_Normalize
    steht nur im alten Docstring, war nie implementiert.
  * Vec4_Dot nutzt kein vaddvq_f32 mehr (das summiert paarweise und aendert
    die Rundung), sondern addiert die Lanes in der Reihenfolge des Skalar-
    Codes.
  * Jeder Fehlschlag wird als 'PATCH-FEHLER:' gemeldet. Mit
    WOTS2_PATCH_STRICT=1 bricht das Skript dann mit Exit-Code 2 ab.

Idempotent: Marker 'wots2_neon_motion_v2'.

Zieldatei: src/engine/motion.cpp
Aufruf:    python3 patches/wots2-motion-neon.py src/engine/motion.cpp
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wots2_patchlib as pl  # noqa: E402

MARKER = "wots2_neon_motion_v2"

NEON_HEADER = '''
// -- NEON fuer heisse Vektor-Operationen (wots2-motion-neon.py) ---------
// wots2_neon_motion_v2
#if defined(__aarch64__)
#include <arm_neon.h>
#define WOTS2_NEON_MOTION 1
#else
#define WOTS2_NEON_MOTION 0
#endif

// o = v0*Zeile0 + v1*Zeile1 + v2*Zeile2 + v3*Zeile3   (m: 4x4, Zeilenweise)
// Gleiche Additionsreihenfolge wie der Skalar-Code. Alle Eingaben werden
// gelesen, bevor o geschrieben wird (o darf also auf v oder m zeigen).
static inline void wots2_row_combine(float* o, const float* m, const float* v) {
#if WOTS2_NEON_MOTION
    float32x4_t r = vmulq_n_f32(vld1q_f32(m + 0), v[0]);
    r = vmlaq_n_f32(r, vld1q_f32(m + 4),  v[1]);
    r = vmlaq_n_f32(r, vld1q_f32(m + 8),  v[2]);
    r = vmlaq_n_f32(r, vld1q_f32(m + 12), v[3]);
    vst1q_f32(o, r);
#else
    float r[4];
    for (int k = 0; k < 4; k++)
        r[k] = m[k] * v[0] + m[4 + k] * v[1] + m[8 + k] * v[2] + m[12 + k] * v[3];
    memcpy(o, r, sizeof r);
#endif
}
'''

NEW_VEC4_FROMFIXED12 = '''void Vec4_FromFixed12(float out[4], const s16 in[4]) {
#if WOTS2_NEON_MOTION
    // s16x4 laden, auf s32 erweitern, in float wandeln, mit 2^-12 multiplizieren
    // (exakt, weil 4096 eine Zweierpotenz ist).
    const int32x4_t v32 = vmovl_s16(vld1_s16(in));
    vst1q_f32(out, vmulq_f32(vcvtq_f32_s32(v32), vdupq_n_f32(1.0f / 4096.0f)));
#else
    for (int i = 0; i < 4; i++)
        out[i] = (float)in[i] / 4096.0f;
#endif
}'''

NEW_VEC4_DOT = '''float Vec4_Dot(const float a[4], const float b[4]) {
#if WOTS2_NEON_MOTION
    // Vier Produkte parallel, dann in der Reihenfolge des Skalar-Codes
    // addieren: ((p0 + p1) + p2) + p3.
    const float32x4_t p = vmulq_f32(vld1q_f32(a), vld1q_f32(b));
    return ((vgetq_lane_f32(p, 0) + vgetq_lane_f32(p, 1)) + vgetq_lane_f32(p, 2)) + vgetq_lane_f32(p, 3);
#else
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3];
#endif
}'''

NEW_QUAT_TOMATRIX = '''void Quat_ToMatrix(const float q[4], float m[16]) {
    const float x = q[0], y = q[1], z = q[2], w = q[3];
    // Die paarweisen Produkte einmal berechnen statt zweimal.
    const float xx = x * x, yy = y * y, zz = z * z;
    const float xy = x * y, xz = x * z, yz = y * z;
    const float xw = x * w, yw = y * w, zw = z * w;
    m[0] = 1 - 2 * (yy + zz); m[1] = 2 * (xy + zw);     m[2] = 2 * (xz - yw);      m[3] = 0;
    m[4] = 2 * (xy - zw);     m[5] = 1 - 2 * (xx + zz); m[6] = 2 * (yz + xw);      m[7] = 0;
    m[8] = 2 * (xz + yw);     m[9] = 2 * (yz - xw);     m[10] = 1 - 2 * (xx + yy); m[11] = 0;
    m[15] = 1;      // the translation (m[12..14]) is left as it was
}'''

NEW_APPLYROW = '''static inline void ApplyRow(float* o, const float* m, const float* v) {
    wots2_row_combine(o, m, v);
}'''

OLD_SKELETON_BLOCK = '''const float* m = guest::ptr<Bone>(bone->parent)->world;
            const float* v = &bone->local[12];
            float r[4];
            for (int k = 0; k < 4; k++)
                r[k] = m[k] * v[0] + m[4 + k] * v[1] + m[8 + k] * v[2] + m[12 + k] * v[3];
            memcpy(&bone->world[12], r, sizeof(r));'''

NEW_SKELETON_BLOCK = '''const float* m = guest::ptr<Bone>(bone->parent)->world;
            const float* v = &bone->local[12];
            wots2_row_combine(&bone->world[12], m, v);'''


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()

    if MARKER in t:
        print('  Motion-NEON bereits vorhanden (Marker: %s).' % MARKER)
        return

    ins = pl.last_include_end(t)
    if ins < 0:
        pl.fail('kein #include gefunden - Header kann nicht eingefuegt werden')
        return
    t = t[:ins] + NEON_HEADER + t[ins:]

    results = []

    t, ok = pl.replace_function(
        t, 'Vec4_FromFixed12',
        r'^void\s+Vec4_FromFixed12\s*\(\s*float\s+out\[4\]\s*,\s*const\s+s16\s+in\[4\]\s*\)',
        NEW_VEC4_FROMFIXED12, must_contain=('4096.0f',))
    results.append(('Vec4_FromFixed12', ok))

    t, ok = pl.replace_function(
        t, 'Vec4_Dot',
        r'^float\s+Vec4_Dot\s*\(\s*const\s+float\s+a\[4\]\s*,\s*const\s+float\s+b\[4\]\s*\)',
        NEW_VEC4_DOT, must_contain=('a[0] * b[0]', 'a[3] * b[3]'))
    results.append(('Vec4_Dot', ok))

    t, ok = pl.replace_function(
        t, 'Quat_ToMatrix',
        r'^void\s+Quat_ToMatrix\s*\(\s*const\s+float\s+q\[4\]\s*,\s*float\s+m\[16\]\s*\)',
        NEW_QUAT_TOMATRIX, must_contain=('m[15] = 1', 'm[10] = 1 - 2'))
    results.append(('Quat_ToMatrix', ok))

    t, ok = pl.replace_function(
        t, 'ApplyRow',
        r'^static\s+inline\s+void\s+ApplyRow\s*\(\s*float\s*\*\s*o\s*,\s*const\s+float\s*\*\s*m\s*,\s*const\s+float\s*\*\s*v\s*\)',
        NEW_APPLYROW, must_contain=('memcpy(o, r', 'm[12 + k]'))
    results.append(('ApplyRow', ok))

    t, ok = pl.replace_snippet(t, 'Skeleton_Update', OLD_SKELETON_BLOCK, NEW_SKELETON_BLOCK)
    results.append(('Skeleton_Update', ok))

    p.write_text(t)

    print('  Motion-NEON eingefuegt:')
    for name, ok in results:
        print('    %-18s %s' % (name + ':', 'OK' if ok else 'FEHLT'))


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/engine/motion.cpp'
    print('Patche %s' % target)
    patch(target)
    pl.finish()
    print('Fertig.')
