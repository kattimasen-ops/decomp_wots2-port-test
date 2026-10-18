#!/usr/bin/env python3
"""Parallelisiert das CPU-Skinning in model.cpp via OpenMP."""
import sys, pathlib

p = pathlib.Path(sys.argv[1])
t = p.read_text()

# Finde die Skinning-Schleife (angepasst an den NEON-Patch)
anchor = "for (const auto& in : part) {"

if anchor not in t:
    print("FEHLER: Skinning-Schleife in model.cpp nicht gefunden.", file=sys.stderr)
    sys.exit(1)

# OpenMP-Pragma vor die Schleife setzen
if "#pragma omp parallel for" not in t:
    t = t.replace(anchor, "#pragma omp parallel for\n    " + anchor, 1)

p.write_text(t)
print("OK: OpenMP-Skinning in model.cpp aktiviert.")
