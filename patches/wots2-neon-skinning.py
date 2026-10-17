#!/usr/bin/env python3
import sys
from pathlib import Path

PATH   = Path("src/native/model.cpp")
MARKER = "/* WOTS2_NEON_SKINNING */"

OLD = """                for (const auto& in : part) {
                    if (in.bone < 0 || in.bone >= (int)bones.size())
                        continue;
                    const float* m = pose ? pose + in.bone * 16 : bones[in.bone].rest;
                    for (int k = 0; k < 3; k++)
                        p[k] += in.q[0] * m[k] + in.q[1] * m[4 + k] + in.q[2] * m[8 + k] + in.w * m[12 + k];
                }"""

NEW = """                /* WOTS2_NEON_SKINNING */
                #if defined(__ARM_NEON)
                for (const auto& in : part) {
                    if (in.bone < 0 || in.bone >= (int)bones.size())
                        continue;
                    const float* m = pose ? pose + in.bone * 16 : bones[in.bone].rest;
                    float32x4_t q0 = vdupq_n_f32(in.q[0]);
                    float32x4_t q1 = vdupq_n_f32(in.q[1]);
                    float32x4_t q2 = vdupq_n_f32(in.q[2]);
                    float32x4_t q3 = vdupq_n_f32(in.w);
                    float32x4_t res = vmulq_f32(vld1q_f32(&m[0]), q0);
                    res = vmlaq_f32(res, vld1q_f32(&m[4]), q1);
                    res = vmlaq_f32(res, vld1q_f32(&m[8]), q2);
                    res = vmlaq_f32(res, vld1q_f32(&m[12]), q3);
                    float out[4];
                    vst1q_f32(out, res);
                    p[0] += out[0];
                    p[1] += out[1];
                    p[2] += out[2];
                }
                #else
                for (const auto& in : part) {
                    if (in.bone < 0 || in.bone >= (int)bones.size())
                        continue;
                    const float* m = pose ? pose + in.bone * 16 : bones[in.bone].rest;
                    for (int k = 0; k < 3; k++)
                        p[k] += in.q[0] * m[k] + in.q[1] * m[4 + k] + in.q[2] * m[8 + k] + in.w * m[12 + k];
                }
                #endif"""

def main():
    if not PATH.exists(): sys.exit(1)
    src = PATH.read_text()
    if MARKER in src: return
    if src.count(OLD) != 1: sys.exit(1)
    if "#include <arm_neon.h>" not in src:
        src = src.replace("#include <cmath>", "#include <cmath>\n#include <arm_neon.h>")
    PATH.write_text(src.replace(OLD, NEW, 1))
