#!/usr/bin/env python3
"""
patches/wots2-npc-lod-closer.py   (v2, ersetzt die alte Version)

Schwelle fuer das Fern-Modell der Figuren, jetzt einstellbar und ohne Flackern.

Chara_Draw waehlt das Modell so:
    CharaModels_Draw(self, self->cameraDistance < 12.0f ? (nah) : 2 /* Fern-LOD */);

Die alte Version setzte die 12.0 fest auf 8.0. Der Launcher setzt aber
WOTS2_NPC_LOD_DIST; diese Variable wurde nie gelesen ("derzeit wirkungslos").

v2:
  * Die Schwelle kommt aus WOTS2_NPC_LOD_DIST (Standard 8.0, 12 = Originalwert).
    ACHTUNG: Der Launcher setzt 4. Das wird mit v2 wirksam, und dann nutzen fast
    alle NPCs das Fern-Modell. Fuer wenig auffaelligen Wechsel 8 bis 10 nehmen.
  * Hysterese: Eine Figur wechselt erst zum Fern-Modell, wenn sie ueber
    Schwelle + 0,75 liegt, und zurueck erst unter Schwelle - 0,75. Dadurch
    flackert das Modell nicht hin und her, wenn eine Figur an der Grenze steht.

Idempotent: Marker 'wots2_npc_lod_v2'.
Zieldatei: src/game/chara.cpp
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wots2_patchlib as pl  # noqa: E402

MARKER = "wots2_npc_lod_v2"

HELPER = '''// wots2_npc_lod_v2 (wots2-npc-lod-closer.py)
// Schwelle fuer das Fern-Modell (Standard 8.0, WOTS2_NPC_LOD_DIST, 12 = Original).
static inline float wots2_lod_dist() {
    static const float d = []() -> float {
        const char* e = getenv("WOTS2_NPC_LOD_DIST");
        const float v = (e != nullptr && *e != '\\0') ? (float)atof(e) : 8.0f;
        return v > 0.5f ? v : 8.0f;
    }();
    return d;
}
// Nah oder fern, mit Hysterese (+-0,75), pro Figur gemerkt.
static inline bool wots2_lod_near(const Chara* self) {
    static std::unordered_map<const Chara*, bool> state;
    const float d = wots2_lod_dist();
    const float dist = self->cameraDistance;
    bool& nearFlag = state.emplace(self, dist < d).first->second;
    if (nearFlag) {
        if (dist >= d + 0.75f)
            nearFlag = false;
    } else if (dist < d - 0.75f) {
        nearFlag = true;
    }
    return nearFlag;
}

'''

SIG = (r'^static\s+int\s+Chara_Draw\s*\(\s*Chara\s*\*\s*self\s*,\s*int\s+shown\s*,'
       r'\s*const\s+float\s*\*\s*wind\s*\)')
COND = pl.flex('self->cameraDistance < 12.0f')


def patch(path):
    p = pathlib.Path(path)
    if not p.exists():
        pl.fail('Zieldatei %s existiert nicht' % path)
        return
    t = p.read_text()
    if MARKER in t:
        print('  NPC-LOD bereits vorhanden (Marker: %s).' % MARKER)
        return

    hit = pl.find_function(t, SIG)
    if hit is None:
        pl.fail('Chara_Draw nicht gefunden')
        return
    s, b, e = hit
    body = t[b:e]
    ms = list(re.finditer(COND, body))
    if len(ms) != 1:
        pl.fail('"self->cameraDistance < 12.0f" in Chara_Draw: %d Treffer statt genau 1 '
                '(hat ein anderer Patch die Schwelle schon geaendert?)' % len(ms))
        return
    m = ms[0]
    new_body = body[:m.start()] + 'wots2_lod_near(self)' + body[m.end():]

    ins = s
    while True:
        prev_end = ins - 1
        if prev_end < 0:
            break
        prev_start = t.rfind('\n', 0, prev_end) + 1
        if t[prev_start:prev_end].lstrip().startswith('//'):
            ins = prev_start
        else:
            break
    t = t[:ins] + HELPER + t[ins:s] + t[s:b] + new_body + t[e:]

    if '<unordered_map>' not in t:
        inc = pl.last_include_end(t)
        if inc < 0:
            pl.fail('kein #include gefunden - <unordered_map> konnte nicht ergaenzt werden')
            return
        t = t[:inc] + '#include <unordered_map>\n' + t[inc:]
    p.write_text(t)
    print('  NPC-LOD-Schwelle einstellbar (Standard 8.0, mit Hysterese).')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/game/chara.cpp'
    print('Patche %s' % target)
    patch(target)
    pl.finish()
    print('Fertig.')
