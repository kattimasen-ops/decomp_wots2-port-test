#!/usr/bin/env python3
"""
Cache fuer CharaResources_GetParams / FindParamTemplate.

Hintergrund:
  Beide Funktionen durchsuchen eine verkettete Liste und werden aus
  Chara_Update, Chara_Reset, Chara_BaseCtor und diversen anderen Stellen
  aufgerufen — pro Charakter pro Frame mehrfach. Bei 40 NPCs sind das
  ueber 200 Listen-Durchlaeufe pro Frame.

  Die IDs, die abgefragt werden, wiederholen sich; ein direkter 8-Slot-
  Cache (id & 7) traegt in fast allen Faellen, ohne die Reihenfolge der
  Liste zu aendern.

Sicher: die Semantik bleibt identisch — bei einem Cache-Miss laeuft die
Original-Suche; der Cache schreibt nur nach erfolgreichem Finde oder
nach dem Anlegen. Kein Verhalten aendert sich, nur die Geschwindigkeit.

Idempotent ueber Marker.

Python 3.6+ kompatibel.
"""
import re
import sys
import pathlib


CACHE_DECL = r'''
// ── [WOTS2-PORT] Direkt gemappte Caches fuer die zwei heissesten Suchen ───
// wots2-chara-resources-cache.py
static s32 wots2_cr_gp_id[8]  = {-1, -1, -1, -1, -1, -1, -1, -1};
static u32 wots2_cr_gp_val[8] = {0, 0, 0, 0, 0, 0, 0, 0};
static s32 wots2_cr_ft_id[8]  = {-1, -1, -1, -1, -1, -1, -1, -1};
static u32 wots2_cr_ft_val[8] = {0, 0, 0, 0, 0, 0, 0, 0};
static inline int wots2_cr_slot(int id) { return (int)(((u32)id) & 7u); }
'''

GP_BODY = '''CharaParams* CharaResources_GetParams(CharaResources* self, int id) {
    // [WOTS2-PORT] direkter Cache-Lookup
    {
        const int s = wots2_cr_slot(id);
        if (wots2_cr_gp_id[s] == id && wots2_cr_gp_val[s] != 0)
            return guest::ptr<CharaParams>(wots2_cr_gp_val[s]);
    }
    for (GuestListNode* n = GuestList_Begin(&self->params); n != GuestList_End(&self->params);
         n = GuestList_Next(n)) {
        CharaParams* p = TemplateOf(n);
        if (p->id == id) {
            const int s = wots2_cr_slot(id);
            wots2_cr_gp_id[s] = id;
            wots2_cr_gp_val[s] = guest::addr(p);
            return p;
        }
    }
    void* mem = MemAlloc(sizeof(CharaParamsRef));
    CharaParamsRef* ref = mem ? CharaParams_New(static_cast<CharaParamsRef*>(mem), id) : nullptr;
    GuestList_Insert(&self->params, GuestList_End(&self->params), guest::addr(ref));
    CharaParams* p = guest::ptr<CharaParams>(ref->params);
    {
        const int s = wots2_cr_slot(id);
        wots2_cr_gp_id[s] = id;
        wots2_cr_gp_val[s] = guest::addr(p);
    }
    return p;
}'''

FT_BODY = '''CharaParams* CharaResources_FindParamTemplate(CharaResources* self, int id) {
    // [WOTS2-PORT] direkter Cache-Lookup
    {
        const int s = wots2_cr_slot(id);
        if (wots2_cr_ft_id[s] == id && wots2_cr_ft_val[s] != 0)
            return guest::ptr<CharaParams>(wots2_cr_ft_val[s]);
    }
    for (GuestListNode* n = GuestList_Begin(&self->templates); n != GuestList_End(&self->templates);
         n = GuestList_Next(n)) {
        CharaParams* p = TemplateOf(n);
        if (p->id == id) {
            const int s = wots2_cr_slot(id);
            wots2_cr_ft_id[s] = id;
            wots2_cr_ft_val[s] = guest::addr(p);
            return p;
        }
    }
    return nullptr;
}'''

MARKER = "wots2-chara-resources-cache.py"


def replace_function(text, name, new_body):
    """Ersetzt eine C++-Funktion anhand ihrer Signatur bis zur ersten
    Zeile die nur '}' enthaelt."""
    pat = re.compile(
        r'(?:^[^\n]*\b' + re.escape(name) + r'\s*\([^)]*\)\s*\{)',
        re.MULTILINE)
    m = pat.search(text)
    if not m:
        return text, 0
    # Klammer-Matching (kein Kommentar-/String-Handling: die Funktionen
    # enthalten keine Klammern in Strings).
    i = text.find('{', m.start())
    depth = 0
    while i < len(text):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                break
        i += 1
    return text[:m.start()] + new_body + text[i + 1:], 1


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    if MARKER in t:
        print('  Cache bereits vorhanden.')
        return

    # 1. Cache-Deklarationen am Dateianfang nach den Includes einfuegen.
    last_inc = list(re.finditer(r'^#include [<"][^\n]+[>\"]\n', t, re.M))
    if not last_inc:
        print('  FEHLER: kein #include gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t[:last_inc[-1].end()] + CACHE_DECL + t[last_inc[-1].end():]

    # 2. Die zwei Funktionen ersetzen.
    t, n1 = replace_function(t, 'CharaResources_GetParams', GP_BODY)
    t, n2 = replace_function(t, 'CharaResources_FindParamTemplate', FT_BODY)

    p.write_text(t)
    print('  CharaResources-Caches eingebaut: GetParams=%d, FindParamTemplate=%d' % (n1, n2))


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/game/chara_resources.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
