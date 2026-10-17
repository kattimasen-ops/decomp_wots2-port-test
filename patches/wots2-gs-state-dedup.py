#!/usr/bin/env python3
"""
patches/wots2-gs-state-dedup.py  (v2)

Dedupliziert set_depth_bias() und set_overlay(): wenn der Wert seit dem
letzten Aufruf nicht geaendert hat, wird kein Cmd gepusht.

v2 behebt den Build-Fehler aus v1: die statics s_recBias/s_recOverlay
wurden in set_depth_bias() deklariert, aber in begin_frame() benutzt
(was weiter oben in der Datei steht). Sie gehoeren in den gemeinsamen
recording-state-Block am Anfang von gs.cpp, wo auch s_recBlend,
s_recAlphaRef, s_recFog etc. stehen.

v2 erkennt auch den kaputten v1-Zustand (statics in set_depth_bias)
und korrigiert ihn. Das ist idempotent.

Patcht src/hal/gs.cpp. Marker "wots2_gs_state_dedup".
"""
import sys
import pathlib

MARKER = "wots2_gs_state_dedup"

# ── Anker 1: recording-state-Block, hier gehoeren die statics hin ──────
ANCHOR_STATE = 'static int   s_recBlend = 0, s_recAlphaRef = 0;\n'
REPL_STATE = (
    'static int   s_recBlend = 0, s_recAlphaRef = 0;\n'
    '// wots2_gs_state_dedup: letzte gesetzte Bias/Overlay-Werte\n'
    'static int   s_recBias = 0;\n'
    'static bool  s_recOverlay = false;\n'
)

# ── Anker 2: die zwei Funktionen im Original ────────────────────────────
OLD_SET = '''void set_depth_bias(int steps) { push(Op::Bias).i = steps; }
void set_overlay(bool on)      { push(Op::Overlay).i = on; }
'''

NEW_SET = '''// wots2_gs_state_dedup
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

# ── Kaputte v1-Version: statics in set_depth_bias ───────────────────────
BROKEN_V1 = '''// wots2_gs_state_dedup
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

# ── Anker 3: begin_frame-Ende, Reset der beiden statics ─────────────────
OLD_BEGIN = '''    Cmd& fog = push(Op::Fog);
    memcpy(fog.f, s_recFog, sizeof(s_recFog));
    memcpy(fog.f + 4, s_recFogColor, sizeof(s_recFogColor));
    s_recOwner = -1;
}
'''

NEW_BEGIN = '''    Cmd& fog = push(Op::Fog);
    memcpy(fog.f, s_recFog, sizeof(s_recFog));
    memcpy(fog.f + 4, s_recFogColor, sizeof(s_recFogColor));
    s_recOwner = -1;
    s_recBias = 0;              // wots2_gs_state_dedup
    s_recOverlay = false;
}
'''

def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()

    # 1. Kaputte v1-Version (statics in set_depth_bias) durch korrekte ersetzen
    if BROKEN_V1 in t:
        t = t.replace(BROKEN_V1, NEW_SET, 1)
        print('  Kaputte v1-Version korrigiert (statics aus set_depth_bias entfernt).')

    # 2. Statics im recording-state-Block einfuegen (idempotent)
    if 'static int   s_recBias = 0;' not in t:
        if ANCHOR_STATE not in t:
            print('  FEHLER: s_recBlend-Anker nicht gefunden.', file=sys.stderr)
            sys.exit(1)
        t = t.replace(ANCHOR_STATE, REPL_STATE, 1)
        print('  Statics im recording-state-Block eingefuegt.')
    else:
        print('  Statics bereits im recording-state-Block.')

    # 3. Funktionen patchen (falls noch Original)
    if OLD_SET in t:
        t = t.replace(OLD_SET, NEW_SET, 1)
        print('  set_depth_bias/set_overlay gepatcht.')
    elif NEW_SET in t:
        print('  set_depth_bias/set_overlay bereits gepatcht.')
    else:
        print('  FEHLER: weder Original noch gepatchte set_depth_bias.', file=sys.stderr)
        sys.exit(1)

    # 4. begin_frame um Reset erweitern (idempotent)
    if 's_recBias = 0;              // wots2_gs_state_dedup' not in t:
        if OLD_BEGIN not in t:
            print('  FEHLER: begin_frame-Anker nicht gefunden.', file=sys.stderr)
            sys.exit(1)
        t = t.replace(OLD_BEGIN, NEW_BEGIN, 1)
        print('  begin_frame um Reset erweitert.')
    else:
        print('  begin_frame bereits erweitert.')

    p.write_text(t)
    print('  State-Dedup fertig.')

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
