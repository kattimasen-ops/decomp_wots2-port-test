#!/usr/bin/env python3
"""WOTS2 lights-cap patch (v2).

Caps the number of point lights the 3D pass uploads each frame to
WOTS2_LIGHTS_MAX (default 2, clamped to 0..8).

Reads the value once from the environment the first time the patch runs.
Replaces the hard-coded cap of 8 from wots2-gs-combat.py; if that patch
did not run, the anchor `n < 16` is also matched.

Idempotent: a second run finds the marker and does nothing.
"""

import os
import re
import sys

MARKER = "wots2_lights_cap_v2"

STATIC_BLOCK = """    // wots2_lights_cap_v2: WOTS2_LIGHTS_MAX (Default 2) begrenzt die
    // Punktlichter pro Frame. Die Shader-Uniform-Arrays fassen 16, das
    // CPU-seitige pos/col-Array 8; der Wert wird auf 0..8 geklemmt.
    static const int s_wots2_lights_max = []() {
        const char* e = getenv("WOTS2_LIGHTS_MAX");
        int v = e ? atoi(e) : 2;
        return v < 0 ? 0 : (v > 8 ? 8 : v);
    }();
    // The sixteen point lights nearest the middle of the view.
    int n = 0;"""


def patch_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    if MARKER in text:
        print("  bereits gepatcht (wots2_lights_cap_v2)")
        return True

    # (1) Insert the static clamp just before `int n = 0;` in lighting_begin().
    #     Primary anchor: the comment line + `int n = 0;` together.
    new_text, n1 = re.subn(
        r"    // The sixteen point lights nearest the middle of the view\.\r?\n    int n = 0;",
        STATIC_BLOCK,
        text,
        count=1,
    )
    if n1 != 1:
        # Fallback: only the comment; `int n = 0;` stays where it was.
        fallback = STATIC_BLOCK.replace("    int n = 0;", "")
        new_text, n1 = re.subn(
            r"    // The sixteen point lights nearest the middle of the view\.",
            fallback,
            text,
            count=1,
        )
    if n1 != 1:
        print("  FEHLER: Anker 'int n = 0;' in lighting_begin() nicht gefunden.")
        return False

    # (2) The loop condition: `n < 8` (combat-patched) or `n < 16` (original).
    new_text, n2 = re.subn(
        r"for \(; n < (?:8|16) && n < \(int\)nearest\.size\(\); n\+\+\)",
        "for (; n < s_wots2_lights_max && n < (int)nearest.size(); n++)",
        new_text,
        count=1,
    )
    if n2 != 1:
        print("  FEHLER: Punktlichter-Schleife nicht gefunden.")
        return False

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_text)
    print("  Lichter-Cap auf WOTS2_LIGHTS_MAX umgestellt (Default 2).")
    return True


def main():
    if len(sys.argv) < 2:
        print("Aufruf: wots2-gs-lights-cap.py <repo-root-oder-gs.cpp>", file=sys.stderr)
        sys.exit(2)
    arg = sys.argv[1]
    path = arg if arg.endswith(".cpp") else os.path.join(arg, "src", "hal", "gs.cpp")
    if not os.path.isfile(path):
        print(f"FEHLER: {path} nicht gefunden.", file=sys.stderr)
        sys.exit(1)
    print(f"Patche {path}")
    ok = patch_file(path)
    print("Fertig." if ok else "Fertig mit Fehlern.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
