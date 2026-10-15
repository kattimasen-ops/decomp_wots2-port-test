#!/usr/bin/env python3
"""
Ersetzt heiße Skalar-Schleifen in src/hal/gs.cpp durch NEON.

Enthält:
  1. wots2_lerp_vertex  — Vertex-Interpolation (2D)
  2. wots2_lerp_vertex3 — Vertex3-Interpolation (3D)
  3. wots2_box_outside  — Frustum-Culling

Die Lerp-Helper sind mit Interleaving geschrieben: die Ladeoperationen
werden zwischen die Berechnungen gezogen, damit der in-order Cortex-A35
seine Pipeline füllen kann (1 Load/Store-Port).

Python 3.6+ kompatibel (keine PEP-585-Typhinweise).
"""
import re
import sys
import pathlib


NEON_HELPER = r'''

// ── NEON-Helfer (aarch64) ─────────────────────────────────────────────
// Cortex-A35: in-order Pipeline, ein Load/Store-Port. Die Ladebefehle
// sind zwischen die Berechnungen gezogen (Interleaving).
#include <arm_neon.h>

static inline void wots2_lerp_vertex(const Vertex& a, const Vertex& b, float t, Vertex& o) {
    const float32x4_t vt   = vdupq_n_f32(t);
    const float32x4_t v1mt = vdupq_n_f32(1.0f - t);
    const float* pa = reinterpret_cast<const float*>(&a);
    const float* pb = reinterpret_cast<const float*>(&b);
    float*       po = reinterpret_cast<float*>(&o);
    const float32x4_t a0 = vld1q_f32(pa);
    const float32x4_t b0 = vld1q_f32(pb);
    const float32x4_t r0 = vmlaq_f32(vmulq_f32(a0, v1mt), b0, vt);
    const float32x4_t a1 = vld1q_f32(pa + 4);
    const float32x4_t b1 = vld1q_f32(pb + 4);
    vst1q_f32(po, r0);
    const float32x4_t r1 = vmlaq_f32(vmulq_f32(a1, v1mt), b1, vt);
    vst1q_f32(po + 4, r1);
}

static inline void wots2_lerp_vertex3(const Vertex3& a, const Vertex3& b, float t, Vertex3& o) {
    const float32x4_t vt   = vdupq_n_f32(t);
    const float32x4_t v1mt = vdupq_n_f32(1.0f - t);
    const float* pa = reinterpret_cast<const float*>(&a);
    const float* pb = reinterpret_cast<const float*>(&b);
    float*       po = reinterpret_cast<float*>(&o);
    const float32x4_t a0 = vld1q_f32(pa);
    const float32x4_t b0 = vld1q_f32(pb);
    const float32x4_t r0 = vmlaq_f32(vmulq_f32(a0, v1mt), b0, vt);
    const float32x4_t a1 = vld1q_f32(pa + 4);
    const float32x4_t b1 = vld1q_f32(pb + 4);
    vst1q_f32(po, r0);
    const float32x4_t r1 = vmlaq_f32(vmulq_f32(a1, v1mt), b1, vt);
    vst1q_f32(po + 4, r1);
    po[8] = pa[8] + (pb[8] - pa[8]) * t;
}

static inline bool wots2_box_outside(const float* lo, const float* hi, const float* m, float xscale) {
    const float32x4_t c0 = vld1q_f32(m + 0);
    const float32x4_t c1 = vld1q_f32(m + 4);
    const float32x4_t c2 = vld1q_f32(m + 8);
    const float32x4_t c3 = vld1q_f32(m + 12);
    alignas(16) float e[8][4];
    for (int i = 0; i < 8; ++i) {
        e[i][0] = (i & 1) ? hi[0] : lo[0];
        e[i][1] = (i & 2) ? hi[1] : lo[1];
        e[i][2] = (i & 4) ? hi[2] : lo[2];
        e[i][3] = 1.0f;
    }
    int out[6] = {0, 0, 0, 0, 0, 0};
    for (int i = 0; i < 8; ++i) {
        const float32x4_t ve = vld1q_f32(e[i]);
        const float cx = vaddvq_f32(vmulq_f32(ve, c0));
        const float cy = vaddvq_f32(vmulq_f32(ve, c1));
        const float cz = vaddvq_f32(vmulq_f32(ve, c2));
        const float cw = vaddvq_f32(vmulq_f32(ve, c3));
        const float cxs = cx * xscale;
        out[0] += (cxs < -cw);
        out[1] += (cxs >  cw);
        out[2] += (cy  < -cw);
        out[3] += (cy  >  cw);
        out[4] += (cz  < -cw);
        out[5] += (cz  >  cw);
    }
    for (int k = 0; k < 6; ++k)
        if (out[k] == 8) return true;
    return false;
}
'''


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()

    if 'wots2_lerp_vertex' in t:
        print('  NEON bereits vorhanden — überspringe.')
        return

    anchor_re = re.compile(r'struct\s+Vertex3\s*\{[^}]*\};\s*\n')
    m = anchor_re.search(t)
    if not m:
        print('  FEHLER: struct Vertex3 nicht gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t[:m.end()] + NEON_HELPER + t[m.end():]

    old_v2 = re.compile(
        r'(o\.x = mix\(a\[i\]\.x, o\.x, t\); o\.y = mix\(a\[i\]\.y, o\.y, t\);\s*'
        r'o\.r = mix\(a\[i\]\.r, o\.r, t\); o\.g = mix\(a\[i\]\.g, o\.g, t\);\s*'
        r'o\.b = mix\(a\[i\]\.b, o\.b, t\); o\.a = mix\(a\[i\]\.a, o\.a, t\);)',
        re.S)
    t, n2 = old_v2.subn(
        'wots2_lerp_vertex(a[i], s_tmp2[(size_t)i], t, s_tmp2[(size_t)i]);',
        t)

    old_v3 = re.compile(
        r'(o\.x = mix\(a\[i\]\.x, o\.x, t\); o\.y = mix\(a\[i\]\.y, o\.y, t\); o\.z = mix\(a\[i\]\.z, o\.z, t\);\s*'
        r'if \(c\.lerpUv\) \{ o\.u = mix\(a\[i\]\.u, o\.u, t\); o\.v = mix\(a\[i\]\.v, o\.v, t\); \}\s*'
        r'o\.r = mix\(a\[i\]\.r, o\.r, t\); o\.g = mix\(a\[i\]\.g, o\.g, t\);\s*'
        r'o\.b = mix\(a\[i\]\.b, o\.b, t\); o\.a = mix\(a\[i\]\.a, o\.a, t\);)',
        re.S)
    t, n3 = old_v3.subn(
        'wots2_lerp_vertex3(a[i], s_tmp3[(size_t)i], t, s_tmp3[(size_t)i]);',
        t)

    old_box = re.compile(
        r'static\s+bool\s+box_outside\s*\(\s*const\s+float\s*\*\s*lo\s*,\s*'
        r'const\s+float\s*\*\s*hi\s*,\s*const\s+float\s*\*\s*m\s*,\s*float\s+xscale\s*\)'
        r'\s*\{.*?\n\}',
        re.S)
    t, nbox = old_box.subn(
        'static bool box_outside(const float* lo, const float* hi, '
        'const float* m, float xscale) {\n'
        '    return wots2_box_outside(lo, hi, m, xscale);\n'
        '}',
        t)

    p.write_text(t)
    print('  NEON-Helper eingefügt (mit Interleaving).')
    print('  verts2: %d, verts3: %d, box_outside: %d gepatcht.' % (n2, n3, nbox))


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
