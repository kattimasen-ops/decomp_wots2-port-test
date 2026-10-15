#!/usr/bin/env python3
"""
NEON-Optimierungen für src/game/collision_world.cpp.

Enthält:
  1. Apply()            — 4x4-Matrix-Vektor-Multiplikation (NEON)
  2. DistanceSquared()  — vermeidet sqrtf in den häufigen Vergleichen
  3. Towards()          — Normalisierung eines 4-Vektors (NEON)

Klammer-Matching statt [^}]* — verschachtelte Blöcke in Apply(),
Distance(), Towards() werden korrekt erfasst (Bugfix v1 -> v2).

Python 3.6+ kompatibel.
"""
import re
import sys
import pathlib


NEON_HELPER = r'''
// ── NEON-Beschleunigung (aarch64) ────────────────────────────────────
#if defined(__aarch64__)
#include <arm_neon.h>

// 4x4-Matrix × 4-Vektor (Zeilen-Konvention: v · M).
static inline void wots2_apply_neon(float* out, const float* m, const float* v) {
    const float32x4_t vv = vld1q_f32(v);
    float32x4_t r = vmulq_laneq_f32(vld1q_f32(m +  0), vv, 0);
    r = vmlaq_laneq_f32(r, vld1q_f32(m +  4), vv, 1);
    r = vmlaq_laneq_f32(r, vld1q_f32(m +  8), vv, 2);
    r = vmlaq_laneq_f32(r, vld1q_f32(m + 12), vv, 3);
    vst1q_f32(out, r);
}

// (a − b), normalisiert über alle vier Komponenten. Auf dem A35 wird
// vaddvq_f32 (horizontale Summe) in 2 Zyklen ausgeführt; vgl. die
// Skalar-Version mit 4 Subtraktionen, 4 Multiplikationen, 3 Additionen.
static inline void wots2_towards_neon(float* out, const float* a, const float* b) {
    const float32x4_t d = vsubq_f32(vld1q_f32(a), vld1q_f32(b));
    const float sum = vaddvq_f32(vmulq_f32(d, d));
    const float len = sqrtf(sum);
    const float scale = len != 0.0f ? 1.0f / len : 0.0f;
    vst1q_f32(out, vmulq_n_f32(d, scale));
}

#define WOTS2_APPLY(out, m, v)      wots2_apply_neon((out), (m), (v))
#define WOTS2_TOWARDS(out, a, b)    wots2_towards_neon((out), (a), (b))

#else
#define WOTS2_APPLY(out, m, v) do { \
    float _r[4]; \
    for (int _j = 0; _j < 4; _j++) \
        _r[_j] = (v)[0]*(m)[_j] + (v)[1]*(m)[4+_j] + (v)[2]*(m)[8+_j] + (v)[3]*(m)[12+_j]; \
    memcpy((out), _r, 16); \
} while (0)
#define WOTS2_TOWARDS(out, a, b) do { \
    float _d[4] = {(a)[0]-(b)[0], (a)[1]-(b)[1], (a)[2]-(b)[2], (a)[3]-(b)[3]}; \
    float _l = sqrtf(_d[0]*_d[0]+_d[1]*_d[1]+_d[2]*_d[2]+_d[3]*_d[3]); \
    float _s = _l != 0.0f ? 1.0f / _l : 0.0f; \
    for (int _i = 0; _i < 4; _i++) (out)[_i] = _d[_i] * _s; \
} while (0)
#endif
'''


def find_matching_brace(text, open_idx):
    """open_idx zeigt auf '{'. Liefert Index NACH dem passenden '}'."""
    depth = 0
    i = open_idx
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
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    return -1


def replace_function(text, sig_regex, new_body):
    m = re.search(sig_regex, text, re.S)
    if not m:
        return text, 0
    brace = text.find('{', m.end() - 1)
    if brace < 0:
        return text, 0
    end = find_matching_brace(text, brace)
    if end < 0:
        return text, 0
    return text[:m.start()] + new_body + text[end:], 1


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()

    if 'wots2_apply_neon' in t:
        print('  NEON-Apply bereits vorhanden — ueberspringe.')
        return

    last_inc = list(re.finditer(r'^#include [<"][^\n]+[>\"]\n', t, re.M))[-1]
    t = t[:last_inc.end()] + NEON_HELPER + t[last_inc.end():]

    # ── Apply() ──────────────────────────────────────────────────────
    sig_apply = (r'static\s+void\s+Apply\s*\(\s*float\s*\*\s*out\s*,\s*'
                 r'const\s+float\s*\*\s*m\s*,\s*const\s+float\s*\*\s*v\s*\)')
    new_apply = (
        'static inline void Apply(float* out, const float* m, const float* v) {\n'
        '    WOTS2_APPLY(out, m, v);\n'
        '}'
    )
    t, n_apply = replace_function(t, sig_apply, new_apply)

    # ── Towards() ────────────────────────────────────────────────────
    sig_towards = (r'static\s+void\s+Towards\s*\(\s*float\s*\*\s*out\s*,\s*'
                   r'const\s+float\s*\*\s*a\s*,\s*const\s+float\s*\*\s*b\s*\)')
    new_towards = (
        'static inline void Towards(float* out, const float* a, const float* b) {\n'
        '    WOTS2_TOWARDS(out, a, b);\n'
        '}'
    )
    t, n_towards = replace_function(t, sig_towards, new_towards)

    # ── Distance() → DistanceSquared() ───────────────────────────────
    n_dist = n_cmp = 0
    if 'DistanceSquared' not in t:
        sig_dist = (r'static\s+inline\s+float\s+Distance\s*\(\s*const\s+float\s*\*\s*a\s*,\s*'
                    r'const\s+float\s*\*\s*b\s*\)')
        new_dist = (
            'static inline float Distance(const float* a, const float* b) {\n'
            '    const float d[3] = {a[0] - b[0], a[1] - b[1], a[2] - b[2]};\n'
            '    return sqrtf(Dot(d, d));\n'
            '}\n'
            'static inline float DistanceSquared(const float* a, const float* b) {\n'
            '    const float d[3] = {a[0] - b[0], a[1] - b[1], a[2] - b[2]};\n'
            '    return Dot(d, d);\n'
            '}'
        )
        t, n_dist = replace_function(t, sig_dist, new_dist)

        old_cmp = re.compile(
            r'if\s*\(\s*Distance\s*\(\s*Centre\s*\(\s*a\s*\)\s*,\s*'
            r'Centre\s*\(\s*b\s*\)\s*\)\s*>\s*a->radius\s*\+\s*b->radius\s*\)\s*'
            r'return\s+false\s*;')
        new_cmp = (
            'const float radSum = a->radius + b->radius;\n'
            '    if (DistanceSquared(Centre(a), Centre(b)) > radSum * radSum)\n'
            '        return false;')
        t, n_cmp = old_cmp.subn(new_cmp, t)

    p.write_text(t)
    print('  NEON-Helper eingefuegt.')
    print('  Apply: %d, Towards: %d, Distance: %d, Vergleich: %d'
          % (n_apply, n_towards, n_dist, n_cmp))


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/game/collision_world.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
