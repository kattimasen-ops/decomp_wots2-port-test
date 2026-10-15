#!/usr/bin/env python3
"""Erzwingt den KMSDRM-Check in SDL2s sdlchecks.cmake."""
import sys, pathlib

p = pathlib.Path(sys.argv[1])
t = p.read_text()
old = '    if(PKG_KMSDRM_FOUND AND HAVE_OPENGL_EGL)'
new = '    set(PKG_KMSDRM_FOUND TRUE)\n    set(HAVE_OPENGL_EGL TRUE)\n    if(TRUE)'
if old in t:
    t = t.replace(old, new, 1)
    p.write_text(t)
    print("OK: KMSDRM-Check erzwungen")
else:
    print("WARNUNG: Anker nicht gefunden (evtl. schon gepatcht)")
