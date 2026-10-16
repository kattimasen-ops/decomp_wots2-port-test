#!/usr/bin/env python3
"""
patches/wots2-pad-swap.py

Tauscht die Zuordnung der SDL-Facebuttons fuer den M9 Pro / R36S.
Auf diesem Geraet meldet die Firmware A und B (und X und Y) vertauscht
gegenueber der physischen Beschriftung. Der Patch vertauscht die
Zuordnung in pad.cpp, damit die Beschriftung auf dem Geraet mit der
Funktion im Spiel uebereinstimmt:

  SDL_CONTROLLER_BUTTON_B  -> PS2 CROSS
  SDL_CONTROLLER_BUTTON_A  -> PS2 CIRCLE
  SDL_CONTROLLER_BUTTON_Y  -> PS2 SQUARE
  SDL_CONTROLLER_BUTTON_X  -> PS2 TRIANGLE

Idempotent: Marker 'wots2-pad-swap.py'.

Zieldatei: src/hal/pad.cpp
Aufruf:    python3 patches/wots2-pad-swap.py src/hal/pad.cpp
"""
import pathlib
import sys

MARKER = "wots2-pad-swap.py"

OLD = """    static constexpr struct { SDL_GameControllerButton from; Button to; } kButtons[] = {
        {SDL_CONTROLLER_BUTTON_A, CROSS}, {SDL_CONTROLLER_BUTTON_B, CIRCLE},
        {SDL_CONTROLLER_BUTTON_X, SQUARE}, {SDL_CONTROLLER_BUTTON_Y, TRIANGLE},"""

NEW = """    // " + MARKER + "
    // A/B und X/Y vertauscht: der Geraetetreiber meldet die physischen
    // Buttons anders als SDL erwartet.
    static constexpr struct { SDL_GameControllerButton from; Button to; } kButtons[] = {
        {SDL_CONTROLLER_BUTTON_B, CROSS}, {SDL_CONTROLLER_BUTTON_A, CIRCLE},
        {SDL_CONTROLLER_BUTTON_Y, SQUARE}, {SDL_CONTROLLER_BUTTON_X, TRIANGLE},"""


def patch(path):
    p = pathlib.Path(path)
    if not p.is_file():
        print(f"  FEHLER: {path} nicht gefunden.")
        sys.exit(1)
    t = p.read_text()
    if MARKER in t:
        print("  Pad-Swap bereits vorhanden.")
        return
    if OLD not in t:
        print("  FEHLER: kButtons-Block in der erwarteten Form nicht gefunden.")
        print("  Moeglicherweise wurde pad.cpp zwischenzeitlich geaendert.")
        sys.exit(1)
    t = t.replace(OLD, NEW, 1)
    p.write_text(t)
    print("  Pad-Swap angewendet (A<->B, X<->Y).")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "src/hal/pad.cpp"
    print(f"Patche {target}")
    patch(target)
    print("Fertig.")
