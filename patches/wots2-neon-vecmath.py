#!/usr/bin/env python3
"""
patches/wots2-neon-vecmath.py   (v3 — 2026-10-22)

NEON fuer Normalize() in src/game/camera.cpp.

Bug (v1/v2): Die NEON-Version summierte beim Quadrieren ALLE vier
Komponenten (x²+y²+z²+w²). Dot() in camera.cpp summiert aber nur drei:
    a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
Damit wurde jeder Vektor mit w=1 (padDir, curUp, Camera_GetViewRotation)
zu kurz normalisiert — Kamera zog schief.

v3 setzt die w-Komponente VOR der Summe auf 0. Und: v3 MIGRIERT bereits
kaputt gepatchte Dateien (Marker vorhanden, aber alter Bug drin) auf die
korrigierte Version — ohne dass die Quelle von Hand geaendert werden muss.

Idempotent: prueft auf 'vsetq_lane_f32(0.0f, sq, 3)' als Korrektheits-
marker. Wenn vorhanden → skip. Wenn nicht, aber kaputte Version da →
ersetzen. Wenn nicht, aber Original da → patchen.

Zieldatei: src/game/camera.cpp
"""
import sys
from pathlib import Path

PATH   = Path("src/game/camera.cpp")

OLD_ORIGINAL = """// 0x1071C0
static inline void Normalize(float* d, const float* s) {
    const float q = 1.0f / sqrtf(Dot(s, s));
    for (int i = 0; i < 4; i++) d[i] = s[i] * q;
}"""

# Die kaputte Version, wie sie der alte Patch eingebaut hat. Sie steht in
# deiner aktuellen camera.cpp — v3 erkennt sie und ersetzt sie.
OLD_BROKEN = """// 0x1071C0
static inline void Normalize(float* d, const float* s) {
    /* WOTS2_NEON_VECMATH */
    #if defined(__ARM_NEON)
    float32x4_t v = vld1q_f32(s);
    float32x4_t dot = vmulq_f32(v, v);
    float32x2_t sum = vadd_f32(vget_low_f32(dot), vget_high_f32(dot));
    float mag = vget_lane_f32(vpadd_f32(sum, sum), 0);
    float q = mag > 0.0f ? 1.0f / sqrtf(mag) : 0.0f;
    vst1q_f32(d, vmulq_n_f32(v, q));
    #else
    const float q = 1.0f / sqrtf(Dot(s, s));
    for (int i = 0; i < 4; i++) d[i] = s[i] * q;
    #endif
}"""

NEW = """// 0x1071C0
// (wots2-neon-vecmath v3: Dot() summiert nur x,y,z — NEON muss w beim
// Quadrieren auf 0 setzen, sonst wird jeder Vektor mit w=1 (padDir,
// curUp, Camera_GetViewRotation) zu kurz normalisiert.)
static inline void Normalize(float* d, const float* s) {
    /* WOTS2_NEON_VECMATH */
    #if defined(__ARM_NEON)
    float32x4_t v = vld1q_f32(s);
    float32x4_t sq = vmulq_f32(v, v);
    sq = vsetq_lane_f32(0.0f, sq, 3);          // w NICHT mitzaehlen (wie Dot)
    float32x2_t sum = vadd_f32(vget_low_f32(sq), vget_high_f32(sq));
    float mag = vget_lane_f32(vpaddf32_placeholder, 0);
    float q = 1.0f / sqrtf(mag);               // wie Skalar (auch inf bei mag=0)
    vst1q_f32(d, vmulq_n_f32(v, q));
    #else
    const float q = 1.0f / sqrtf(Dot(s, s));
    for (int i = 0; i < 4; i++) d[i] = s[i] * q;
    #endif
}""".replace('vpaddf32_placeholder', 'vpadd_f32(sum, sum)')


def main():
    if not PATH.exists():
        print(f"  FEHLER: {PATH} fehlt")
        return 1
    src = PATH.read_text()

    # 1. Schon korrekt? (v3-Korrekturmarker)
    if "vsetq_lane_f32(0.0f, sq, 3)" in src:
        print("  bereits korrekt (v3-Marker) — ueberspringe")
        return 0

    # 2. Kaputte Version da? (alte NEON-Version mit 4-Komponenten-Summe)
    if OLD_BROKEN in src:
        print("  kaputte NEON-Version gefunden — ersetze durch korrigierte")
        src = src.replace(OLD_BROKEN, NEW, 1)
    # 3. Original da? (kein NEON)
    elif OLD_ORIGINAL in src:
        print("  Original gefunden — baue korrigierte NEON-Version ein")
        if "#include <arm_neon.h>" not in src:
            if "#include <cmath>" not in src:
                print(f"  FEHLER: kein #include <cmath> in {PATH}")
                return 1
            src = src.replace("#include <cmath>",
                              "#include <cmath>\n#include <arm_neon.h>", 1)
        src = src.replace(OLD_ORIGINAL, NEW, 1)
    # 4. Weder noch — Datei unbekannt
    else:
        print(f"  FEHLER: weder Original noch kaputte Version in {PATH}")
        print("  Die Datei sieht anders aus als erwartet. Schick sie mir.")
        return 1

    PATH.write_text(src)
    print(f"  gepatcht: {PATH}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
