#!/usr/bin/env python3
"""Fügt in app.cpp einen Fixed-Timestep-Akkumulator ein (beseitigt die Zeitlupe)."""
import sys, re, pathlib

p = pathlib.Path(sys.argv[1])
t = p.read_text()

anchor = "for (;;) {\n                    PadMgr_Poll(PadMgr_Get());"
if anchor not in t:
    print("FEHLER: App_Run-Schleife nicht gefunden.", file=sys.stderr)
    sys.exit(1)

# Akkumulator-basierte Update-Schleife
new_loop = r"""// Fixed-timestep accumulator (native port)
                double acc = 0.0;
                Uint64 last = SDL_GetPerformanceCounter();
                const double step = 1.0 / 30.0;
                for (;;) {
                    Uint64 now = SDL_GetPerformanceCounter();
                    double frame = (double)(now - last) / (double)SDL_GetPerformanceFrequency();
                    last = now;
                    if (frame > 0.25) frame = 0.25; // Spiral of death verhindern
                    acc += frame;
                    while (acc >= step) {
                        PadMgr_Poll(PadMgr_Get());
                        GsDevice_BeginFrame(dev);
                        T0_COUNT = 0;
                        Bgm_ReapFinished();
                        WindowMgr_Update(*gWindowMgr);
                        if (SceneOf(app->scene)->hasQueuedScene && !app->queuedScene) {
                            app->queuedScene = guest::addr(SceneCall<Scene*>(SceneOf(app->scene), kSceneGetNextScene));
                            SceneCall<int>(SceneOf(app->queuedScene), kSceneStart);
                        }
                        if (!Native_EditorPaused() && !SceneCall<int>(SceneOf(app->scene), kSceneUpdate))
                            break;
                        acc -= step;
                    }
                    App_RenderFrame(app);
                }"""

t = t.replace(anchor, new_loop, 1)
p.write_text(t)
print("OK: Fixed-Timestep-Akkumulator in app.cpp eingefügt.")
