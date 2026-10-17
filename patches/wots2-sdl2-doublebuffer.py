#!/usr/bin/env python3
"""Setzt SDL_HINT_VIDEO_DOUBLE_BUFFER vor SDL_Init (RK3326-Fix)."""
import sys, re, pathlib

p = pathlib.Path(sys.argv[1])
t = p.read_text()

anchor = "SDL_Init(SDL_INIT_VIDEO);"
if anchor not in t:
    print("FEHLER: SDL_Init nicht gefunden.", file=sys.stderr)
    sys.exit(1)

inject = "SDL_SetHint(SDL_HINT_VIDEO_DOUBLE_BUFFER, \"1\");\n    "
t = t.replace(anchor, inject + anchor, 1)
p.write_text(t)
print("OK: SDL_HINT_VIDEO_DOUBLE_BUFFER in gs.cpp gesetzt.")
