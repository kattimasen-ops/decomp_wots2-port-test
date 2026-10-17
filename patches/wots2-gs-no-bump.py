#!/usr/bin/env python3
"""
patches/wots2-gs-no-bump.py

WOTS2_NO_BUMP=1 zwingt uBump.x = 0, wodurch bump_light() im Fragment-
Shader uebersprungen wird (Bump-Mapping aus). Kein Shader-Eingriff.

Idempotent ueber Marker 'wots2-gs-no-bump.py'.

Zieldatei: src/hal/gs.cpp

Python 3.6+ kompatibel.
"""
import sys
import pathlib

MARKER = "wots2-gs-no-bump.py"

OLD = '''    glUniform4f(s_uBump, s_light.bump, s_light.bumpDepth, s_light.characterBump, s_light.groundWarp);
'''

NEW = '''    // wots2-gs-no-bump.py
    // WOTS2_NO_BUMP=1 schaltet Bump-Mapping ab (bump_light() wird im
    // Shader uebersprungen, da uBump.x = 0). Spart zwei bis vier
    // Texture-Lookups pro Pixel auf dem Map-Pass.
    static const bool s_wots2_no_bump = getenv("WOTS2_NO_BUMP") != nullptr;
    glUniform4f(s_uBump,
                s_wots2_no_bump ? 0.0f : s_light.bump,
                s_light.bumpDepth,
                s_light.characterBump,
                s_light.groundWarp);
'''

def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    if MARKER in t:
        print('  GS-No-Bump bereits vorhanden.')
        return
    if OLD not in t:
        print('  FEHLER: glUniform4f(s_uBump, ...)-Zeile nicht gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t.replace(OLD, NEW, 1)
    p.write_text(t)
    print('  GS-No-Bump eingebaut (WOTS2_NO_BUMP).')

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
