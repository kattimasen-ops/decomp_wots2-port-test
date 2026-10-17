#!/usr/bin/env python3
"""
patches/wots2-gs-state-dedup.py

Dedupliziert set_depth_bias() und set_overlay(): wenn der Wert seit dem
letzten Aufruf nicht geaendert hat, wird kein Cmd gepusht.

Model::draw ruft pro Batch BEIDE auf, auch wenn sich nur einer aendert.
Bei 231 Draws × 2 = ~460 State-Calls pro Frame, davon die Haelfte
redundant.  Nach dem Patch: nur echte Aenderungen.

Der Reset in begin_frame() auf (0, false) ist sicher, weil play() mit
state_2d() startet, das ebenfalls (0, false) setzt.

Patcht src/hal/gs.cpp. Idempotent ueber Marker "wots2_gs_state_dedup".
"""
import sys
import pathlib

MARKER = "wots2_gs_state_dedup"

OLD_SET = '''void set_depth_bias(int steps) { push(Op::Bias).i = steps; }
void set_overlay(bool on)      { push(Op::Overlay).i = on; }
'''

NEW_SET = '''// wots2_gs_state_dedup
static int  s_recBias = 0;
static bool s_recOverlay = false;
void set_depth_bias(int steps) {
    if (s_recBias == steps) return;
    s_recBias = steps;
    push(Op::Bias).i = steps;
}
void set_overlay(bool on) {
    if (s_recOverlay == on) return;
    s_recOverlay = on;
    push(Op::Overlay).i = on ? 1 : 0;
}
'''

OLD_BEGIN = '''    Cmd& fog = push(Op::Fog);
    memcpy(fog.f, s_recFog, sizeof(s_recFog));
    memcpy(fog.f + 4, s_recFogColor, sizeof(s_recFogColor));
    s_recOwner = -1;
}'''

NEW_BEGIN = '''    Cmd& fog = push(Op::Fog);
    memcpy(fog.f, s_recFog, sizeof(s_recFog));
    memcpy(fog.f + 4, s_recFogColor, sizeof(s_recFogColor));
    s_recOwner = -1;
    s_recBias = 0;              // wots2_gs_state_dedup: play() startet mit (0,false)
    s_recOverlay = false;
}'''

def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    if MARKER in t:
        print('  State-Dedup bereits vorhanden.')
        return
    if OLD_SET not in t:
        print('  FEHLER: set_depth_bias/set_overlay nicht gefunden.', file=sys.stderr)
        sys.exit(1)
    if OLD_BEGIN not in t:
        print('  FEHLER: begin_frame-Ende nicht gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t.replace(OLD_SET, NEW_SET, 1)
    t = t.replace(OLD_BEGIN, NEW_BEGIN, 1)
    p.write_text(t)
    print('  State-Dedup eingebaut.')

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
