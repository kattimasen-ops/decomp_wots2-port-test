#!/usr/bin/env python3
"""
patches/sdl2-kmsdrm-window.py

Zweck:   Behebt das KMSDRM-Fenstererstellungsproblem auf ARM-SoCs
         (insbesondere Mali-G31 / RK3326), bei dem SDL2 ein Fenster
         ohne GL-Flag erstellt und dadurch kein EGL-Kontext erzeugt
         werden kann ("no OpenGL 3.3: Invalid window").

Hintergrund:
         Der KMSDRM-Treiber in SDL2 markierte urspruenglich nur das
         *erste* erstellte Fenster als SDL_WINDOW_OPENGL. Auf Geräten
         mit Mali-GPU (und vc4) führt das dazu, dass nachfolgende
         Fenster keinen GL-Kontext bekommen und SDL_CreateWindow()
         fehlschlägt.

         Der Fix (Commit c35e71892e von vanfanel) verschiebt die
         Zuweisung window->flags |= SDL_WINDOW_OPENGL; in den
         NON-Vulkan-Block, sodass ALLE Nicht-Vulkan-Fenster als
         OpenGL-Fenster markiert werden.

         Betroffene Datei im SDL2-Quellbaum:
             src/video/kmsdrm/SDL_kmsdrmvideo.c
         Betroffene Funktion:
             KMSDRM_CreateWindow()

Idempotenz:
         Der Patch prueft vor dem Schreiben, ob der Marker bereits
         vorhanden ist. Mehrfaches Ausfuehren ist unschaedlich.

Aufruf:
         python3 patches/sdl2-kmsdrm-window.py <SDL2_SRC_DIR>
         Beispiel:
             python3 patches/sdl2-kmsdrm-window.py /build/SDL2-2.0.14
"""

import sys
import os
import re

MARKER = "window->flags |= SDL_WINDOW_OPENGL;"

# Die Ziel-Datei relativ zum SDL2-Quellbaum
TARGET_REL = "src/video/kmsdrm/SDL_kmsdrmvideo.c"


