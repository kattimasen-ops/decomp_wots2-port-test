#!/usr/bin/env python3
"""WOTS2 NPC simulation-distance patch (v2).

Skips simulation (CharaMgr_Update, StepA..D, StepMap) for NPCs farther than
WOTS2_NPC_SIM_DIST (default 0 = off; recommended 40) from the PLAYER.

v2 fixes the v1 bug where the check used c->cameraDistance, which is set by
CharaMgr_StepMap — one of the skipped functions. Stale cameraDistance froze
NPCs permanently: they never woke up as the player approached.

v2 uses the player's position directly, cached once per frame from the
player's CharaParams matrix (the player is id 0 and is never skipped).

Not affected:
  - the player (id 0)
  - NPCs the player is locked on to (CharaBody::targetFlags & 0x1000000)
  - NPCs closer than WOTS2_NPC_SIM_DIST to the player
  - collision (CharaMgr_StepFlags), so a hit still registers

Rollback: WOTS2_NPC_SIM_DIST=0 (or unset).

Idempotent: marker `wots2_npc_sim_distance_v2`.
"""

import os
import re
import sys

MARKER = "wots2_npc_sim_distance_v2"

HELPER = r"""// [WOTS2-PORT] wots2_npc_sim_distance_v2
// Ferne NPCs (> WOTS2_NPC_SIM_DIST Units vom Spieler) werden in Update/
// StepA..D/StepMap uebersprungen. Default 0 = aus; empfohlen 40.
// Gemessen wird die Distanz zum SPIELER, nicht zur Kamera: die Kamera-
// Distanz (c->cameraDistance) wird in CharaMgr_StepMap gesetzt, und die
// wird hier uebersprungen — mit c->cameraDistance als Schwelle bleibt der
// NPC ewig eingefroren und unsichtbar, egal wie nah der Spieler kommt.
// Der Spieler (id 0) ist nie eingefroren; seine Position matrix[12..14]
// ist damit immer frisch und dient als Bezugspunkt.
// Gelockte Gegner (targetFlags & 0x1000000) laufen immer.
static float s_wots2_player_x = 0.0f;
static float s_wots2_player_y = 0.0f;
static float s_wots2_player_z = 0.0f;

static inline void wots2_npc_cache_player(Chara* c) {
    if (c == nullptr || c->id != 0 || c->params == 0) return;
    const CharaParams* p = guest::ptr<CharaParams>(c->params);
    s_wots2_player_x = p->matrix[12];
    s_wots2_player_y = p->matrix[13];
    s_wots2_player_z = p->matrix[14];
}

static bool wots2_npc_sim_skip(Chara* c) {
    static const float s_dist = []() {
        const char* e = getenv("WOTS2_NPC_SIM_DIST");
        float v = e ? (float)atof(e) : 0.0f;
        return v < 5.0f ? 0.0f : v;
    }();
    if (s_dist <= 0.0f) return false;
    if (c == nullptr || c->id == 0) return false;
    if (c->params == 0) return false;
    if ((Body(c)->targetFlags & 0x1000000u) != 0) return false;
    const CharaParams* p = guest::ptr<CharaParams>(c->params);
    const float dx = p->matrix[12] - s_wots2_player_x;
    const float dy = p->matrix[13] - s_wots2_player_y;
    const float dz = p->matrix[14] - s_wots2_player_z;
    const float d2 = dx * dx + dy * dy + dz * dz;
    return d2 > s_dist * s_dist;
}

"""


def patch_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    if MARKER in text:
        print("  bereits gepatcht (v2)")
        return True

    # Wenn v1 schon drin ist: seinen Helper-Block durch v2 ersetzen.
    if "wots2_npc_sim_distance_v1" in text:
        v1_pattern = re.compile(
            r"// \[WOTS2-PORT\] wots2_npc_sim_distance_v1.*?\n"
            r"static bool wots2_npc_sim_skip\(Chara\* c\) \{.*?\n\}\n",
            re.DOTALL,
        )
        if not v1_pattern.search(text):
            print("  FEHLER: v1-Helper-Block nicht gefunden (Marker da, Body unerwartet).")
            return False
        text = v1_pattern.sub(HELPER, text, count=1)
        print("  v1-Helper durch v2 ersetzt.")
    else:
        # Frischer Einbau: cstdlib sicherstellen und Helper vor CharaMgr_Ctor setzen.
        if "#include <cstdlib>" not in text:
            if "#include <cstring>" in text:
                text = text.replace("#include <cstring>",
                                    "#include <cstring>\n#include <cstdlib>", 1)
        ctor_anchor = "CharaMgr* CharaMgr_Ctor(void* mem) {"
        if ctor_anchor not in text:
            print("  FEHLER: Anker 'CharaMgr_Ctor' nicht gefunden.")
            return False
        text = text.replace(ctor_anchor, HELPER + ctor_anchor, 1)
        # Step-Loops patchen.
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
        applied = 0
        for name, pattern, replacement in patches:
            text, n = re.subn(pattern, replacement, text, count=1)
            if n == 1:
                applied += 1
            else:
                print(f"  WARNUNG: {name} nicht gefunden.")
        if applied == 0:
            print("  FEHLER: keine Step-Loop gepatcht.")
            return False
        print(f"  {applied} Step-Loop(s) gepatcht.")

        # StepMap patchen (wird oft nicht gefunden — der Anker variiert).
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
            print("  StepMap gepatcht.")
        else:
            print("  WARNUNG: StepMap-Anker nicht gefunden.")

    # Update-Loop um den Player-Cache erweitern.
    update_old = re.compile(
        r"EACH_CHARA\(mgr, c\)\r?\n"
        r"        if \(c->active != 0 && !wots2_npc_sim_skip\(c\)\)\r?\n"
        r"            VirtualCall<void, Chara\*>\(c->vtable, kCharaUpdate, c\);"
    )
    update_new = (
        "EACH_CHARA(mgr, c) {\n"
        "        if (c->id == 0)\n"
        "            wots2_npc_cache_player(c);\n"
        "        if (c->active != 0 && !wots2_npc_sim_skip(c))\n"
        "            VirtualCall<void, Chara*>(c->vtable, kCharaUpdate, c);\n"
        "    }"
    )
    text, n = re.subn(update_old, update_new, text, count=1)
    if n != 1:
        print("  FEHLER: Update-Loop nicht gefunden (Player-Cache konnte nicht eingebaut werden).")
        return False
    print("  Player-Cache in Update-Loop eingebaut.")

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
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
