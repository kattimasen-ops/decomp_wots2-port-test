#!/usr/bin/env python3
import sys
from pathlib import Path

PATH   = Path("src/native/hle_tasks.cpp")
MARKER = "/* WOTS2_CANSEE_CACHE */"

OLD_START = """int Collision_CanSee(int idA, int idB, int) {
    CharaMgr* charas = P<CharaMgr>(*P<u32>(0x2EE5C4u));"""

NEW_START = """int Collision_CanSee(int idA, int idB, int) {
    /* WOTS2_CANSEE_CACHE */
    static std::map<std::pair<int, int>, int> cache;
    static int lastFrame = -1;
    if (lastFrame != hal::gs::frame_count()) { cache.clear(); lastFrame = hal::gs::frame_count(); }
    auto key = std::make_pair(idA, idB);
    auto it = cache.find(key);
    if (it != cache.end()) return it->second;

    CharaMgr* charas = P<CharaMgr>(*P<u32>(0x2EE5C4u));"""

OLD_END = """    return Map_LineBlocked(map, CharaMgr_GetPosition(charas, idA), CharaMgr_GetPosition(charas, idB), 0) == nullptr;
}"""

NEW_END = """    int result = Map_LineBlocked(map, CharaMgr_GetPosition(charas, idA), CharaMgr_GetPosition(charas, idB), 0) == nullptr;
    cache[key] = result;
    return result;
}"""

def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)

def main():
    if not PATH.exists(): fail(f"{PATH} not found")
    src = PATH.read_text()
    if MARKER in src: return

    if src.count(OLD_START) != 1: fail("Start anchor missing")
    if src.count(OLD_END) != 1: fail("End anchor missing")

    # add includes
    if '#include "hal/gs.h"' not in src:
        src = src.replace('#include "native/hle.h"', '#include "native/hle.h"\n#include "hal/gs.h"\n#include <map>')

    src = src.replace(OLD_START, NEW_START, 1)
    src = src.replace(OLD_END, NEW_END, 1)
    PATH.write_text(src)
