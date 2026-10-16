#!/usr/bin/env python3
"""
patches/sdl2-kmsdrm-window.py

Zweck:
    Erzwingt SDL_WINDOW_OPENGL fuer alle Nicht-Vulkan-Fenster im
    KMSDRM-Treiber. Ohne diesen Flag kann auf manchen ARM-SoCs
    (Mali-G31 / RK3326) kein EGL-Kontext erstellt werden; der Port
    bricht dann mit "no OpenGL 3.3: Invalid window" ab.

Hintergrund:
    Der KMSDRM-Treiber in aelteren SDL2-Versionen setzte den
    OPENGL-Flag nur unter bestimmten Bedingungen. Auf Mali-G31
    fuehrt das dazu, dass SDL_CreateWindow() ein Fenster ohne
    GL-Kontext liefert und SDL_GL_CreateContext() mit
    "Invalid window" scheitert.

    Der Fix (Upstream-Kommit c35e71892e) verschiebt die Zuweisung
    an den Anfang des NON-Vulkan-Blocks. In SDL 2.30.10 ist der Fix
    moeglicherweise bereits enthalten — dieses Skript erkennt das
    und setzt trotzdem einen Marker, damit der CI-Report
    reproduzierbar bleibt.

Idempotenz:
    Marker "WOTS2-KMSDRM-WINDOW-FLAG". Wird vor dem Schreiben geprueft.

Zieldatei:
    <SDL2_SRC_DIR>/src/video/kmsdrm/SDL_kmsdrmvideo.c

Aufruf:
    python3 patches/sdl2-kmsdrm-window.py <SDL2_SRC_DIR>
"""

import sys
import os
import re

MARKER = "WOTS2-KMSDRM-WINDOW-FLAG"

FUNC_NAME = "KMSDRM_CreateWindow"
TARGET_REL = "src/video/kmsdrm/SDL_kmsdrmvideo.c"


def find_function_open_brace(text: str, func_name: str) -> int:
    """Sucht die oeffnende { der Funktion func_name. Gibt Index zurueck."""
    pattern = re.compile(
        re.escape(func_name) + r"\s*\([^)]*\)\s*\{",
        re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        return -1
    return m.end()


def klammer_balance_ok(text: str) -> bool:
    """Grober Klammer-Check: { und } muessen gleich oft vorkommen."""
    return text.count("{") == text.count("}")


def patch_file(path: str) -> bool:
    if not os.path.isfile(path):
        print(f"  FEHLER: Datei nicht gefunden: {path}")
        return False

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    # --- Diagnose ---
    print(f"  Datei: {path}")
    print(f"  Groesse: {len(content)} Bytes, {content.count(chr(10))} Zeilen")

    # --- Idempotenz ---
    if MARKER in content:
        print(f"  Patch bereits vorhanden (Marker: {MARKER}).")
        return False

    # --- Upstream-Status pruefen ---
    has_flag_assignment = "window->flags |= SDL_WINDOW_OPENGL" in content
    print(f"  SDL_WINDOW_OPENGL-Zuweisung vorhanden: {has_flag_assignment}")

    # --- Funktion finden ---
    insert_pos = find_function_open_brace(content, FUNC_NAME)
    if insert_pos < 0:
        print(f"  FEHLER: {FUNC_NAME} nicht gefunden.")
        return False
    print(f"  {FUNC_NAME}: oeffnende Klammer bei Byte {insert_pos}")

    # --- Einfuege-Text ---
    insert = (
        "\n"
        "    /* " + MARKER + ":\n"
        "     * Erzwingt OPENGL-Flag fuer alle Nicht-Vulkan-Fenster.\n"
        "     * Auf Mali-G31 (RK3326) noetig, damit SDL_GL_CreateContext\n"
        "     * einen gueltigen EGL-Kontext erzeugen kann. */\n"
        "    if (!(window->flags & SDL_WINDOW_VULKAN)) {\n"
        "        window->flags |= SDL_WINDOW_OPENGL;\n"
        "    }\n"
    )

    patched = content[:insert_pos] + insert + content[insert_pos:]

    # --- Klammerbilanz ---
    if not klammer_balance_ok(patched):
        print(f"  FEHLER: Klammerbilanz verletzt "
              f"({{={patched.count('{')}, }}={patched.count('}')}).")
        return False

    # --- Schreiben ---
    with open(path, "w", encoding="utf-8") as f:
        f.write(patched)

    print(f"  Patch angewendet. Neue Groesse: {len(patched)} Bytes")
    return True


def main():
    if len(sys.argv) < 2:
        print("Verwendung: python3 sdl2-kmsdrm-window.py <SDL2_SRC_DIR>")
        sys.exit(1)

    sdl2_dir = sys.argv[1]
    if not os.path.isdir(sdl2_dir):
        print(f"FEHLER: Kein Verzeichnis: {sdl2_dir}")
        sys.exit(1)

    target = os.path.join(sdl2_dir, TARGET_REL)
    print(f"== SDL2 KMSDRM Window-Flag-Patch ==")
    print(f"== Ziel: {target} ==")

    patch_file(target)
    print("== Patch-Lauf beendet ==")


if __name__ == "__main__":
    main()
