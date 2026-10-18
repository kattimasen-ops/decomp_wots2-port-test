#!/usr/bin/env python3
"""Entfernt unsicheres OpenMP aus model.cpp und fügt sicheres OpenMP in motion.cpp ein."""
import sys, pathlib

# 1. Fix model.cpp (Unsicheres OpenMP entfernen, das die Glitches verursacht)
p_model = pathlib.Path("src/native/model.cpp")
if p_model.exists():
    t = p_model.read_text()
    if "#pragma omp parallel for\n    for (const auto& in : part) {" in t:
        t = t.replace("#pragma omp parallel for\n    for (const auto& in : part) {", "for (const auto& in : part) {")
        p_model.write_text(t)
        print("  model.cpp: Unsicheres OpenMP entfernt (verhindert Grafik-Glitches).")

# 2. Patch motion.cpp (Sicheres OpenMP in Skeleton_Update)
p_motion = pathlib.Path("src/engine/motion.cpp")
if p_motion.exists():
    t = p_motion.read_text()
    anchor = "for (int i = 0; i < self->count; i++, bone++) {"
    if anchor in t:
        # Wir teilen die Schleife sicher auf die 4 Kerne auf
        new_loop = """Bone* base_bone = guest::ptr<Bone>(self->bones);
            #pragma omp parallel for schedule(static)
            for (int i = 0; i < self->count; i++) {
                Bone* bone = base_bone + i;"""
        t = t.replace(anchor, new_loop, 1)
        p_motion.write_text(t)
        print("  motion.cpp: Sicheres OpenMP in Skeleton_Update eingebaut.")
