#!/usr/bin/env python3
"""
patches/wots2-neon-skinning.py   (v2)

NEON fuer das CPU-Skinning in src/native/model.cpp. Das ist die innerste
Schleife des Modell-Zeichnens: Sie laeuft fuer JEDEN Vertex JEDES gezeichneten
Modells in JEDEM Frame, mit je zwei Gelenk-Einfluessen:

    for (const auto& in : part) {
        ...
        for (int k = 0; k < 3; k++)
            p[k] += in.q[0]*m[k] + in.q[1]*m[4+k] + in.q[2]*m[8+k] + in.w*m[12+k];
    }

Dein Timing zeigt rund 16 ms pro Frame in CharaMgr_Draw; ein grosser Teil davon
duerfte genau diese Schleife sein.

Warum v2: Der alte Patch lief nie (main() wurde nicht aufgerufen). Die Idee war
richtig, die Umsetzung aber unnoetig langsam: Pro Einfluss wurde das Ergebnis in
ein Array gespeichert und danach skalar wieder gelesen. v2 haelt die Summe die
ganze Schleife lang in einem NEON-Register und liest erst am Ende die drei
Komponenten aus.

Rechnet exakt wie der Skalar-Code: gleiche Additionsreihenfolge
(((q0*m0 + q1*m4) + q2*m8) + w*m12, dann + p). Der Patch steckt in
'#if defined(__aarch64__)', <arm_neon.h> wird nur dort eingebunden.

Idempotent: Marker 'wots2_neon_skinning_v2'.
Zieldatei: src/native/model.cpp
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wots2_patchlib as pl  # noqa: E402

MARKER = "wots2_neon_skinning_v2"

OLD = '''for (const auto& in : part) {
                    if (in.bone < 0 || in.bone >= (int)bones.size())
                        continue;
                    const float* m = pose ? pose + in.bone * 16 : bones[in.bone].rest;
                    for (int k = 0; k < 3; k++)
                        p[k] += in.q[0] * m[k] + in.q[1] * m[4 + k] + in.q[2] * m[8 + k] + in.w * m[12 + k];
                }'''

NEW = '''/* wots2_neon_skinning_v2 */
#if defined(__aarch64__)
                float32x4_t wots2_acc = vdupq_n_f32(0.0f);
                for (const auto& in : part) {
                    if (in.bone < 0 || in.bone >= (int)bones.size())
                        continue;
                    const float* m = pose ? pose + in.bone * 16 : bones[in.bone].rest;
                    float32x4_t r = vmulq_n_f32(vld1q_f32(m), in.q[0]);
                    r = vmlaq_n_f32(r, vld1q_f32(m + 4),  in.q[1]);
                    r = vmlaq_n_f32(r, vld1q_f32(m + 8),  in.q[2]);
                    r = vmlaq_n_f32(r, vld1q_f32(m + 12), in.w);
                    wots2_acc = vaddq_f32(wots2_acc, r);
                }
                p[0] += vgetq_lane_f32(wots2_acc, 0);
                p[1] += vgetq_lane_f32(wots2_acc, 1);
                p[2] += vgetq_lane_f32(wots2_acc, 2);
#else
                for (const auto& in : part) {
                    if (in.bone < 0 || in.bone >= (int)bones.size())
                        continue;
                    const float* m = pose ? pose + in.bone * 16 : bones[in.bone].rest;
                    for (int k = 0; k < 3; k++)
                        p[k] += in.q[0] * m[k] + in.q[1] * m[4 + k] + in.q[2] * m[8 + k] + in.w * m[12 + k];
                }
#endif'''

NEON_INCLUDE = '''#if defined(__aarch64__)
#include <arm_neon.h>
#endif
'''


def patch(path):
    p = pathlib.Path(path)
    if not p.exists():
        pl.fail('Zieldatei %s existiert nicht' % path)
        return
    t = p.read_text()
    if MARKER in t:
        print('  NEON-Skinning bereits vorhanden (Marker: %s).' % MARKER)
        return

    t, ok = pl.replace_snippet(t, 'Skinning-Schleife', OLD, NEW)
    if not ok:
        return
    ins = pl.last_include_end(t)
    if ins < 0:
        pl.fail('kein #include gefunden - <arm_neon.h> konnte nicht eingebunden werden')
        return
    t = t[:ins] + NEON_INCLUDE + t[ins:]
    p.write_text(t)
    print('  NEON-Skinning eingebaut (Summe bleibt im Register).')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/native/model.cpp'
    print('Patche %s' % target)
    patch(target)
    pl.finish()
    print('Fertig.')
