#!/usr/bin/env python3
"""patches/wots2-gs-no-post-env.py  (v1)

Setzt lighting_wanted() auf false, wenn WOTS2_NO_POST gesetzt ist. Das
ueberspringt die ganze Post-Pass-Kette (AO, Bloom, Grade, DOF, God-Rays)
und den Depth-Buffer-Schreibpfad in lighting_begin. Der [gtiming]-Wert
play.post (~3,3 ms) plus play.loop-Depth-Overhead plus der Blit in
swap fallen zusammen weg — geschaetzt 9-12 ms/Frame.

Achtung: Das Bild verliert Farbkorrektur, Bloom und Schatten. Visuell
sichtbar, aber spielbar.

Idempotent (Marker wots2_gs_no_post_env_v1).

Rollback: WOTS2_NO_POST unset.
"""
import sys, pathlib

MARKER = "wots2_gs_no_post_env_v1"

def patch(path):
    p = pathlib.Path(path)
    t = p.read_text(encoding="utf-8", errors="replace")
    if MARKER in t:
        print("  bereits gepatcht.")
        return
    anchor = "static bool lighting_wanted() {"
    i = t.find(anchor)
    if i < 0:
        print("  FEHLER: lighting_wanted nicht gefunden.")
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
        print("  FEHLER: lighting_wanted-Blockende nicht gefunden.")
        sys.exit(1)
    body = t[body_open+1:body_close]
    body = "\n    if (getenv(\"WOTS2_NO_POST\")) return false;\n" + body
    t = t[:body_open+1] + body + t[body_close:]
    t += "\n/* " + MARKER + " */\n"
    p.write_text(t, encoding="utf-8")
    print("  No-Post-Env eingebaut.")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "src/hal/gs.cpp"
    if not target.endswith(".cpp"):
        target = target.rstrip("/") + "/src/hal/gs.cpp"
    print(f"Patche {target}")
    patch(target)
    print("Fertig.")
