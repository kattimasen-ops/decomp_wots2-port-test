#!/usr/bin/env python3
"""WOTS2 character draw LOD patch (v1).

Reduces the per-NPC draw cost for NPCs far from the player without making
them disappear:
  * skips Lights_At and ground_eased for far NPCs (static scene light)
  * skips the per-bone matrix multiplication for far NPCs (rest pose)
  * skips the shadow pass for far NPCs (saves 2 extra draws per NPC)

The player (id 0) and near NPCs are unaffected. No LOD-2 models are loaded
(the port only ships LOD-1; see CharaModels_Start's phase > 2 comment).

Rollback: WOTS2_CHARA_DRAW_SKIP_DIST=0 (or unset) and
          WOTS2_CHARA_SHADOW_SKIP_DIST=0 (or unset).

Idempotent: marker wots2_chara_draw_lod_v1.
"""

import os
import re
import sys

MARKER = "wots2_chara_draw_lod_v1"

HELPER = r"""
// [WOTS2-PORT] wots2_chara_draw_lod_v1
// Ferne NPCs (> WOTS2_CHARA_DRAW_SKIP_DIST Units vom Spieler) werden im
// Draw-Pfad vereinfacht: keine Lights_At/ground_eased-Abfrage, keine
// Per-Bone-Matrixmultiplikation (Rest-Pose), kein Shadow-Pass. Der Spieler
// (id 0) und nahe NPCs sind unberuehrt.
// Rollback: WOTS2_CHARA_DRAW_SKIP_DIST=0 und WOTS2_CHARA_SHADOW_SKIP_DIST=0.
static float s_wots2_chara_draw_px = 0.0f;
static float s_wots2_chara_draw_py = 0.0f;
static float s_wots2_chara_draw_pz = 0.0f;
static bool  s_wots2_chara_draw_ok = false;

static inline void wots2_chara_draw_cache_player(Chara* c) {
    if (c == nullptr || c->id != 0 || c->params == 0) return;
    const CharaParams* p = guest::ptr<CharaParams>(c->params);
    s_wots2_chara_draw_px = p->matrix[12];
    s_wots2_chara_draw_py = p->matrix[13];
    s_wots2_chara_draw_pz = p->matrix[14];
    s_wots2_chara_draw_ok = true;
}

static bool wots2_chara_draw_skip(Chara* c) {
    static const float s_dist = []() {
        const char* e = getenv("WOTS2_CHARA_DRAW_SKIP_DIST");
        float v = e ? (float)atof(e) : 0.0f;
        return v < 5.0f ? 0.0f : v;
    }();
    if (s_dist <= 0.0f) return false;
    if (!s_wots2_chara_draw_ok) return false;
    if (c == nullptr || c->id == 0 || c->params == 0) return false;
    const CharaParams* p = guest::ptr<CharaParams>(c->params);
    const float dx = p->matrix[12] - s_wots2_chara_draw_px;
    const float dy = p->matrix[13] - s_wots2_chara_draw_py;
    const float dz = p->matrix[14] - s_wots2_chara_draw_pz;
    return (dx * dx + dy * dy + dz * dz) > s_dist * s_dist;
}

static bool wots2_chara_shadow_skip(Chara* c) {
    static const float s_dist = []() {
        const char* e = getenv("WOTS2_CHARA_SHADOW_SKIP_DIST");
        float v = e ? (float)atof(e) : 0.0f;
        return v < 5.0f ? 0.0f : v;
    }();
    if (s_dist <= 0.0f) return false;
    if (!s_wots2_chara_draw_ok) return false;
    if (c == nullptr || c->id == 0 || c->params == 0) return false;
    const CharaParams* p = guest::ptr<CharaParams>(c->params);
    const float dx = p->matrix[12] - s_wots2_chara_draw_px;
    const float dy = p->matrix[13] - s_wots2_chara_draw_py;
    const float dz = p->matrix[14] - s_wots2_chara_draw_pz;
    return (dx * dx + dy * dy + dz * dz) > s_dist * s_dist;
}

"""


