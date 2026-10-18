#!/usr/bin/env python3
"""Fügt App-Loop-Timing hinzu, angepasst an den Deltatime-Akkumulator."""
import sys, pathlib

p = pathlib.Path(sys.argv[1])
t = p.read_text()

# Der neue Anker (nach dem Deltatime-Patch)
anchor = "if (!Native_EditorPaused() && !SceneCall<int>(SceneOf(app->scene), kSceneUpdate)) {"

if anchor not in t:
    print("FEHLER: Neuer Deltatime-SceneUpdate-Aufruf nicht gefunden.", file=sys.stderr)
    sys.exit(1)

# Wir fügen eine Zeitmessung um den Aufruf herum ein
new_code = """auto t0_upd = std::chrono::high_resolution_clock::now();
                            if (!Native_EditorPaused() && !SceneCall<int>(SceneOf(app->scene), kSceneUpdate)) {"""
t = t.replace(anchor, new_code, 1)

anchor_end = """wots2_scene_ended = true;
                                break;
                            }
                            wots2_acc -= (1.0 / 30.0);"""
new_code_end = """wots2_scene_ended = true;
                                break;
                            }
                            auto t1_upd = std::chrono::high_resolution_clock::now();
                            wots2_timing_upd += std::chrono::duration<double, std::milli>(t1_upd - t0_upd).count();
                            wots2_acc -= (1.0 / 30.0);"""
t = t.replace(anchor_end, new_code_end, 1)

# Wir fügen die Timing-Variablen am Anfang der Funktion ein
fn_anchor = "[[noreturn]] void App_Run(App* app) {"
if fn_anchor in t and "wots2_timing_upd" not in t:
    t = t.replace(fn_anchor, fn_anchor + "\n    static double wots2_timing_upd = 0.0;")

# Includes hinzufügen
if "#include <chrono>" not in t:
    t = t.replace('#include "engine/app.h"', '#include <chrono>\n#include "engine/app.h"')

p.write_text(t)
print("OK: App-Timing an Deltatime angepasst.")
