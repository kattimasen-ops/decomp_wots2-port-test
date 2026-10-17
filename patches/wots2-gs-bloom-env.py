#!/usr/bin/env python3
"""patches/wots2-gs-bloom-env.py  (v1)

Setzt s_light.bloom auf 0, wenn WOTS2_NO_BLOOM gesetzt ist. Spart den
Bloom-Pass (~3,3 ms/Frame auf Mali-G31 laut [gtiming]-Daten).

Idempotent (Marker wots2_gs_bloom_env_v1). Bricht ab, wenn der Anker
in gs.cpp fehlt — kein halb gepatchtes Binary.

Rollback: WOTS2_NO_BLOOM unset.
"""
import sys, pathlib

MARKER = "wots2_gs_bloom_env_v1"

def patch(path):
    p = pathlib.Path(path)
    t = p.read_text(encoding="utf-8", errors="replace")
    if MARKER in t:
        print("  bereits gepatcht.")
        return
    anchor = "void set_lighting(const Lighting& lighting) {"
    i = t.find(anchor)
    if i < 0:
        print("  FEHLER: set_lighting nicht gefunden.")
        sys.exit(1)
    body_open = t.index("{", i)
    depth = 0
    body_close = -1
    for j in range(body_open, len(t)):
        if t[j] == '{': depth += 1
        elif t[j] == '}':
            depth -= 1
            if depth == 0:
                body_close = j
                break
    if body_close < 0:
        print("  FEHLER: set_lighting-Blockende nicht gefunden.")
        sys.exit(1)
    body = t[body_open+1:body_close]
    if "s_light = s_base;" not in body:
        print("  FEHLER: 's_light = s_base;' in set_lighting nicht gefunden.")
        sys.exit(1)
    body = body.replace(
        "    s_light = s_base;",
        "    s_light = s_base;\n"
        "    // [WOTS2-PORT] " + MARKER + "\n"
        "    if (getenv(\"WOTS2_NO_BLOOM\"))\n"
        "        s_light.bloom = 0.0f;",
        1)
    t = t[:body_open+1] + body + t[body_close:]
    t += "\n/* " + MARKER + " */\n"
    p.write_text(t, encoding="utf-8")
    print("  Bloom-Env eingebaut.")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "src/hal/gs.cpp"
    if not target.endswith(".cpp"):
        target = target.rstrip("/") + "/src/hal/gs.cpp"
    print(f"Patche {target}")
    patch(target)
    print("Fertig.")