def patch_file(path: str) -> bool:
    """Wendet den Patch an. Gibt True zurueck, wenn geaendert wurde."""
    if not os.path.isfile(path):
        print(f"  FEHLER: Datei nicht gefunden: {path}")
        return False

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    # --- Idempotenz-Pruefung ---
    # Der Fix hat den OPENGL-Flag-Aufruf *vor* dem gbm_init-Block.
    # Wir suchen nach dem Muster, das durch den Patch entsteht.
    # Wenn wir den Marker im NON-Vulkan-Block finden, ist der Patch
    # bereits angewendet.
    #
    # Wir suchen nach:
    #   if (!is_vulkan && !vulkan_mode) {
    #       /* NON-Vulkan block. */
    #       window->flags |= SDL_WINDOW_OPENGL;
    #
    # Das ist der Zustand NACH dem Patch.
    already_pattern = re.compile(
        r"if\s*\(\s*!is_vulkan\s*&&\s*!vulkan_mode\s*\)\s*\{"
        r"(?:(?!\n\s*if\s*\(\s*!\s*\(viddata->gbm_init\)\s*\)).)*?"
        r"window->flags\s*\|=\s*SDL_WINDOW_OPENGL\s*;",
        re.DOTALL,
    )
    if already_pattern.search(content):
        print(f"  Patch bereits vorhanden in: {path}")
        return False

    # --- Patch anwenden ---
    # Wir suchen den NON-Vulkan-Block und fuegen die Zuweisung ein.
    #
    # Zu findender Original-Code (SDL 2.0.14 / 2.0.16 / 2.0.18):
    #
    #     if (!is_vulkan && !vulkan_mode) {
    #         /* NON-Vulkan block. */
    #
    #         if (!(viddata->gbm_init)) {
    #             ... (Kommentarblock)
    #             /* Maybe you didn't ask for an OPENGL window, but that's what you will get.
    #              * See previous comment on why. */
    #             window->flags |= SDL_WINDOW_OPENGL;
    #
    #             /* Reopen FD, create gbm dev, setup display plane, etc,. */
    #
    # Wir verschieben die Zuweisung *vor* den gbm_init-Block.

    # Schritt 1: Finde den NON-Vulkan-Block und die erste Zeile danach.
    non_vulkan_re = re.compile(
        r"(if\s*\(\s*!is_vulkan\s*&&\s*!vulkan_mode\s*\)\s*\{\s*"
        r"/\*\s*NON-Vulkan\s+block\.\s*\*/\s*)",
        re.DOTALL,
    )
    m = non_vulkan_re.search(content)
    if not m:
        print(f"  FEHLER: NON-Vulkan-Block nicht gefunden in: {path}")
        print("  Die SDL2-Version passt moeglicherweise nicht zum Patch.")
        return False

    # Schritt 2: Suche die vorhandene OPENGL-Zuweisung im gbm_init-Block,
    # um sie zu entfernen (sie wird verschoben).
    # Muster:
    #     /* Maybe you didn't ask for an OPENGL window, but that's what you will get.
    #      * See previous comment on why. */
    #     window->flags |= SDL_WINDOW_OPENGL;
    #
    # oder (je nach Version):
    #     /* Maybe you didn't ask for an OPENGL window, but that's what you will get.
    #      * See following comments on why. */
    #     window->flags |= SDL_WINDOW_OPENGL;
    old_assign_re = re.compile(
        r"/\*\s*Maybe\s+you\s+didn't\s+ask\s+for\s+an\s+OPENGL\s+window,\s+but\s+that's\s+what\s+you\s+will\s+get\.\s*"
        r"(?:See\s+(?:previous|following)\s+comment(?:s)?\s+on\s+why\.\s*\*/\s*)"
        r"window->flags\s*\|=\s*SDL_WINDOW_OPENGL\s*;",
        re.DOTALL,
    )

    # Schritt 3: Patch durchfuehren
    # Wir fuegen die Zuweisung direkt nach der NON-Vulkan-Block-Klammer ein
    # und entfernen die alte Zuweisung aus dem gbm_init-Block.

    # Neuen Einfuege-Text bauen
    insert_text = (
        "    /* Maybe you didn't ask for an OPENGL window, but that's what you will get.\n"
        "     * See following comments on why. */\n"
        "    window->flags |= SDL_WINDOW_OPENGL;\n"
        "\n"
    )

    # Einfuegen nach dem Match
    patched = content[:m.end()] + insert_text + content[m.end():]

    # Alte Zuweisung entfernen
    patched, n_removed = old_assign_re.subn("", patched)

    if n_removed == 0:
        print(f"  WARNUNG: Alte Zuweisung nicht gefunden in: {path}")
        print("  Der Patch wurde trotzdem geschrieben (Zuweisung ist jetzt doppelt).")
        # Wir schreiben trotzdem, weil die neue Zuweisung im NON-Vulkan-Block
        # wichtiger ist als die alte im gbm_init-Block. Doppelte Zuweisung
        # ist harmlos (idempotent im Effekt).
    else:
        print(f"  Alte Zuweisung entfernt ({n_removed} Vorkommen).")

    # Schritt 4: Zurueckschreiben
    with open(path, "w", encoding="utf-8") as f:
        f.write(patched)

    print(f"  Patch erfolgreich angewendet: {path}")
    return True


def main():
    if len(sys.argv) < 2:
        print("Verwendung: python3 sdl2-kmsdrm-window.py <SDL2_SRC_DIR>")
        print("  <SDL2_SRC_DIR> ist das Wurzelverzeichnis des SDL2-Quellbaums,")
        print("  z. B. /build/SDL2-2.0.14 oder ./SDL2")
        sys.exit(1)

    sdl2_dir = sys.argv[1]
    if not os.path.isdir(sdl2_dir):
        print(f"FEHLER: Kein Verzeichnis: {sdl2_dir}")
        sys.exit(1)

    target = os.path.join(sdl2_dir, TARGET_REL)
    print(f"== Patche SDL2 KMSDRM-Fenster: {target} ==")

    changed = patch_file(target)
    if changed:
        print("== SDL2 KMSDRM-Patch fertig ==")
    else:
        print("== SDL2 KMSDRM-Patch: Keine Aenderung notwendig ==")


if __name__ == "__main__":
    main()
