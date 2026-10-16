#!/usr/bin/env python3
"""
patches/wots2-pad-swap.py

Tauscht die Zuordnung der SDL-Facebuttons fuer den M9 Pro / R36S.
Auf diesem Geraet meldet die Firmware die Buttons vertauscht
gegenueber der physischen Beschriftung. Der Patch vertauscht die
Zuordnung in pad.cpp, damit die Beschriftung auf dem Geraet mit
der Funktion im Spiel uebereinstimmt.

PS2-Belegung (Way of the Samurai 2):
  SDL_CONTROLLER_BUTTON_B  -> PS2 CROSS       (physisch unten)
  SDL_CONTROLLER_BUTTON_A  -> PS2 CIRCLE      (physisch rechts)
  SDL_CONTROLLER_BUTTON_Y  -> PS2 SQUARE      (physisch links)
  SDL_CONTROLLER_BUTTON_X  -> PS2 TRIANGLE    (physisch oben)

Idempotent: Marker 'wots2-pad-swap.py'.

Zieldatei: src/hal/pad.cpp
Aufruf:    python3 patches/wots2-pad-swap.py src/hal/pad.cpp
"""
import pathlib
import sys

MARKER = "wots2-pad-swap.py"

OLD_BUTTONS = """    static constexpr struct { SDL_GameControllerButton from; Button to; } kButtons[] = {
        {SDL_CONTROLLER_BUTTON_A, CROSS}, {SDL_CONTROLLER_BUTTON_B, CIRCLE},
        {SDL_CONTROLLER_BUTTON_X, SQUARE}, {SDL_CONTROLLER_BUTTON_Y, TRIANGLE},"""

NEW_BUTTONS = """    // " + MARKER + "
    // A/B und X/Y vertauscht: der Geraetetreiber meldet die physischen
    // Buttons anders als SDL erwartet. Auf dem R36S/M9:
    //   physisch unten  -> SDL B  -> PS2 Cross
    //   physisch rechts -> SDL A  -> PS2 Circle
    //   physisch links  -> SDL Y  -> PS2 Square
    //   physisch oben   -> SDL X  -> PS2 Triangle
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
    if OLD_BUTTONS not in t:
        print("  FEHLER: kButtons-Block nicht in der erwarteten Form gefunden.")
        sys.exit(1)
    t = t.replace(OLD_BUTTONS, NEW_BUTTONS, 1)
    p.write_text(t)
    print("  Pad-Swap angewendet (A<->B, X<->Y).")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "src/hal/pad.cpp"
    print(f"Patche {target}")
    patch(target)
    print("Fertig.")
