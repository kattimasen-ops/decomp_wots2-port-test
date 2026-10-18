#!/usr/bin/env python3
"""
patches/wots2-neon.py   (Revision v4)

Ersetzt zwei heisse Skalar-Stellen in src/hal/gs.cpp durch NEON:

  1. verts2/verts3: Vertex-Interpolation zwischen zwei Frames
     (wots2_lerp_vertex, wots2_lerp_vertex3)
  2. box_outside:   Frustum-Culling einer Box (wots2_box_outside)

Was v4 gegenueber v3 aendert
----------------------------
  * FEHLER BEHOBEN (Interpolation): v3 hat alle 8 bzw. 9 Floats eines
    Vertex interpoliert. Das Original tut das nicht:
      - Vertex (2D):  x, y, r, g, b, a  - u und v bleiben unveraendert.
      - Vertex3 (3D): x, y, z, r, g, b, a - u und v nur, wenn c.lerpUv
        gesetzt ist.
    v3 hat also Texturkoordinaten ueberblendet, die das Original gar nicht
    anfasst. Das waere bei animierten Texturen als Verschmieren sichtbar
    geworden (nur in Zwischenbildern, also wenn video.fps ueber der
    Spielrate liegt). v4 haelt sich exakt ans Original.
  * Die Interpolation rechnet jetzt wie mix() im Original: a + (b - a) * t
    (v3: a*(1-t) + b*t, minimal andere Rundung).
  * box_outside rechnet pro Eckpunkt direkt mit den Matrixzeilen
    (c = p0*Zeile0 + p1*Zeile1 + p2*Zeile2 + Zeile3). Das braucht weder
    vld4q noch horizontale Additionen noch einen Zwischenspeicher und hat
    dieselbe Additionsreihenfolge wie die Skalar-Schleife.
  * Alles steckt in '#if defined(__aarch64__)' mit Skalar-Fallback.
  * Fehler werden als 'PATCH-FEHLER:' gemeldet.

Zur Einordnung: Beides sind Mikro-Optimierungen. box_outside kostet
geschaetzt unter 0,2 ms pro Frame, die Interpolation laeuft bei video.fps=30
gar nicht (nur in Zwischenbildern). Am gemessenen Engpass aendert das wenig.

Idempotent: Marker 'wots2_neon_gs_v4'.
Zieldatei: src/hal/gs.cpp
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wots2_patchlib as pl  # noqa: E402

MARKER = "wots2_neon_gs_v4"

NEON_HELPER = r'''
// wots2_neon_gs_v4 (wots2-neon.py)
#if defined(__aarch64__)
#include <arm_neon.h>

// a + (b - a) * t, genau wie mix() im Original.
static inline float32x4_t wots2_mix4(float32x4_t a, float32x4_t b, float t) {
    return vmlaq_n_f32(a, vsubq_f32(b, a), t);
}

// Vertex: x, y, u, v, r, g, b, a. Wie im Original werden u und v NICHT
// interpoliert (sie bleiben die von b). o darf b sein.
static inline void wots2_lerp_vertex(const Vertex& a, const Vertex& b, float t, Vertex& o) {
    const float* pa = reinterpret_cast<const float*>(&a);
    const float* pb = reinterpret_cast<const float*>(&b);
    float*       po = reinterpret_cast<float*>(&o);
    const float32x4_t a0 = vld1q_f32(pa),     b0 = vld1q_f32(pb);
    const float32x4_t a1 = vld1q_f32(pa + 4), b1 = vld1q_f32(pb + 4);
    const float32x4_t m0 = wots2_mix4(a0, b0, t);
    const float32x4_t m1 = wots2_mix4(a1, b1, t);
    vst1q_f32(po,     vcombine_f32(vget_low_f32(m0), vget_high_f32(b0)));    // x, y neu; u, v von b
    vst1q_f32(po + 4, m1);                                                   // r, g, b, a
}

// Vertex3: x, y, z, u, v, r, g, b, a. u und v nur mit lerpUv. o darf b sein.
static inline void wots2_lerp_vertex3(const Vertex3& a, const Vertex3& b, float t, Vertex3& o, bool lerpUv) {
    const float* pa = reinterpret_cast<const float*>(&a);
    const float* pb = reinterpret_cast<const float*>(&b);
    float*       po = reinterpret_cast<float*>(&o);
    const float32x4_t a0 = vld1q_f32(pa),     b0 = vld1q_f32(pb);        // x y z u
    const float32x4_t a1 = vld1q_f32(pa + 4), b1 = vld1q_f32(pb + 4);    // v r g b
    const float a8 = pa[8], b8 = pb[8];                                  // a (vor dem Schreiben lesen)
    float32x4_t m0 = wots2_mix4(a0, b0, t);
    float32x4_t m1 = wots2_mix4(a1, b1, t);
    if (!lerpUv) {
        m0 = vsetq_lane_f32(vgetq_lane_f32(b0, 3), m0, 3);               // u von b
        m1 = vsetq_lane_f32(vgetq_lane_f32(b1, 0), m1, 0);               // v von b
    }
    vst1q_f32(po,     m0);
    vst1q_f32(po + 4, m1);
    po[8] = a8 + (b8 - a8) * t;
}

// Box-gegen-Frustum, bitgleich zur Skalar-Schleife: pro Eckpunkt
// c = ((p0*Z0 + p1*Z1) + p2*Z2) + Z3 mit den Matrixzeilen Z0..Z3.
static inline bool wots2_box_outside(const float* lo, const float* hi, const float* m, float xscale) {
    const float32x4_t z0 = vld1q_f32(m),     z1 = vld1q_f32(m + 4);
    const float32x4_t z2 = vld1q_f32(m + 8), z3 = vld1q_f32(m + 12);
    const float xs[4] = {xscale, 1.0f, 1.0f, 1.0f};
    const float32x4_t vxs = vld1q_f32(xs);
    uint32x4_t allLt = vdupq_n_u32(0xFFFFFFFFu);      // Ecken, die links/unter/vor der Ebene liegen (alle 8?)
    uint32x4_t allGt = vdupq_n_u32(0xFFFFFFFFu);
    for (int i = 0; i < 8; ++i) {
        const float p0 = (i & 1) ? hi[0] : lo[0];
        const float p1 = (i & 2) ? hi[1] : lo[1];
        const float p2 = (i & 4) ? hi[2] : lo[2];
        float32x4_t c = vmulq_n_f32(z0, p0);
        c = vmlaq_n_f32(c, z1, p1);
        c = vmlaq_n_f32(c, z2, p2);
        c = vaddq_f32(c, z3);
        c = vmulq_f32(c, vxs);                         // c[0] *= xscale
        const float32x4_t w = vdupq_laneq_f32(c, 3);
        allLt = vandq_u32(allLt, vcltq_f32(c, vnegq_f32(w)));
        allGt = vandq_u32(allGt, vcgtq_f32(c, w));
    }
    uint32x4_t any = vorrq_u32(allLt, allGt);
    any = vsetq_lane_u32(0, any, 3);                   // Lane 3 (w) zaehlt nicht
    return vmaxvq_u32(any) != 0;
}
#else
static inline void wots2_lerp_vertex(const Vertex& a, const Vertex& b, float t, Vertex& o) {
    o.x = a.x + (b.x - a.x) * t; o.y = a.y + (b.y - a.y) * t;
    o.r = a.r + (b.r - a.r) * t; o.g = a.g + (b.g - a.g) * t;
    o.b = a.b + (b.b - a.b) * t; o.a = a.a + (b.a - a.a) * t;
    o.u = b.u; o.v = b.v;
}
static inline void wots2_lerp_vertex3(const Vertex3& a, const Vertex3& b, float t, Vertex3& o, bool lerpUv) {
    const float bu = b.u, bv = b.v;
    o.x = a.x + (b.x - a.x) * t; o.y = a.y + (b.y - a.y) * t; o.z = a.z + (b.z - a.z) * t;
    o.u = lerpUv ? a.u + (bu - a.u) * t : bu; o.v = lerpUv ? a.v + (bv - a.v) * t : bv;
    o.r = a.r + (b.r - a.r) * t; o.g = a.g + (b.g - a.g) * t;
    o.b = a.b + (b.b - a.b) * t; o.a = a.a + (b.a - a.a) * t;
}
#endif
'''

OLD_V2 = '''o.x = mix(a[i].x, o.x, t); o.y = mix(a[i].y, o.y, t);
            o.r = mix(a[i].r, o.r, t); o.g = mix(a[i].g, o.g, t);
            o.b = mix(a[i].b, o.b, t); o.a = mix(a[i].a, o.a, t);'''

OLD_V3 = '''o.x = mix(a[i].x, o.x, t); o.y = mix(a[i].y, o.y, t); o.z = mix(a[i].z, o.z, t);
            if (c.lerpUv) { o.u = mix(a[i].u, o.u, t); o.v = mix(a[i].v, o.v, t); }
            o.r = mix(a[i].r, o.r, t); o.g = mix(a[i].g, o.g, t);
            o.b = mix(a[i].b, o.b, t); o.a = mix(a[i].a, o.a, t);'''

BOX_SIG = (r'^static\s+bool\s+box_outside\s*\(\s*const\s+float\s*\*\s*lo\s*,\s*const\s+float\s*\*\s*hi\s*,'
           r'\s*const\s+float\s*\*\s*m\s*,\s*float\s+xscale\s*\)')


def patch(path):
    p = pathlib.Path(path)
    if not p.exists():
        pl.fail('Zieldatei %s existiert nicht' % path)
        return
    t = p.read_text()
    if MARKER in t:
        print('  NEON bereits vorhanden (Marker: %s).' % MARKER)
        return
    if 'wots2_lerp_vertex' in t:
        pl.fail('eine aeltere NEON-Version (v1-v3) steckt schon in der Datei - bitte nicht doppelt anwenden')
        return

    results = []

    t, ok = pl.replace_snippet(t, 'verts2 (2D-Interpolation)', OLD_V2,
                               'wots2_lerp_vertex(a[i], o, t, o);')
    results.append(('verts2', ok))
    t, ok = pl.replace_snippet(t, 'verts3 (3D-Interpolation)', OLD_V3,
                               'wots2_lerp_vertex3(a[i], o, t, o, c.lerpUv);')
    results.append(('verts3', ok))

    hit = pl.find_function(t, BOX_SIG)
    if hit is None:
        pl.fail('box_outside: Definition nicht gefunden')
        results.append(('box_outside', False))
    else:
        s, b, e = hit
        old_fn = t[s:e]
        flat = re.sub(r'\s+', ' ', old_fn)
        if 'out[6]' not in flat or 'xscale' not in flat:
            pl.fail('box_outside: Rumpf sieht anders aus als erwartet')
            results.append(('box_outside', False))
        else:
            head = t[s:b]
            inner = t[b + 1:e - 1]
            new_fn = (head + '{\n#if defined(__aarch64__)\n'
                      '    return wots2_box_outside(lo, hi, m, xscale);\n'
                      '#else' + inner + '#endif\n}')
            t = t[:s] + new_fn + t[e:]
            results.append(('box_outside', True))

    s3 = re.search(r'struct\s+Vertex3\s*\{[^}]*\}\s*;\s*\n', t)
    if not s3:
        pl.fail('struct Vertex3 nicht gefunden - Helfer kann nicht eingefuegt werden')
        return
    first_use = re.search(r'wots2_lerp_vertex|wots2_box_outside', t)
    if first_use and first_use.start() < s3.end():
        pl.fail('Helfer wuerde nach seiner ersten Verwendung stehen')
        return
    t = t[:s3.end()] + NEON_HELPER + t[s3.end():]
    p.write_text(t)

    print('  NEON-Helfer eingefuegt (aarch64, mit Skalar-Fallback).')
    for name, ok in results:
        print('    %-12s %s' % (name + ':', 'OK' if ok else 'FEHLT'))


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    pl.finish()
    print('Fertig.')
