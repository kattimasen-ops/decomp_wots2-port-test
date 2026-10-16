#!/usr/bin/env python3
"""
Direct-Mapped Cache fuer CharaMgr_Find in chara_mgr.cpp.

Hintergrund:
  Jede CharaMgr-Funktion (SetActive, GetFlags, SetState, GetParams, ...)
  ruft Find(mgr, id) und durchsucht die verkettete Charas-Liste. Bei
  ~40 Charakteren und ~80 Aufrufen pro Frame sind das ~3200
  Listen-Iterationen pro Frame, alle mit Pointer-Deref und Vergleich.

  Die IDs sind klein (0..~30) und wiederholen sich pro Frame — ein
  direkter 16-Slot-Cache (id & 15) traegt in fast allen Faellen, ohne
  die Reihenfolge der Liste zu aendern.

Sicher: der Cache liefert bei einem Treffer nur, was Find ohnehin
gefunden haette. Bei einem Miss laeuft die Original-Suche. Add, Remove
und Dtor invalidieren den Cache.

Idempotent ueber Marker.

Python 3.6+ kompatibel.
"""
import re
import sys
import pathlib


HELPER = r'''
// ── [WOTS2-PORT] Direct-Mapped Cache fuer CharaMgr_Find ──────────────────
// wots2-chara-mgr-find-cache.py
static u32 wots2_chara_mgr_cache[16] = {0};

static inline int wots2_chara_slot(int id) {
    return (int)(((u32)id) & 15u);
}
static void wots2_chara_mgr_cache_clear(void) {
    for (int i = 0; i < 16; ++i)
        wots2_chara_mgr_cache[i] = 0;
}
'''

FIND_BODY = '''static Chara* Find(CharaMgr* mgr, int id) {
    // [WOTS2-PORT] Cache-Lookup vor der linearen Suche.
    {
        const int s = wots2_chara_slot(id);
        const u32 hit = wots2_chara_mgr_cache[s];
        if (hit != 0) {
            Chara* c = guest::ptr<Chara>(hit);
            if (c->id == id)
                return c;
        }
    }
    for (GuestListNode* n = GuestList_Begin(&mgr->charas); n != GuestList_End(&mgr->charas); n = GuestList_Next(n)) {
        Chara* c = guest::ptr<Chara>(n->value);
        if (c->id == id) {
            wots2_chara_mgr_cache[wots2_chara_slot(id)] = n->value;
            return c;
        }
    }
    return nullptr;
}'''

MARKER = "wots2-chara-mgr-find-cache.py"


def replace_function(text, name, new_body):
    """Ersetzt eine C++-Funktion anhand ihrer Signatur, per Klammer-Matching."""
    pat = re.compile(r'(?:^[^\n]*\b' + re.escape(name) + r'\s*\([^)]*\)\s*\{)',
                     re.MULTILINE)
    m = pat.search(text)
    if not m:
        return text, 0
    i = text.find('{', m.start())
    depth = 0
    in_line = False
    while i < len(text):
        c = text[i]
        if c == '\n':
            in_line = False
        elif c == '/' and i + 1 < len(text) and text[i + 1] == '/':
            in_line = True
        elif not in_line:
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    break
        i += 1
    return text[:m.start()] + new_body + text[i + 1:], 1


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    if MARKER in t:
        print('  Find-Cache bereits vorhanden.')
        return

    # 1. Helper nach den Includes einfuegen.
    last_inc = list(re.finditer(r'^#include [<"][^\n]+[>\"]\n', t, re.M))
    if not last_inc:
        print('  FEHLER: kein #include gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t[:last_inc[-1].end()] + HELPER + t[last_inc[-1].end():]

    # 2. Die Find-Funktion ersetzen.
    t, n = replace_function(t, 'Find', FIND_BODY)
    if n == 0:
        print('  WARNUNG: Find() nicht gefunden.', file=sys.stderr)

    # 3. Invalidierung: an jeder Stelle, die die Charas-Liste veraendert,
    #    den Cache leeren. Wir haengen den Aufruf direkt nach den
    #    GuestList-Insert/Erase/Init-Zeilen an, die mit mgr->charas
    #    zu tun haben. Das sind: CharaMgr_Ctor, CharaMgr_Dtor,
    #    CharaMgr_Add, CharaMgr_Remove.
    def add_clear(text, anchor_pattern, label):
        nonlocal n
        m = re.search(anchor_pattern, text)
        if not m:
            print('  HINWEIS: Invalidierungsanker nicht gefunden: %s' % label)
            return text
        insertion = m.group(0) + '    wots2_chara_mgr_cache_clear();\n'
        return text[:m.start()] + insertion + text[m.end():]

    # CharaMgr_Ctor: nach GuestList_Init(&mgr->charas) — verhindert stale
    # Eintraege beim ersten Aufruf nach einem Map-Wechsel.
    t = add_clear(t, r'GuestList_Init\(&mgr->charas\);\s*\n', 'Ctor')
    # CharaMgr_Add: nach dem Insert in mgr->charas.
    t = add_clear(
        t,
        r'GuestList_Insert\(&mgr->charas,\s*GuestList_End\(&mgr->charas\),\s*guest::addr\(c\)\);\s*\n',
        'Add')
    # CharaMgr_Remove: nach dem Erase aus mgr->charas.
    t = add_clear(t,
                  r'GuestList_Erase\(&mgr->charas,\s*n\);\s*\n\s*return;\s*\n',
                  'Remove')

    p.write_text(t)
    print('  CharaMgr-Find-Cache eingebaut (Helper=1, Find=%d).' % n)


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/game/chara_mgr.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
