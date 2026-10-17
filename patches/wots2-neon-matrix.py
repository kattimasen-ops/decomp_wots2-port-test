#!/usr/bin/env python3
import sys
from pathlib import Path

PATH   = Path("src/native/hle.cpp")
MARKER = "/* WOTS2_NEON_MATRIX */"

OLD = """void Matrix_Multiply(void* dst, const void* a, const void* b) {
    mat_mul(static_cast<const float*>(b), static_cast<const float*>(a), static_cast<float*>(dst));
}"""

NEW = """void Matrix_Multiply(void* dst, const void* a, const void* b) {
    /* WOTS2_NEON_MATRIX */
    #if defined(__ARM_NEON)
    const float* A = static_cast<const float*>(b);
    const float* B = static_cast<const float*>(a);
    float* out = static_cast<float*>(dst);
    float32x4_t r0 = vmulq_n_f32(vld1q_f32(&A[0]), B[0]);
    float32x4_t r1 = vmulq_n_f32(vld1q_f32(&A[0]), B[1]);
    float32x4_t r2 = vmulq_n_f32(vld1q_f32(&A[0]), B[2]);
    float32x4_t r3 = vmulq_n_f32(vld1q_f32(&A[0]), B[3]);
    r0 = vmlaq_n_f32(r0, vld1q_f32(&A[4]), B[4]);
    r1 = vmlaq_n_f32(r1, vld1q_f32(&A[4]), B[5]);
    r2 = vmlaq_n_f32(r2, vld1q_f32(&A[4]), B[6]);
    r3 = vmlaq_n_f32(r3, vld1q_f32(&A[4]), B[7]);
    r0 = vmlaq_n_f32(r0, vld1q_f32(&A[8]), B[8]);
    r1 = vmlaq_n_f32(r1, vld1q_f32(&A[8]), B[9]);
    r2 = vmlaq_n_f32(r2, vld1q_f32(&A[8]), B[10]);
    r3 = vmlaq_n_f32(r3, vld1q_f32(&A[8]), B[11]);
    r0 = vmlaq_n_f32(r0, vld1q_f32(&A[12]), B[12]);
    r1 = vmlaq_n_f32(r1, vld1q_f32(&A[12]), B[13]);
    r2 = vmlaq_n_f32(r2, vld1q_f32(&A[12]), B[14]);
    r3 = vmlaq_n_f32(r3, vld1q_f32(&A[12]), B[15]);
    vst1q_f32(&out[0], r0);
    vst1q_f32(&out[4], r1);
    vst1q_f32(&out[8], r2);
    vst1q_f32(&out[12], r3);
    #else
    mat_mul(static_cast<const float*>(b), static_cast<const float*>(a), static_cast<float*>(dst));
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
