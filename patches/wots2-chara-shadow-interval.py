#!/usr/bin/env python3
"""
patches/wots2-chara-shadow-interval.py — WOTS2_SHADOW_INTERVAL=N rendert
den Shadow-Pass nur jeden N-ten Frame neu. Default 4.
Patcht src/native/hle_chara.cpp. Idempotent ueber Marker
"wots2_chara_shadow_interval".
"""
import sys
import pathlib

MARKER = "wots2_chara_shadow_interval"

OLD = '''void hle_chara_shadow(Chara* c, float strength) {
    auto it = g_native.find(guest::addr(c));
'''

NEW = '''void hle_chara_shadow(Chara* c, float strength) {
    // wots2_chara_shadow_interval: nur jeden N-ten Frame neu rendern.
    static const int s_shadow_interval = getenv("WOTS2_SHADOW_INTERVAL")
        ? atoi(getenv("WOTS2_SHADOW_INTERVAL")) : 4;
    if (s_shadow_interval > 1 && (hal::gs::frame_count() % s_shadow_interval) != 0)
        return;
    auto it = g_native.find(guest::addr(c));
'''

def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    if MARKER in t:
        print('  Shadow-Interval bereits vorhanden.')
        return
    if OLD not in t:
        print('  FEHLER: hle_chara_shadow nicht gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t.replace(OLD, NEW, 1)
    p.write_text(t)
    print('  Shadow-Interval eingebaut.')

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/native/hle_chara.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
