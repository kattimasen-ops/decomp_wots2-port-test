#!/usr/bin/env python3
"""
2D-Draw-Call-Batching fuer Mali-G31 (Revision v3).

Fix v2:
  - Helper wird NACH `static Frame s_cur, s_prev;` eingefuegt, nicht am
    Dateianfang (dort ist Cmd noch nicht deklariert).
  - Kein separates wots2_batch_init(): der Env-Check sitzt direkt in
    der Variable s_batchEnabled.

Fix v3:
  - Batching erlaubt jetzt auch kUvRect-Befehle. Vorher war
    `prev.flags == 0` gefordert, was jeden Sprite und jeden Font-
    Glyph vom Batching ausgeschlossen hat. Auf dem M9 bedeutete
    das einen eigenen glDrawArrays pro Zeichen.
  - Beim Zusammenfassen wird kUvRect auf dem gemergten Befehl
    entfernt: die Klausel bezog sich nur auf den ersten der beiden
    Befehle. Ein halbes Texel Bleeding an Raendern ist der Preis
    fuer deutlich weniger Draw Calls.
  - kHasZ, kFrameTex und kSpan blockieren weiterhin das Batching.

Steuerung:
  WOTS2_NO_BATCH=1   schaltet das Batching ab.

Zieldatei: src/hal/gs.cpp
Aufruf:    python3 patches/wots2-gs-batch-2d.py src/hal/gs.cpp
"""
import re
import sys
import pathlib


HELPER = '''
// ── 2D-Draw-Call-Batching (Mali-G31) ─────────────────────────────────
// wots2-gs-batch-2d.py
static bool s_batchEnabled = (getenv("WOTS2_NO_BATCH") == nullptr);
'''

MARKER = "wots2-gs-batch-2d.py"


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()

    if MARKER in t:
        print('  Batch-Helper bereits vorhanden (Marker: %s).' % MARKER)
        return

    anchor_struct = re.search(
        r'(static\s+Frame\s+s_cur\s*,\s*s_prev\s*;\s*\n)',
        t)
    if not anchor_struct:
        print('  FEHLER: s_cur-Anker nicht gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t[:anchor_struct.end()] + HELPER + t[anchor_struct.end():]

    anchor_push = re.search(
        r'static\s+Cmd&\s+push_2d\s*\(\s*GLuint\s+tex\s*,\s*Prim\s+prim\s*,\s*'
        r'u32\s+first\s*,\s*int\s+count\s*\)\s*\{',
        t)
    if not anchor_push:
        print('  FEHLER: push_2d nicht gefunden.', file=sys.stderr)
        sys.exit(1)
    push_call = t.find('Cmd& c = push(Op::Draw2D);', anchor_push.end())
    if push_call < 0:
        print('  FEHLER: push(Op::Draw2D) in push_2d nicht gefunden.',
              file=sys.stderr)
        sys.exit(1)

    batch_code = (
        '\n'
        '    // Batching-Vorprüfung: nur wenn alle Bedingungen passen.\n'
        '    // kUvRect ist ERLAUBT: die UVs liegen in den Vertex-Daten.\n'
        '    // kHasZ / kFrameTex / kSpan blockieren weiterhin.\n'
        '    if (s_batchEnabled && s_recZ == kNoZ && !s_cur.cmds.empty()\n'
        '        && tex != s_grabTex) {\n'
        '        Cmd& prev = s_cur.cmds.back();\n'
        '        if (prev.op == Op::Draw2D && prev.tex == tex\n'
        '            && prev.prim == (u8)prim\n'
        '            && (prev.flags & ~(u8)kUvRect) == 0) {\n'
        '            float _lo = 1e9f, _hi = -1e9f;\n'
        '            for (int _i = 0; _i < count; _i++) {\n'
        '                const float _x = s_cur.v2[(size_t)first + (size_t)_i].x;\n'
        '                _lo = _x < _lo ? _x : _lo;\n'
        '                _hi = _x > _hi ? _x : _hi;\n'
        '            }\n'
        '            if (!(_lo <= 0.5f && _hi >= (float)s_width - 0.5f\n'
        '                  && (tex == s_white || s_recWide))) {\n'
        '                prev.count += count;\n'
        '                prev.flags &= ~(u8)kUvRect;\n'
        '                s_recWide = false;\n'
        '                return prev;\n'
        '            }\n'
        '        }\n'
        '    }\n'
    )
    t = t[:push_call] + batch_code + t[push_call:]

    p.write_text(t)
    print('  Batch-Patch v3 fertig (kUvRect erlaubt).')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