def patch_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    if MARKER in text:
        print("  bereits gepatcht (v1) - nichts zu tun.")
        return True

    # 1. Helfer nach mat_mul einfuegen (im anonymen Namespace).
    mat_mul_end = re.search(
        r"void mat_mul\(const float\* a, const float\* b, float\* out\) \{.*?\n\}\n",
        text, re.DOTALL)
    if not mat_mul_end:
        print("  FEHLER: mat_mul-Anker nicht gefunden.")
        return False
    at = mat_mul_end.end()
    text = text[:at] + HELPER + text[at:]
    print("  Helfer eingefuegt.")

    # 2. CharaModels_Draw: Cache und Skip am Anfang.
    text, n = re.subn(
        r"(void CharaModels_Draw\(Chara\* c, int\) \{\n)",
        r"\1    wots2_chara_draw_cache_player(c);\n"
        r"    const bool skip = wots2_chara_draw_skip(c);\n",
        text, count=1)
    if n != 1:
        print("  FEHLER: CharaModels_Draw-Anker nicht gefunden.")
        return False
    print("  CharaModels_Draw: Cache + Skip eingebaut.")

    # 3. Body-Pose: Per-Bone-Matrixmultiplikation nur wenn !skip.
    text, n = re.subn(
        r"(for \(int i = 0; i < skeleton->count; i\+\+\) \{\n"
        r"        float\* out = &pose\[\(size_t\)i \* 16\];\n"
        r"        if \()"
        r"(\(bones\[i\]\.flags & 0xE0000000u\) && bones\[i\]\.parent != 0\))",
        r"\1!skip && \2",
        text, count=1)
    if n != 1:
        print("  FEHLER: body-pose-Anker nicht gefunden.")
        return False
    print("  Body-Pose: Skip-Bedingung eingebaut.")

    # 4. Head-Pose: Per-Bone-Matrixmultiplikation nur wenn !skip.
    text, n = re.subn(
        r"(for \(size_t i = 0; i < count; i\+\+\) \{\n"
        r"            float\* out = &headPose\[i \* 16\];\n"
        r"            if \()"
        r"(i < 28 && i < \(size_t\)skeleton->count\))",
        r"\1!skip && \2",
        text, count=1)
    if n != 1:
        print("  FEHLER: head-pose-Anker nicht gefunden.")
        return False
    print("  Head-Pose: Skip-Bedingung eingebaut.")

    # 5. ground_eased nur wenn !skip.
    text, n = re.subn(
        r"const float ground = ground_eased\(guest::addr\(c\), &matrix\[12\]\);",
        r"const float ground = skip ? 1.0f : ground_eased(guest::addr(c), &matrix[12]);",
        text, count=1)
    if n != 1:
        print("  FEHLER: ground_eased-Anker nicht gefunden.")
        return False
    print("  ground_eased: Skip-Bedingung eingebaut.")

    # 6. Lights_At nur wenn !skip.
    text, n = re.subn(
        r"const int changed = Lights_At\(&matrix\[12\], dirs, colours\);",
        r"const int changed = skip ? 0 : Lights_At(&matrix[12], dirs, colours);",
        text, count=1)
    if n != 1:
        print("  FEHLER: Lights_At-Anker nicht gefunden.")
        return False
    print("  Lights_At: Skip-Bedingung eingebaut.")

    # 7. hle_chara_shadow: Skip am Anfang.
    text, n = re.subn(
        r"(void hle_chara_shadow\(Chara\* c, float strength\) \{\n)",
        r"\1    if (wots2_chara_shadow_skip(c)) return;\n",
        text, count=1)
    if n != 1:
        print("  FEHLER: hle_chara_shadow-Anker nicht gefunden.")
        return False
    print("  hle_chara_shadow: Skip eingebaut.")

    text += f"\n/* {MARKER} */\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True


def main():
    if len(sys.argv) < 2:
        print("Aufruf: wots2-chara-draw-lod.py <repo-root-oder-hle_chara.cpp>",
              file=sys.stderr)
        sys.exit(2)
    arg = sys.argv[1]
    path = arg if arg.endswith(".cpp") else os.path.join(
        arg, "src", "native", "hle_chara.cpp")
    if not os.path.isfile(path):
        print(f"FEHLER: {path} nicht gefunden.", file=sys.stderr)
        sys.exit(1)
    print(f"Patche {path}")
    ok = patch_file(path)
    print("Fertig." if ok else "Fertig mit Fehlern.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
