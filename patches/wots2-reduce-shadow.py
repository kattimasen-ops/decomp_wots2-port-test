#!/usr/bin/env python3
"""
patches/wots2-reduce-shadow.py   (v2)

Verkleinert die Schatten-Textur der Figuren in src/native/hle_chara.cpp.

hle_chara_shadow() rendert fuer jede gezeichnete Figur deren Koerper und Kopf
noch einmal in ein eigenes Render-Target (Silhouette), das danach als
Schatten auf den Boden gelegt wird. Original: 256 x 256. Auf einer
Tile-basierten Mali-GPU kostet jedes solche Target einen eigenen Render-Pass
samt Clear und Resolve, und die Flaeche geht direkt in die Kosten ein.

Der alte Patch setzte 128 fest (und lief nie, weil main() fehlte). v2 haelt
die Absicht, macht den Wert aber einstellbar:

  WOTS2_SHADOW_RES=128   Standard (hier gepatcht), vier Mal weniger Pixel
  WOTS2_SHADOW_RES=256   Originalaufloesung
  WOTS2_SHADOW_RES=64    noch gröber (Werte werden auf 32..1024 begrenzt)

Aenderungen: ein Helfer wots2_shadow_res() vor hle_chara_shadow() und der
Aufruf hal::gs::begin_target(256) wird zu begin_target(wots2_shadow_res()).
Es gibt nur diese eine begin_target-Stelle; so bleibt die Zielgroesse
konstant (ein Wechsel der Groesse wuerde das Target neu anlegen).

Idempotent: Marker 'wots2_shadow_res'.
Zieldatei: src/native/hle_chara.cpp
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wots2_patchlib as pl  # noqa: E402

MARKER = "wots2_shadow_res"

HELPER = '''// wots2_shadow_res (wots2-reduce-shadow.py)
// Kantenlaenge der Schatten-Textur. WOTS2_SHADOW_RES, Standard 128, begrenzt auf 32..1024.
static inline int wots2_shadow_res() {
    static const int res = []() -> int {
        const char* e = getenv("WOTS2_SHADOW_RES");
        const int v = (e != nullptr && *e != '\\0') ? atoi(e) : 128;
        return v < 32 ? 32 : (v > 1024 ? 1024 : v);
    }();
    return res;
}

'''

SIG = r'^void\s+hle_chara_shadow\s*\(\s*Chara\s*\*\s*c\s*,\s*float\s+strength\s*\)'
CALL = pl.flex('hal::gs::begin_target(256);')


def insertion_point(t, func_start):
    pos = func_start
    while True:
        prev_end = pos - 1
        if prev_end < 0:
            break
        prev_start = t.rfind('\n', 0, prev_end) + 1
        if t[prev_start:prev_end].lstrip().startswith('//'):
            pos = prev_start
        else:
            break
    return pos


def patch(path):
    p = pathlib.Path(path)
    if not p.exists():
        pl.fail('Zieldatei %s existiert nicht' % path)
        return
    t = p.read_text()
    if MARKER in t:
        print('  Shadow-Res bereits vorhanden (Marker: %s).' % MARKER)
        return

    hit = pl.find_function(t, SIG)
    if hit is None:
        pl.fail('hle_chara_shadow(Chara*, float) nicht gefunden')
        return
    s, b, e = hit
    body = t[b:e]
    ms = list(re.finditer(CALL, body))
    if len(ms) != 1:
        pl.fail('begin_target(256) in hle_chara_shadow: %d Treffer statt genau 1 '
                '(hat ein frueherer Patch die Zeile veraendert?)' % len(ms))
        return
    m = ms[0]
    new_body = body[:m.start()] + 'hal::gs::begin_target(wots2_shadow_res());' + body[m.end():]
    ins = insertion_point(t, s)
    t = t[:ins] + HELPER + t[ins:s] + t[s:b] + new_body + t[e:]

    if '<cstdlib>' not in t and '<stdlib.h>' not in t:
        inc = pl.last_include_end(t)
        if inc < 0:
            pl.fail('kein #include gefunden - <cstdlib> konnte nicht ergaenzt werden')
            return
        t = t[:inc] + '#include <cstdlib>\n' + t[inc:]

    p.write_text(t)
    print('  Schatten-Textur einstellbar (Standard 128, WOTS2_SHADOW_RES=256 = Original).')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/native/hle_chara.cpp'
    print('Patche %s' % target)
    patch(target)
    pl.finish()
    print('Fertig.')
