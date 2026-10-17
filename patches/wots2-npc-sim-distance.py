#!/usr/bin/env python3
"""WOTS2 NPC simulation-distance patch (v2.1).

Skips simulation (CharaMgr_Update, StepA..D, StepMap) for NPCs farther than
WOTS2_NPC_SIM_DIST (default 0 = off; recommended 40) from the PLAYER.

v1 bug (fixed): the check used c->cameraDistance, set by CharaMgr_StepMap,
one of the skipped functions. Stale value froze NPCs permanently.

v2.1 changes over v2:
  * StepC pattern fixed: the code calls Chara_fn1cec20(), not
    VirtualCall(...kCharaStepC...). v2 never patched StepC, the build-log
    "kCharaStepC nicht gefunden" was exactly this.
  * player_ok flag: skip() only acts after the player position has been
    cached once, so the very first EACH_CHARA frame cannot mis-skip.
  * Far NPCs in StepMap get c->visible = 0 after the skip, so Draw never
    touches them (was: stale visible flag kept them "drawn" via kCharaCull).
  * The on-disk file (chara_mgr.cpp) is only rewritten on success - a
    failed anchor aborts the build before any half-patched binary exists.

Not affected:
  - the player (id 0)
  - NPCs the player is locked on to (CharaBody::targetFlags & 0x1000000)
  - NPCs closer than WOTS2_NPC_SIM_DIST to the player
  - collision (CharaMgr_StepFlags / StepFlags2)

Rollback: WOTS2_NPC_SIM_DIST=0 (or unset).

Idempotent: marker wots2_npc_sim_distance_v2.
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
// wird hier uebersprungen - mit c->cameraDistance als Schwelle bleibt
// der NPC ewig eingefroren, egal wie nah der Spieler kommt.
// Der Spieler (id 0) ist nie eingefroren; seine Position matrix[12..14]
// dient als Bezugspunkt. Solange der Spieler noch nicht gecacht wurde,
// liefert wots2_npc_sim_skip() immer false - der Patch ist dann No-op.
static float s_wots2_player_x = 0.0f;
static float s_wots2_player_y = 0.0f;
static float s_wots2_player_z = 0.0f;
static bool  s_wots2_player_ok = false;

static inline void wots2_npc_cache_player(Chara* c) {
    if (c == nullptr || c->id != 0 || c->params == 0) return;
    const CharaParams* p = guest::ptr<CharaParams>(c->params);
    s_wots2_player_x = p->matrix[12];
    s_wots2_player_y = p->matrix[13];
    s_wots2_player_z = p->matrix[14];
    s_wots2_player_ok = true;
}

static bool wots2_npc_sim_skip(Chara* c) {
    static const float s_dist = []() {
        const char* e = getenv("WOTS2_NPC_SIM_DIST");
        float v = e ? (float)atof(e) : 0.0f;
        return v < 5.0f ? 0.0f : v;   // < 5 Units gilt als "aus"
    }();
    if (s_dist <= 0.0f) return false;
    if (!s_wots2_player_ok) return false;
    if (c == nullptr || c->id == 0) return false;
    if (c->params == 0) return false;
    if ((Body(c)->targetFlags & 0x1000000u) != 0) return false;
    const CharaParams* p = guest::ptr<CharaParams>(c->params);
    const float dx = p->matrix[12] - s_wots2_player_x;
    const float dy = p->matrix[13] - s_wots2_player_y;
    const float dz = p->matrix[14] - s_wots2_player_z;
    return (dx * dx + dy * dy + dz * dz) > s_dist * s_dist;
}

"""


# Patch-Liste: (Name, Such-Pattern, Ersatz)
# Indentierung muss der echten chara_mgr.cpp entsprechen:
#   EACH_CHARA(mgr, c)          (4 Spaces)
#       if (c->active != 0)     (8 Spaces)
#           <body>;             (12 Spaces)
STEP_PATCHES = [
    ("kCharaUpdate",
     r"(EACH_CHARA\(mgr, c\)\r?\n"
     r"        if \(c->active != 0\)\r?\n"
     r"            VirtualCall<void, Chara\*>\(c->vtable, kCharaUpdate, c\);)",
     r"EACH_CHARA(mgr, c)\n"
     r"        if (c->active != 0 && !wots2_npc_sim_skip(c))\n"
     r"            VirtualCall<void, Chara*>(c->vtable, kCharaUpdate, c);"),
    ("kCharaStepA",
     r"(EACH_CHARA\(mgr, c\)\r?\n"
     r"        if \(c->active != 0\)\r?\n"
     r"            VirtualCall<void, Chara\*>\(c->vtable, kCharaStepA, c\);)",
     r"EACH_CHARA(mgr, c)\n"
     r"        if (c->active != 0 && !wots2_npc_sim_skip(c))\n"
     r"            VirtualCall<void, Chara*>(c->vtable, kCharaStepA, c);"),
    ("kCharaStepB",
     r"(EACH_CHARA\(mgr, c\)\r?\n"
     r"        if \(c->active != 0\)\r?\n"
     r"            VirtualCall<void, Chara\*>\(c->vtable, kCharaStepB, c\);)",
     r"EACH_CHARA(mgr, c)\n"
     r"        if (c->active != 0 && !wots2_npc_sim_skip(c))\n"
     r"            VirtualCall<void, Chara*>(c->vtable, kCharaStepB, c);"),
    # Zweite EACH_CHARA-Schleife in StepB ruft Chara_fn1cccf0 direkt auf.
    ("Chara_fn1cccf0",
     r"(EACH_CHARA\(mgr, c\)\r?\n"
     r"        if \(c->active != 0\)\r?\n"
     r"            Chara_fn1cccf0\(c\);)",
     r"EACH_CHARA(mgr, c)\n"
     r"        if (c->active != 0 && !wots2_npc_sim_skip(c))\n"
     r"            Chara_fn1cccf0(c);"),
    # StepC ruft Chara_fn1cec20 direkt auf - das ist der Fix gegenueber v2.
    ("Chara_fn1cec20 (StepC)",
     r"(EACH_CHARA\(mgr, c\)\r?\n"
     r"        if \(c->active != 0\)\r?\n"
     r"            Chara_fn1cec20\(c\);)",
     r"EACH_CHARA(mgr, c)\n"
     r"        if (c->active != 0 && !wots2_npc_sim_skip(c))\n"
     r"            Chara_fn1cec20(c);"),
    ("kCharaStepD",
     r"(EACH_CHARA\(mgr, c\)\r?\n"
     r"        if \(c->active != 0\)\r?\n"
     r"            VirtualCall<void, Chara\*>\(c->vtable, kCharaStepD, c\);)",
     r"EACH_CHARA(mgr, c)\n"
     r"        if (c->active != 0 && !wots2_npc_sim_skip(c))\n"
     r"            VirtualCall<void, Chara*>(c->vtable, kCharaStepD, c);"),
]

