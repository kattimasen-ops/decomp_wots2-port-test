#!/usr/bin/env python3
"""Fügt in app.cpp einen Fixed-Timestep-Akkumulator ein (beseitigt die Zeitlupe)."""
import sys, pathlib

p = pathlib.Path(sys.argv[1])
t = p.read_text()

# Der exakte Original-Block aus App_Run
anchor = """if (!Native_EditorPaused() && !SceneCall<int>(SceneOf(app->scene), kSceneUpdate))
                        break;
                    App_RenderFrame(app);"""

if anchor not in t:
    print("FEHLER: App_Run-Schleife (SceneUpdate/RenderFrame) nicht gefunden.", file=sys.stderr)
    sys.exit(1)

# Der neue Block mit Akkumulator
new_code = """// Fixed-timestep accumulator (native port)
                    {
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
                        if (wots2_scene_ended) break;
                    }
                    App_RenderFrame(app);"""

t = t.replace(anchor, new_code, 1)

# Sicherstellen, dass SDL für den Performance-Counter eingebunden ist
if "#include <SDL2/SDL.h>" not in t and "#include <SDL.h>" not in t:
    t = t.replace('#include "engine/app.h"', '#include <SDL2/SDL.h>\n#include "engine/app.h"')

p.write_text(t)
print("OK: Fixed-Timestep-Akkumulator in app.cpp eingefügt.")
