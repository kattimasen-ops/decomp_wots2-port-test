#!/usr/bin/env python3
import sys
from pathlib import Path

PATH   = Path("src/game/world_effects.cpp")
MARKER = "/* WOTS2_NEON_PARTICLES */"

OLD = """int Particle_Update(Particle* self) {
    if (self->base.life == 0)
        return 0;
    self->base.life--;
    Add(self->pos, self->pos, self->vel);
    if (self->order != 0) {
        const FxOrder* order = P<FxOrder>(self->order);
        self->vel[1] -= order->gravity;
        ScaleXYZ(self->vel, self->vel, order->drag);"""

NEW = """int Particle_Update(Particle* self) {
    if (self->base.life == 0)
        return 0;
    self->base.life--;
    /* WOTS2_NEON_PARTICLES */
    #if defined(__ARM_NEON)
    float32x4_t p = vld1q_f32(self->pos);
    float32x4_t v = vld1q_f32(self->vel);
    p = vaddq_f32(p, v);
    vst1q_f32(self->pos, p);
    if (self->order != 0) {
        const FxOrder* order = P<FxOrder>(self->order);
        float grav_arr[4] = {0, order->gravity, 0, 0};
        v = vsubq_f32(v, vld1q_f32(grav_arr));
        v = vmulq_n_f32(v, order->drag);
        vst1q_f32(self->vel, v);
    #else
    Add(self->pos, self->pos, self->vel);
    if (self->order != 0) {
        const FxOrder* order = P<FxOrder>(self->order);
        self->vel[1] -= order->gravity;
        ScaleXYZ(self->vel, self->vel, order->drag);
    #endif"""

def main():
    if not PATH.exists(): sys.exit(1)
    src = PATH.read_text()
    if MARKER in src: return
    if src.count(OLD) != 1: sys.exit(1)
    if "#include <arm_neon.h>" not in src:
        src = src.replace("#include <cmath>", "#include <cmath>\n#include <arm_neon.h>")
    PATH.write_text(src.replace(OLD, NEW, 1))