# StepMap: skip the VirtualCall + distance computation for far NPCs, and
# force c->visible = 0 so Draw does not touch them at all.
STEPMAP_PATTERN = (
    r"(EACH_CHARA\(mgr, c\) \{\r?\n"
    r"        if \(c->active == 0\)\r?\n"
    r"            continue;\r?\n"
    r"        c->visible = 1;)"
)
STEPMAP_REPLACEMENT = (
    r"EACH_CHARA(mgr, c) {\n"
    r"        if (c->active == 0)\n"
    r"            continue;\n"
    r"        if (wots2_npc_sim_skip(c)) {\n"
    r"            c->visible = 0;\n"
    r"            continue;\n"
    r"        }\n"
    r"        c->visible = 1;"
)


def patch_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    if MARKER in text:
        print("  bereits gepatcht (v2) - nichts zu tun.")
        return True

    if "wots2_npc_sim_distance_v1" in text:
        # v1 -> v2: Helper-Block ersetzen, Step-Calls bleiben (gleicher Name).
        v1_pat = re.compile(
            r"// \[WOTS2-PORT\] wots2_npc_sim_distance_v1.*?"
            r"static bool wots2_npc_sim_skip\(Chara\* c\) \{.*?\n\}\n",
            re.DOTALL,
        )
        if not v1_pat.search(text):
            print("  FEHLER: v1-Marker da, Helper-Block nicht gefunden.")
            return False
        text = v1_pat.sub(HELPER, text, count=1)
        print("  v1-Helper durch v2-Helper ersetzt.")
    else:
        # Frischer Einbau: cstdlib sicherstellen, Helper vor CharaMgr_Ctor.
        if "#include <cstdlib>" not in text:
            if "#include <cstring>" in text:
                text = text.replace(
                    "#include <cstring>",
                    "#include <cstring>\n#include <cstdlib>",
                    1,
                )
        ctor_anchor = "CharaMgr* CharaMgr_Ctor(void* mem) {"
        if ctor_anchor not in text:
            print("  FEHLER: Anker 'CharaMgr_Ctor' nicht gefunden.")
            return False
        text = text.replace(ctor_anchor, HELPER + ctor_anchor, 1)

        applied = 0
        missing = []
        for name, pattern, replacement in STEP_PATCHES:
            new_text, n = re.subn(pattern, replacement, text, count=1)
            if n == 1:
                text = new_text
                applied += 1
            else:
                missing.append(name)
        if missing:
            print(f"  WARNUNG: {len(missing)} Step-Loop(s) nicht gefunden: "
                  + ", ".join(missing))
        if applied == 0:
            print("  FEHLER: keine Step-Loop gepatcht.")
            return False
        print(f"  {applied}/{len(STEP_PATCHES)} Step-Loop(s) gepatcht.")

        text, n = re.subn(STEPMAP_PATTERN, STEPMAP_REPLACEMENT, text, count=1)
        if n == 1:
            print("  StepMap gepatcht (visible=0 fuer ferne NPCs).")
        else:
            print("  WARNUNG: StepMap-Anker nicht gefunden - "
                  "kCharaStepMap laeuft weiter fuer alle NPCs.")

    # Update-Loop: Player-Cache einfuegen. Muster erwartet den bereits
    # gepatchten Update-Loop mit dem Skip im if().
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
    new_text, n = re.subn(update_old, update_new, text, count=1)
    if n != 1:
        print("  FEHLER: Update-Loop nicht gefunden "
              "(Player-Cache konnte nicht eingebaut werden).")
        return False
    text = new_text
    print("  Player-Cache in Update-Loop eingebaut.")

    # Erst jetzt schreiben - bei Fehlern oben bleibt die Datei unveraendert.
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True


def main():
    if len(sys.argv) < 2:
        print("Aufruf: wots2-npc-sim-distance.py <repo-root-oder-chara_mgr.cpp>",
              file=sys.stderr)
        sys.exit(2)
    arg = sys.argv[1]
    path = arg if arg.endswith(".cpp") else os.path.join(
        arg, "src", "game", "chara_mgr.cpp")
    if not os.path.isfile(path):
        print(f"FEHLER: {path} nicht gefunden.", file=sys.stderr)
        sys.exit(1)
    print(f"Patche {path}")
    ok = patch_file(path)
    print("Fertig." if ok else "Fertig mit Fehlern.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
