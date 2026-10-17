#!/usr/bin/env python3
"""
patches/wots2-gs-lights-cap.py

Begrenzt die Anzahl der Punktlichter, die pro Frame an den Fragment-
Shader hochgeladen werden. Der Shader iteriert `for (i < uLights)`, der
C++-Code setzt uLights. Default: 4 (Original: bis zu 16). Ueber
WOTS2_LIGHTS_MAX=N einstellbar, 0 = so viele wie der Shader hergibt.

Idempotent ueber Marker 'wots2-gs-lights-cap.py'.

Zieldatei: src/hal/gs.cpp

Python 3.6+ kompatibel.
"""
import sys
import pathlib

MARKER = "wots2-gs-lights-cap.py"

OLD = '''        float pos[16][4], col[16][3];
        for (; n < 16 && n < (int)nearest.size(); n++) {
            const float* l = &f.world.lights[(size_t)nearest[(size_t)n].second * 8];
            pos[n][0] = l[0]; pos[n][1] = l[1]; pos[n][2] = l[2];
            pos[n][3] = l[3] * s_light.lanternRadius / 5.0f;
            for (int k = 0; k < 3; k++)
                col[n][k] = l[4 + k] * s_light.lanternStrength;
        }
'''

NEW = '''        float pos[16][4], col[16][3];
        // wots2-gs-lights-cap.py
        // WOTS2_LIGHTS_MAX (Default 4): wie viele Punktlichter pro Frame
        // an den Shader hochgeladen werden. Der Shader iteriert bis
        // uLights, das gleich mitgesetzt wird. Reduziert die Pixel-Arbeit
        // im Map-Pass deutlich; 4 Laternen decken den sichtbaren Bereich
        // meist ab, mehr bringt kaum noch Licht dazu.
        static const int s_wots2_lights_cap = getenv("WOTS2_LIGHTS_MAX")
            ? atoi(getenv("WOTS2_LIGHTS_MAX")) : 4;
        const int s_wots2_lights_max =
            s_wots2_lights_cap <= 0 || s_wots2_lights_cap > 16 ? 16 : s_wots2_lights_cap;
        for (; n < s_wots2_lights_max && n < (int)nearest.size(); n++) {
            const float* l = &f.world.lights[(size_t)nearest[(size_t)n].second * 8];
            pos[n][0] = l[0]; pos[n][1] = l[1]; pos[n][2] = l[2];
            pos[n][3] = l[3] * s_light.lanternRadius / 5.0f;
            for (int k = 0; k < 3; k++)
                col[n][k] = l[4 + k] * s_light.lanternStrength;
        }
'''

def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    if MARKER in t:
        print('  GS-Lights-Cap bereits vorhanden.')
        return
    if OLD not in t:
        print('  FEHLER: Punktlichter-Schleife nicht gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t.replace(OLD, NEW, 1)
    p.write_text(t)
    print('  GS-Lights-Cap eingebaut (Default 4, WOTS2_LIGHTS_MAX).')

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
