#!/usr/bin/env python3
"""
patches/wots2-gs-init-diag.py

Zweck:  Ersetzt den undifferenzierten Fehler-Check in hal::gs::init()
        durch granulare Fehlerbehandlung und Diagnoseausgaben. Stellt
        den GL-Profilwunsch von Desktop-GL-Core auf OpenGL ES 3.2 um.

Hintergrund:
        Der urspruengliche Code fragt einen Desktop-OpenGL-3.3-Core-
        Kontext an, obwohl SDL2 mit '-DSDL_OPENGL=OFF -DSDL_OPENGLES=ON'
        gebaut wurde und die Mali-G31 nur OpenGL ES hat. Ausserdem prueft
        der Code SDL_Init und SDL_CreateWindow nicht: ein NULL-Window
        wird an SDL_GL_CreateContext weitergereicht, was
        CHECK_WINDOW_MAGIC mit 'Invalid window' quittiert — nicht die
        eigentliche Ursache.

        ES-3.2 statt ES-3.0: Mali gibt bei minor=0 nur einen ES-3.0-
        Kontext, der '320 es' in den Shadern nicht akzeptiert. Der Port
        braucht aber gl_FragDepth, das erst ab ES 3.2 verfuegbar ist.

Zieldatei: src/hal/gs.cpp
Marker:    WOTS2-GS-INIT-DIAG

Aufruf:
    python3 patches/wots2-gs-init-diag.py src/hal/gs.cpp
"""

import sys
import os

MARKER = "WOTS2-GS-INIT-DIAG"
START_MARKER = "    SDL_Init(SDL_INIT_VIDEO);"
END_MARKER = "        exit(1);\n    }\n"

NEW_BLOCK = '''    // --- WOTS2-GS-INIT-DIAG: granulare Fehlerdiagnose ---
    if (const char* drv = getenv("SDL_VIDEODRIVER"))
        fprintf(stderr, "[GS] SDL_VIDEODRIVER=%s\\n", drv);
    if (SDL_Init(SDL_INIT_VIDEO) != 0) {
        fprintf(stderr, "[GS] SDL_Init(SDL_INIT_VIDEO) failed: %s\\n", SDL_GetError());
        exit(1);
    }
    fprintf(stderr, "[GS] video driver: %s\\n", SDL_GetCurrentVideoDriver());

    // Mali-G31 has OpenGL ES 3.2 only.  Ask for ES 3.2; the driver gives
    // the highest 3.x it has.
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 2);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_ES);
    SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);
    SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE, 24);

    // The PS2's frame is shown at 4:3, so the window is 2x wide and slightly
    // more than 2x tall.
    s_window = SDL_CreateWindow(title,
        SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
        width * 2, width * 2 * 3 / 4,
        SDL_WINDOW_OPENGL | SDL_WINDOW_SHOWN | SDL_WINDOW_RESIZABLE);
    if (s_window == nullptr) {
        fprintf(stderr, "[GS] SDL_CreateWindow(%dx%d) failed: %s\\n",
                width * 2, width * 2 * 3 / 4, SDL_GetError());
        exit(1);
    }

    s_gl_ctx = SDL_GL_CreateContext(s_window);
    if (s_gl_ctx == nullptr) {
        fprintf(stderr, "[GS] SDL_GL_CreateContext failed: %s\\n", SDL_GetError());
        exit(1);
    }
    if (!wots2_gl_load()) {
        fprintf(stderr, "[GS] wots2_gl_load failed: %s\\n", SDL_GetError());
        exit(1);
    }
    {
        GLint vmajor = 0, vminor = 0;
        SDL_GL_GetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, &vmajor);
        SDL_GL_GetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, &vminor);
        fprintf(stderr, "[GS] context: ES %d.%d  GL_VERSION='%s'  GL_RENDERER='%s'\\n",
                vmajor, vminor,
                (const char*)glGetString(GL_VERSION),
                (const char*)glGetString(GL_RENDERER));
    }
    // --- WOTS2-GS-INIT-DIAG end ---
'''

def patch_file(path):
    if not os.path.isfile(path):
        print(f"  FEHLER: Datei nicht gefunden: {path}")
        return False
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    if MARKER in content:
        print(f"  Patch bereits vorhanden (Marker: {MARKER}).")
        return False
    start = content.find(START_MARKER)
    if start < 0:
        print(f"  FEHLER: '{START_MARKER.strip()}' nicht gefunden.")
        return False
    end = content.find(END_MARKER, start)
    if end < 0:
        print(f"  FEHLER: '{END_MARKER.strip()}' nicht gefunden.")
        return False
    end += len(END_MARKER)
    patched = content[:start] + NEW_BLOCK + content[end:]
    with open(path, "w", encoding="utf-8") as f:
        f.write(patched)
    print(f"  Patch angewendet. {end - start} Bytes ersetzt.")
    return True

def main():
    if len(sys.argv) < 2:
        print("Verwendung: python3 wots2-gs-init-diag.py <zieldatei>")
        sys.exit(1)
    print("== WOTS2 gs::init Diagnose-Patch ==")
    patch_file(sys.argv[1])
    print("== Fertig ==")

if __name__ == "__main__":
    main()
