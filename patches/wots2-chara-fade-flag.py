#!/usr/bin/env python3
"""
patches/wots2-chara-fade-flag.py   (v2)

Markiert in src/native/hle_chara.cpp die 3D-Ansichten von Figuren (Koerper und
Schwert-Teile) und gibt jeder einen Blend-Faktor mit, den wots2-gs-npc-fade.py
im Shader umsetzt.

Der Faktor kommt von der CPU-Seite aus Chara::cameraDistance. Das ist
dieselbe Groesse, nach der wots2-npc-max-dist.py die NPCs abschneidet
(CharaOther_Cull). Deshalb ist die Figur genau dann ganz aufgeloest, wenn sie
nicht mehr gezeichnet wird, auch am Bildrand. (Eine Berechnung aus der
Bildtiefe waere dort zu gross und liesse einen Rest sichtbar.)

  Faktor = 1                       bei Distanz <= ENDE - LAENGE
  Faktor = (ENDE - Distanz)/LAENGE dazwischen
  Faktor = 0                       bei Distanz >= ENDE

  WOTS2_NPC_FADE_END   Standard: WOTS2_NPC_MAX_DIST - 0.5 (ohne MAX_DIST: aus)
  WOTS2_NPC_FADE_LEN   Standard: 4.0
  WOTS2_NO_NPC_FADE=1  aus

Eingriffe: ein Helfer hinter 'static u32 g_drawing', und vor jedem
begin_3d(mvp, View::Model, who_of(g_drawing, ...)) ein Komma-Ausdruck
(wots2_mark_chara(), begin_3d(...)), damit es ein einzelnes Statement bleibt.
Props (who_of((u32)matrix, ...)) und Schatten bleiben unmarkiert.

Die Variablen g_wots2_chara_* sind hier SCHWACHE Symbole: Fehlt das Gegenstueck
in gs.cpp, gibt es kein Linker-Problem und nichts passiert.

Idempotent: Marker 'wots2_mark_chara'.
Zieldatei: src/native/hle_chara.cpp
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wots2_patchlib as pl  # noqa: E402

MARKER = "wots2_mark_chara"

HELPER = '''
// wots2_mark_chara (wots2-chara-fade-flag.py v2): Gegenstueck in gs.cpp (wots2-gs-npc-fade.py)
extern "C" __attribute__((weak)) int g_wots2_chara_view;
extern "C" __attribute__((weak)) float g_wots2_chara_fade;
// Blend-Faktor 1 = voll sichtbar ... 0 = weg, aus der Kamera-Distanz der Figur.
static inline float wots2_chara_fade_factor(float dist) {
    static float end = 0.0f, len = 4.0f;
    static bool init = false;
    if (!init) {
        init = true;
        if (getenv("WOTS2_NO_NPC_FADE") == nullptr) {
            const char* m = getenv("WOTS2_NPC_MAX_DIST");
            const float maxd = m != nullptr ? (float)atof(m) : 0.0f;
            const char* e = getenv("WOTS2_NPC_FADE_END");
            end = (e != nullptr && *e != '\\0') ? (float)atof(e) : (maxd > 0.0f ? maxd - 0.5f : 0.0f);
            const char* l = getenv("WOTS2_NPC_FADE_LEN");
            len = (l != nullptr && *l != '\\0') ? (float)atof(l) : 4.0f;
            if (len < 0.5f)
                len = 0.5f;
        }
    }
    if (end <= 0.0f)
        return 1.0f;
    if (dist >= end)
        return 0.0f;
    if (dist <= end - len)
        return 1.0f;
    return (end - dist) / len;
}
static inline void wots2_mark_chara() {
    if (&g_wots2_chara_view == nullptr || &g_wots2_chara_fade == nullptr)
        return;
    const Chara* ch = g_drawing != 0 ? guest::ptr<Chara>(g_drawing) : nullptr;
    g_wots2_chara_fade = ch != nullptr ? wots2_chara_fade_factor(ch->cameraDistance) : 1.0f;
    g_wots2_chara_view = 1;
}
'''

CALL_RE = re.compile(r'hal::gs::begin_3d\s*\(\s*mvp\s*,\s*hal::gs::View::Model\s*,\s*who_of\s*\(\s*g_drawing\s*,')
DRAWING_RE = re.compile(r'^static\s+u32\s+g_drawing\s*=\s*0\s*;[^\n]*\n', re.M)


def find_call_end(t, open_paren):
    depth = 0
    i = open_paren
    n = len(t)
    while i < n:
        c = t[i]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def patch(path):
    p = pathlib.Path(path)
    if not p.exists():
        pl.fail('Zieldatei %s existiert nicht' % path)
        return
    t = p.read_text()
    if MARKER in t:
        print('  Chara-Fade-Flag bereits vorhanden.')
        return

    hits = list(CALL_RE.finditer(t))
    if len(hits) < 1:
        pl.fail('kein begin_3d(mvp, View::Model, who_of(g_drawing, ...)) gefunden')
        return
    if len(hits) > 4:
        pl.fail('%d Treffer, erwartet 1 bis 4 - zu viele, bitte pruefen' % len(hits))
        return
    md = list(DRAWING_RE.finditer(t))
    if len(md) != 1:
        pl.fail('"static u32 g_drawing = 0;" %d Treffer statt genau 1' % len(md))
        return
    if md[0].end() > hits[0].start():
        pl.fail('g_drawing wird erst nach dem ersten begin_3d-Aufruf deklariert')
        return

    for m in reversed(hits):
        start = m.start()
        paren = t.index('(', start + len('hal::gs::begin_3d') - 1)
        end = find_call_end(t, paren)
        if end < 0:
            pl.fail('Klammer des begin_3d-Aufrufs nicht abgeschlossen')
            return
        t = t[:start] + '(wots2_mark_chara(), ' + t[start:end] + ')' + t[end:]

    md = list(DRAWING_RE.finditer(t))
    t = t[:md[0].end()] + HELPER + t[md[0].end():]
    p.write_text(t)
    print('  %d Figuren-Ansichten markiert (Blend-Faktor aus cameraDistance).' % len(hits))


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/native/hle_chara.cpp'
    print('Patche %s' % target)
    patch(target)
    pl.finish()
    print('Fertig.')
