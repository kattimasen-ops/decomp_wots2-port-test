#!/usr/bin/env python3
import sys
from pathlib import Path

PATH   = Path("src/game/camera.cpp")
MARKER = "/* WOTS2_NEON_VECMATH */"

OLD = """// 0x1071C0
static inline void Normalize(float* d, const float* s) {
    const float q = 1.0f / sqrtf(Dot(s, s));
    for (int i = 0; i < 4; i++) d[i] = s[i] * q;
}"""

NEW = """// 0x1071C0
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

def main():
    if not PATH.exists(): sys.exit(1)
    src = PATH.read_text()
    if MARKER in src: return
    if src.count(OLD) != 1: sys.exit(1)
    if "#include <arm_neon.h>" not in src:
        src = src.replace("#include <cmath>", "#include <cmath>\n#include <arm_neon.h>")
    PATH.write_text(src.replace(OLD, NEW, 1))
