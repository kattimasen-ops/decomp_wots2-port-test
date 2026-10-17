#!/usr/bin/env python3
"""WOTS2 NPC simulation-distance patch.

Skips simulation (CharaMgr_Update, StepA..D, StepMap) for NPCs farther away
than WOTS2_NPC_SIM_DIST (default 0 = off; recommended 40).

Not affected:
  - the player (id 0)
  - NPCs the player is locked on to (CharaBody::targetFlags & 0x1000000)
  - NPCs closer than WOTS2_NPC_SIM_DIST
  - collision (CharaMgr_StepFlags), so a hit still registers

Rollback: WOTS2_NPC_SIM_DIST=0 (or unset).

Idempotent: marker `wots2_npc_sim_distance_v1`.
"""

import os
import re
import sys

MARKER = "wots2_npc_sim_distance_v1"

HELPER = r"""// [WOTS2-PORT] wots2_npc_sim_distance_v1
// Ferne NPCs (cameraDistance > WOTS2_NPC_SIM_DIST) werden in Update/StepA..D/
// StepMap uebersprungen. Default 0 = aus. Werte < 5 sind ungueltig (zu nah).
// Spieler (id 0) und gelockte Gegner (targetFlags & 0x1000000) laufen immer.
static bool wots2_npc_sim_skip(Chara* c) {
    static const float s_dist = []() {
        const char* e = getenv("WOTS2_NPC_SIM_DIST");
        float v = e ? (float)atof(e) : 0.0f;
        return v < 5.0f ? 0.0f : v;
    }();
    if (s_dist <= 0.0f) return false;
    if (c->id == 0) return false;
    if (c->cameraDistance < s_dist) return false;
    if ((Body(c)->targetFlags & 0x1000000u) != 0) return false;
    return true;
}

"""


def patch_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    if MARKER in text:
        print("  bereits gepatcht (wots2_npc_sim_distance_v1)")
        return True

    # 1) cstdlib fuer getenv/atof
    if "#include <cstdlib>" not in text:
        if "#include <cstring>" in text:
            text = text.replace("#include <cstring>",
                                "#include <cstring>\n#include <cstdlib>", 1)
        else:
            print("  WARNUNG: <cstring> nicht gefunden, cstdlib-Include uebersprungen.")

    # 2) Helper einfuegen, direkt vor CharaMgr_Ctor.
    ctor_anchor = "CharaMgr* CharaMgr_Ctor(void* mem) {"
    if ctor_anchor not in text:
        print("  FEHLER: Anker 'CharaMgr_Ctor' nicht gefunden.")
        return False
    text = text.replace(ctor_anchor, HELPER + ctor_anchor, 1)

    # 3) Step-Loops patchen (pro spezifischem Call-Aufruf).
    patches = [
        ("kCharaUpdate",
         r"(EACH_CHARA\(mgr, c\)\r?\n        if \(c->active != 0\)\r?\n            VirtualCall<void, Chara\*>\(c->vtable, kCharaUpdate, c\);)",
         r"EACH_CHARA(mgr, c)\n        if (c->active != 0 && !wots2_npc_sim_skip(c))\n            VirtualCall<void, Chara*>(c->vtable, kCharaUpdate, c);"),
        ("kCharaStepA",
         r"(EACH_CHARA\(mgr, c\)\r?\n        if \(c->active != 0\)\r?\n            VirtualCall<void, Chara\*>\(c->vtable, kCharaStepA, c\);)",
         r"EACH_CHARA(mgr, c)\n        if (c->active != 0 && !wots2_npc_sim_skip(c))\n            VirtualCall<void, Chara*>(c->vtable, kCharaStepA, c);"),
        ("kCharaStepB",
         r"(EACH_CHARA\(mgr, c\)\r?\n        if \(c->active != 0\)\r?\n            VirtualCall<void, Chara\*>\(c->vtable, kCharaStepB, c\);)",
         r"EACH_CHARA(mgr, c)\n        if (c->active != 0 && !wots2_npc_sim_skip(c))\n            VirtualCall<void, Chara*>(c->vtable, kCharaStepB, c);"),
        ("Chara_fn1cccf0",
         r"(EACH_CHARA\(mgr, c\)\r?\n        if \(c->active != 0\)\r?\n            Chara_fn1cccf0\(c\);)",
         r"EACH_CHARA(mgr, c)\n        if (c->active != 0 && !wots2_npc_sim_skip(c))\n            Chara_fn1cccf0(c);"),
        ("kCharaStepC",
         r"(EACH_CHARA\(mgr, c\)\r?\n        if \(c->active != 0\)\r?\n            VirtualCall<void, Chara\*>\(c->vtable, kCharaStepC, c\);)",
         r"EACH_CHARA(mgr, c)\n        if (c->active != 0 && !wots2_npc_sim_skip(c))\n            VirtualCall<void, Chara*>(c->vtable, kCharaStepC, c);"),
        ("kCharaStepD",
         r"(EACH_CHARA\(mgr, c\)\r?\n        if \(c->active != 0\)\r?\n            VirtualCall<void, Chara\*>\(c->vtable, kCharaStepD, c\);)",
         r"EACH_CHARA(mgr, c)\n        if (c->active != 0 && !wots2_npc_sim_skip(c))\n            VirtualCall<void, Chara*>(c->vtable, kCharaStepD, c);"),
    ]

    count = 0
    for name, pattern, replacement in patches:
        text, n = re.subn(pattern, replacement, text, count=1)
        if n == 1:
            count += 1
        else:
            print(f"  WARNUNG: {name} nicht gefunden.")
    if count == 0:
        print("  FEHLER: keine Step-Loop gepatcht.")
        return False

    # 4) StepMap: skip, bevor visible gesetzt wird.
    sm_pattern = (
        r"(EACH_CHARA\(mgr, c\) \{\r?\n"
        r"        if \(c->active == 0\)\r?\n"
        r"            continue;\r?\n"
        r"        c->visible = 1;)"
    )
    sm_replacement = (
        r"EACH_CHARA(mgr, c) {\n"
        r"        if (c->active == 0)\n"
        r"            continue;\n"
        r"        if (wots2_npc_sim_skip(c))\n"
        r"            continue;\n"
        r"        c->visible = 1;"
    )
    text, n = re.subn(sm_pattern, sm_replacement, text, count=1)
    if n == 1:
        count += 1
    else:
        print("  WARNUNG: StepMap-Anker nicht gefunden.")

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  {count} Einbau-Stellen gepatcht.")
    return True


def main():
    if len(sys.argv) < 2:
        print("Aufruf: wots2-npc-sim-distance.py <repo-root-oder-chara_mgr.cpp>", file=sys.stderr)
        sys.exit(2)
    arg = sys.argv[1]
    path = arg if arg.endswith(".cpp") else os.path.join(arg, "src", "game", "chara_mgr.cpp")
    if not os.path.isfile(path):
        print(f"FEHLER: {path} nicht gefunden.", file=sys.stderr)
        sys.exit(1)
    print(f"Patche {path}")
    ok = patch_file(path)
    print("Fertig." if ok else "Fertig mit Fehlern.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
