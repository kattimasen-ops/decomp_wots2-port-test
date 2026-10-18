#!/usr/bin/env python3
"""
patches/wots2-collision-cache.py   (v2)

Pro Frame nur einmal berechnen, ob Figur A Figur B sehen kann
(Collision_CanSee in src/native/hle_tasks.cpp). Die Sichtlinie fragt die
Karten-Kollision ab (Map_LineBlocked) und wird von der KI oft mehrfach mit
denselben Figuren-IDs aufgerufen.

v2 statt v1: Der alte Patch schrieb den Cache in den Rumpf der Funktion und
brauchte zwei Anker (Anfang UND Ende), dazu einen Include-Austausch, der nur
bei '#include "native/hle.h"' wirkte. Jetzt wird die Originalfunktion
unveraendert in wots2_CanSee_uncached umbenannt (static) und dahinter eine
neue Collision_CanSee mit Cache definiert. Der Funktionsname fuer GUEST_BIND/
Tabellen bleibt gleich.

Hinweise:
  * Der Cache gilt pro angezeigtem Frame (hal::gs::frame_count()). Laufen im
    selben Anzeigeframe zwei Logikschritte (Fixed-Timestep), kann der zweite
    das Ergebnis des ersten wiederverwenden. Positionen unterscheiden sich
    dann um einen Logikschritt.
  * Notausschalter: WOTS2_NO_CANSEE_CACHE=1

Idempotent: Marker 'wots2_cansee_cache_v2'.
Zieldatei: src/native/hle_tasks.cpp
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wots2_patchlib as pl  # noqa: E402

MARKER = "wots2_cansee_cache_v2"

SIG = r'^int\s+Collision_CanSee\s*\(\s*int\s+idA\s*,\s*int\s+idB\s*,\s*int\s*\w*\s*\)'

WRAPPER = '''

// wots2_cansee_cache_v2 (wots2-collision-cache.py)
int Collision_CanSee(int idA, int idB, int unused) {
    static const bool off = (getenv("WOTS2_NO_CANSEE_CACHE") != nullptr);
    if (off)
        return wots2_CanSee_uncached(idA, idB, unused);
    static int lastFrame = -1;
    static std::unordered_map<uint64_t, int> cache;
    const int frame = hal::gs::frame_count();
    if (frame != lastFrame) {
        cache.clear();
        lastFrame = frame;
    }
    const uint64_t key = ((uint64_t)(uint32_t)idA << 32) | (uint64_t)(uint32_t)idB;
    const auto it = cache.find(key);
    if (it != cache.end())
        return it->second;
    const int result = wots2_CanSee_uncached(idA, idB, unused);
    cache.emplace(key, result);
    return result;
}
'''


def patch(path):
    p = pathlib.Path(path)
    if not p.exists():
        pl.fail('Zieldatei %s existiert nicht' % path)
        return
    t = p.read_text()
    if MARKER in t:
        print('  CanSee-Cache bereits vorhanden (Marker: %s).' % MARKER)
        return

    hit = pl.find_function(t, SIG)
    if hit is None:
        pl.fail('Collision_CanSee(int, int, int) nicht gefunden (Signatur geaendert?)')
        return
    s, b, e = hit
    body = t[b:e]
    if 'Map_LineBlocked' not in body:
        pl.fail('Collision_CanSee: Rumpf ohne Map_LineBlocked - falsche Funktion?')
        return

    # 1. Original umbenennen und static machen
    head = t[s:b]
    new_head = re.sub(r'\bCollision_CanSee\b', 'wots2_CanSee_uncached', head, count=1)
    new_head = re.sub(r'^int\b', 'static int', new_head, count=1)
    t = t[:s] + new_head + body + WRAPPER + t[e:]

    # 2. Includes (hinter dem Include-Block am Dateianfang)
    extra = ''
    if '"hal/gs.h"' not in t:
        extra += '#include "hal/gs.h"\n'
    for inc in ('<unordered_map>', '<cstdint>', '<cstdlib>'):
        if inc not in t:
            extra += '#include %s\n' % inc
    if extra:
        ins = pl.last_include_end(t)
        if ins < 0:
            pl.fail('kein #include gefunden - Includes konnten nicht ergaenzt werden')
            return
        t = t[:ins] + extra + t[ins:]

    p.write_text(t)
    print('  CanSee-Cache eingebaut (Original -> wots2_CanSee_uncached, Wrapper mit Frame-Cache).')
    print('  Notausschalter: WOTS2_NO_CANSEE_CACHE=1')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/native/hle_tasks.cpp'
    print('Patche %s' % target)
    patch(target)
    pl.finish()
    print('Fertig.')
