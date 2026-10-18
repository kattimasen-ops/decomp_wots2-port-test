#!/usr/bin/env python3
"""Fügt in app.cpp einen Fixed-Timestep-Akkumulator ein (beseitigt die Zeitlupe)."""
import sys, re, pathlib

p = pathlib.Path(sys.argv[1])
t = p.read_text()

# Wir suchen nach dem Update-Aufruf in der inneren Spielschleife.
# Der Patch wots2-app-timing.py hat hier bereits eine Zeitmessung eingebaut,
# daher suchen wir nach dem Kern-Aufruf.
anchor = "if (!Native_EditorPaused() && !SceneCall<int>(SceneOf(app->scene), kSceneUpdate))"

if anchor not in t:
    print("FEHLER: SceneUpdate-Aufruf in App_Run nicht gefunden.", file=sys.stderr)
    sys.exit(1)

# Die neue Logik: Ein Akkumulator, der die Update-Schritte ausführt.
# Wir ersetzen NUR den Update-Teil, das Rendern (App_RenderFrame) bleibt in der äußeren Schleife.
new_logic = r"""// Fixed-timestep accumulator
                    static double wots2_acc = 0.0;
                    static Uint64 wots2_last = SDL_GetPerformanceCounter();
                    Uint64 wots2_now = SDL_GetPerformanceCounter();
                    double wots2_frame = (double)(wots2_now - wots2_last) / (double)SDL_GetPerformanceFrequency();
                    wots2_last = wots2_now;
                    if (wots2_frame > 0.25) wots2_frame = 0.25;
                    wots2_acc += wots2_frame;
                    bool wots2_scene_ended = false;
                    
                    do {
                        if (!Native_EditorPaused() && !SceneCall<int>(SceneOf(app->scene), kSceneUpdate)) {
                            wots2_scene_ended = true;
                            break;
                        }
                        wots2_acc -= (1.0 / 30.0);
                    } while (wots2_acc >= (1.0 / 30.0));
                    
                    if (wots2_scene_ended)
                        break;"""

# Ersetze den alten Aufruf mit der neuen Logik
t = t.replace(anchor, new_logic, 1)

# In app.cpp fehlen oft die Includes für SDL. Wir prüfen, ob sie da sind.
if "#include <SDL2/SDL.h>" not in t and "#include <SDL.h>" not in t:
    t = t.replace("#include \"engine/app.h\"", "#include <SDL2/SDL.h>\n#include \"engine/app.h\"")

p.write_text(t)
print("OK: Fixed-Timestep-Akkumulator in app.cpp eingefügt.")
