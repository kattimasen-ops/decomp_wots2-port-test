#!/usr/bin/env python3
"""
patches/wots2-gs-no-mipmap.py   (v2)

Macht das Mipmap-Sampling in src/hal/gs.cpp zur Laufzeit abschaltbar.

Der alte Patch schrieb GL_LINEAR fest in den Code. Ob das auf dem RK3326
schneller ist, ist unklar: Mipmaps sparen bei verkleinerten Texturen oft
Texturbandbreite. Deshalb jetzt ein Schalter, mit dem du ohne neuen Build
A/B-testen kannst:

  WOTS2_NO_MIPMAP=1   nur GL_LINEAR (kein Mipmap-Sampling)
  nicht gesetzt / 0   Originalverhalten

Gepatcht wird die Zeile
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER,
                  count > 1 ? GL_LINEAR_MIPMAP_LINEAR : GL_LINEAR);

Idempotent: Marker 'wots2_gs_no_mipmap_v2'.
Zieldatei: src/hal/gs.cpp
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wots2_patchlib as pl  # noqa: E402

MARKER = "wots2_gs_no_mipmap_v2"

HELPER = '''
// wots2_gs_no_mipmap_v2 (wots2-gs-no-mipmap.py)
#include <cstdlib>
static inline bool wots2_no_mipmap() {
    static const bool v = []() -> bool {
        const char* e = getenv("WOTS2_NO_MIPMAP");
        return e != nullptr && *e != '\\0' && *e != '0';
    }();
    return v;
}
'''

PAT = re.compile(
    r'(GL_TEXTURE_MIN_FILTER\s*,\s*)'
    r'count\s*>\s*1\s*\?\s*GL_LINEAR_MIPMAP_LINEAR\s*:\s*GL_LINEAR')


def patch(path):
    p = pathlib.Path(path)
    if not p.exists():
        pl.fail('Zieldatei %s existiert nicht' % path)
        return
    t = p.read_text()
    if MARKER in t:
        print('  No-Mipmap bereits vorhanden (Marker: %s).' % MARKER)
        return

    hits = list(PAT.finditer(t))
    if len(hits) != 1:
        pl.fail('MIN_FILTER-Zeile: %d Treffer statt genau 1 '
                '(geaendert durch wots2-gs-tex-storage.py o. a.?)' % len(hits))
        return

    ins = pl.last_include_end(t)
    if ins < 0:
        pl.fail('kein #include gefunden')
        return

    m = hits[0]
    new_line = (m.group(1) +
                '(count > 1 && !wots2_no_mipmap()) ? GL_LINEAR_MIPMAP_LINEAR : GL_LINEAR')
    t = t[:m.start()] + new_line + t[m.end():]
    ins = pl.last_include_end(t)            # Position ist unveraendert, sicherheitshalber
    t = t[:ins] + HELPER + t[ins:]
    p.write_text(t)
    print('  No-Mipmap-Schalter eingebaut (WOTS2_NO_MIPMAP=1 schaltet Mipmaps ab).')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    pl.finish()
    print('Fertig.')
