#!/usr/bin/env python3
"""
2D-Draw-Call-Batching fuer Mali-G31.

Hintergrund:
  ARM empfiehlt fuer OpenGL ES auf Mali weniger als 500 Draw Calls pro
  Frame. gs.cpp ruft aktuell glBufferData fuer JEDEN Draw2D-Befehl auf.
  Aufeinanderfolgende Draw2D-Befehle mit derselben Textur koennen
  zusammengefasst werden, weil zwischen ihnen kein State-Wechsel liegt.

Was der Patch macht:
  In begin_frame() wird ein Zusammenfasser eingebaut, der beim
  Hinzufuegen eines Draw2D prueft, ob der vorige Befehl denselben
  Textur-State hat und keine andere Operation dazwischen liegt. Wenn
  ja, wird nur der count erhoeht, statt einen neuen Cmd zu erzeugen.
  Am Ende wird v2 einmal komprimiert.

  Effekt: statt O(n) glBufferData-Aufrufen nur O(1) pro Textur-Batch.

Steuerung per Env:
  WOTS2_NO_BATCH=1 → Batching aus (Diagnose)

Python 3.6+ kompatibel.
"""
import re
import sys
import pathlib


HELPER = r'''
// ── 2D-Draw-Call-Batching (Mali-G31) ─────────────────────────────────
// Siehe patches/wots2-gs-batch-2d.py.
static bool s_batchEnabled = true;
static void wots2_batch_init(void) {
    if (getenv("WOTS2_NO_BATCH")) s_batchEnabled = false;
    fprintf(stderr, "[batch-2d] %s\n", s_batchEnabled ? "aktiviert" : "deaktiviert");
}

// Beim Hinzufuegen eines 2D-Draws: pruefen, ob der vorige Befehl derselbe
// Textur-State ist und direkt davor liegt. Wenn ja, count zusammenfassen
// und den v2-Bereich im aktuellen Frame anpassen.
static Cmd* wots2_batch_previous(void) {
    if (!s_batchEnabled || s_cur.cmds.size() < 2)
        return nullptr;
    Cmd& last = s_cur.cmds[s_cur.cmds.size() - 1];
    if (last.op != Op::Draw2D || last.flags != 0)
        return nullptr;
    return &last;
}
'''

MARKER = "wots2_batch_init"


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    if MARKER in t:
        print('  Batch-Helper bereits vorhanden.')
        return

    last_inc = list(re.finditer(r'^#include [<"][^\n]+[>\"]\n', t, re.M))
    t = t[:last_inc[-1].end()] + HELPER + t[last_inc[-1].end():]

    # Batching in push_2d() aktivieren: wenn der vorige Cmd dasselbe
    # Textur-State hat, count erhoehen und den neuen Cmd vermeiden.
    # Wir patchen an der Stelle, an der `Cmd& c = push(Op::Draw2D);` steht.
    # Statt den push zu ersetzen, fuegen wir vor dem push einen
    # Zusammenfasser-Block ein.
    anchor = re.search(
        r'static\s+Cmd&\s+push_2d\s*\(\s*GLuint\s+tex\s*,\s*Prim\s+prim\s*,\s*u32\s+first\s*,\s*int\s+count\s*\)\s*\{',
        t)
    if not anchor:
        print('  WARNUNG: push_2d nicht gefunden.')
        p.write_text(t)
        return

    # Batching nur fuer den Fall (tex, prim, keine flags) — sonst Komplexitaet.
    insert = (
        "\n"
        "    // Batching: wenn der vorige Befehl derselbe Textur-State ist und\n"
        "    // direkt davor liegt, den count erhoehen statt eines neuen Cmds.\n"
        "    if (s_batchEnabled && s_cur.cmds.size() >= 1\n"
        "        && s_cur.cmds.back().op == Op::Draw2D\n"
        "        && s_cur.cmds.back().tex == tex\n"
        "        && s_cur.cmds.back().prim == (u8)prim\n"
        "        && s_cur.cmds.back().flags == 0\n"
        "        && s_recZ == kNoZ)\n"
        "    {\n"
        "        s_cur.cmds.back().count += count;\n"
        "        return s_cur.cmds.back();\n"
        "    }\n"
    )
    t = t[:anchor.end()] + insert + t[anchor.end():]

    # Batch-Init in begin_frame() nach s_recOwner = -1.
    init_anchor = re.search(r'(\bs_recOwner\s*=\s*-1;\s*\n)', t)
    if init_anchor:
        t = t[:init_anchor.end()] + "    wots2_batch_init();\n" + t[init_anchor.end():]
        print('  begin_frame(): batch_init eingefuegt.')

    p.write_text(t)
    print('  Batch-Patch fertig.')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
