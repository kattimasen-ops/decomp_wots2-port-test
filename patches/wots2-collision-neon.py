#!/usr/bin/env python3
"""
NEON-Optimierungen für src/game/collision_world.cpp.

Fix gegenüber v1: Klammer-Matching statt [^}]* — verschachtelte
Blöcke in Apply()/Distance() werden korrekt erfasst.

Python 3.6+ kompatibel.
"""
import re
import sys
import pathlib


NEON_APPLY_HELPER = r'''
// ── NEON-Beschleunigung (aarch64) ────────────────────────────────────
#if defined(__aarch64__)
#include <arm_neon.h>
static inline void wots2_apply_neon(float* out, const float* m, const float* v) {
    const float32x4_t vv = vld1q_f32(v);
    float32x4_t r = vmulq_laneq_f32(vld1q_f32(m +  0), vv, 0);
    r = vmlaq_laneq_f32(r, vld1q_f32(m +  4), vv, 1);
    r = vmlaq_laneq_f32(r, vld1q_f32(m +  8), vv, 2);
    r = vmlaq_laneq_f32(r, vld1q_f32(m + 12), vv, 3);
    vst1q_f32(out, r);
}
#define WOTS2_APPLY(out, m, v) wots2_apply_neon((out), (m), (v))
#else
#define WOTS2_APPLY(out, m, v) do { \
    float _r[4]; \
    for (int _j = 0; _j < 4; _j++) \
        _r[_j] = (v)[0]*(m)[_j] + (v)[1]*(m)[4+_j] + (v)[2]*(m)[8+_j] + (v)[3]*(m)[12+_j]; \
    memcpy((out), _r, 16); \
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
    """Ersetzt eine Funktion, deren Signatur auf sig_regex passt."""
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
        print('  NEON-Apply bereits vorhanden — überspringe.')
        return

    last_inc = list(re.finditer(r'^#include [<"][^\n]+[>\"]\n', t, re.M))[-1]
    t = t[:last_inc.end()] + NEON_APPLY_HELPER + t[last_inc.end():]

    # ── Apply() ──────────────────────────────────────────────────────
    sig_apply = (r'static\s+void\s+Apply\s*\(\s*float\s*\*\s*out\s*,\s*'
                 r'const\s+float\s*\*\s*m\s*,\s*const\s+float\s*\*\s*v\s*\)')
    new_apply = (
        'static inline void Apply(float* out, const float* m, const float* v) {\n'
        '    WOTS2_APPLY(out, m, v);\n'
        '}'
    )
    t, n_apply = replace_function(t, sig_apply, new_apply)

    # ── Distance() → DistanceSquared() ───────────────────────────────
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
        print('  Distance: %d Funktion(en), %d Vergleich(e)' % (n_dist, n_cmp))

    p.write_text(t)
    print('  NEON-Apply: %d Stelle(n)' % n_apply)


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/game/collision_world.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
