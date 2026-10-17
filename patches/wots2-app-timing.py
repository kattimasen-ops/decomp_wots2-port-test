#!/usr/bin/env python3
# wots2-app-timing.py (v1)
# Instruments src/engine/app.cpp with [atiming] output every 30 frames.
# Activate with WOTS2_ATIMING=1; unset or 0 disables (compile-time no-op overhead ~1-2 us/frame).
# Idempotent: detects /* WOTS2_ATIMING_V1 */ marker.
# Fails loudly (exit != 0) if any anchor is missing or ambiguous.

import sys
from pathlib import Path

PATH   = Path("src/engine/app.cpp")
MARKER = "/* WOTS2_ATIMING_V1 */"

HELPER = r'''/* WOTS2_ATIMING_V1 */
#include <chrono>
#include <cstdio>
#include <cstdlib>

static int wots2_atiming_on = -1;
static inline int Wots2_ATiming_On(void) {
    if (wots2_atiming_on < 0) {
        const char* v = getenv("WOTS2_ATIMING");
        wots2_atiming_on = (v && v[0] == '1') ? 1 : 0;
    }
    return wots2_atiming_on;
}
static inline double Wots2_NowMs(void) {
    using namespace std::chrono;
    return (double)duration_cast<nanoseconds>(steady_clock::now().time_since_epoch()).count() / 1e6;
}

enum {
    WOTS2_AT_PAD, WOTS2_AT_BEGIN, WOTS2_AT_BGM, WOTS2_AT_WINUPD,
    WOTS2_AT_UPD, WOTS2_AT_CLEAR, WOTS2_AT_VU1, WOTS2_AT_CAM,
    WOTS2_AT_DRAW, WOTS2_AT_WINDRAW, WOTS2_AT_FX, WOTS2_AT_LOADING,
    WOTS2_AT_END, WOTS2_AT_SYNC, WOTS2_AT_SWAP, WOTS2_AT_DISP,
    WOTS2_AT_COUNT
};
static double wots2_at_acc[WOTS2_AT_COUNT];
static int    wots2_at_frames = 0;
static const char* const wots2_at_names[WOTS2_AT_COUNT] = {
    "pad","begin","bgm","winUpd","upd","clear","vu1","cam",
    "draw","winDraw","fx","loading","end","sync","swap","disp"
};
static inline void Wots2_AT_Add(int b, double ms) {
    if (Wots2_ATiming_On()) wots2_at_acc[b] += ms;
}
static void Wots2_AT_Flush(void) {
    if (!Wots2_ATiming_On()) return;
    if (++wots2_at_frames < 30) return;
    double total = 0.0;
    for (int i = 0; i < WOTS2_AT_COUNT; i++) total += wots2_at_acc[i];
    fprintf(stdout, "[atiming] %df avg: total=%.2f", wots2_at_frames, total / wots2_at_frames);
    for (int i = 0; i < WOTS2_AT_COUNT; i++)
        fprintf(stdout, " %s=%.2f", wots2_at_names[i], wots2_at_acc[i] / wots2_at_frames);
    fprintf(stdout, "\n");
    fflush(stdout);
    for (int i = 0; i < WOTS2_AT_COUNT; i++) wots2_at_acc[i] = 0.0;
    wots2_at_frames = 0;
}
/* /WOTS2_ATIMING_V1 */
'''

OLD_LOOP_HEAD = """                    PadMgr_Poll(PadMgr_Get());
                    GsDevice_BeginFrame(dev);
                    T0_COUNT = 0;
                    Bgm_ReapFinished();
                    WindowMgr_Update(*gWindowMgr);
"""

NEW_LOOP_HEAD = """                    { double t;
                      t = Wots2_NowMs(); PadMgr_Poll(PadMgr_Get());       Wots2_AT_Add(WOTS2_AT_PAD,    Wots2_NowMs() - t);
                      t = Wots2_NowMs(); GsDevice_BeginFrame(dev);        Wots2_AT_Add(WOTS2_AT_BEGIN,  Wots2_NowMs() - t);
                      T0_COUNT = 0;
                      t = Wots2_NowMs(); Bgm_ReapFinished();              Wots2_AT_Add(WOTS2_AT_BGM,    Wots2_NowMs() - t);
                      t = Wots2_NowMs(); WindowMgr_Update(*gWindowMgr);   Wots2_AT_Add(WOTS2_AT_WINUPD, Wots2_NowMs() - t);
                    }
"""

OLD_UPDATE = """                    // (Native: the level editor holds the game still.)
                    if (!Native_EditorPaused() && !SceneCall<int>(SceneOf(app->scene), kSceneUpdate))
                        break;
                    App_RenderFrame(app);
"""

NEW_UPDATE = """                    // (Native: the level editor holds the game still.)
                    { double t; int r;
                      t = Wots2_NowMs();
                      r = Native_EditorPaused() ? 1 : SceneCall<int>(SceneOf(app->scene), kSceneUpdate);
                      Wots2_AT_Add(WOTS2_AT_UPD, Wots2_NowMs() - t);
                      if (!r) break;
                    }
                    App_RenderFrame(app);
"""

OLD_RENDER = """int App_RenderFrame(App* app) {
    GsDevice* dev = *gGsDevice;

    GsDevice_ClearScreenColor(dev, *gClearColor);
    GsDevice_SetVu1Program(dev, 1);
    Camera_Apply(*gCamera, dev);

    int result = SceneCall<int>(SceneOf(app->scene), kSceneDraw);

    WindowMgr_Draw(*gWindowMgr, dev, *gFont);
    RenderMgr_DrawEffects(*gRenderMgrPtr);
    if (*gLoadingActive)
        App_DrawLoadingText(app);

    Profiler_End(*gProfiler);
    GsDevice_EndFrame(dev);
    app->drawTicks = T0_COUNT;
    Profiler_Begin(*gProfiler);
    sceGsSyncPath(0, 0);
    app->syncTicks = T0_COUNT;

    GsDevice_SwapBuffers(dev, 0);
    GsDevice_SetDisplay(dev, 0x80, 1, 1);
    ++*gFrameCount;
    return result;
}
"""

NEW_RENDER = """int App_RenderFrame(App* app) {
    GsDevice* dev = *gGsDevice;
    double t;

    t = Wots2_NowMs(); GsDevice_ClearScreenColor(dev, *gClearColor);
    Wots2_AT_Add(WOTS2_AT_CLEAR, Wots2_NowMs() - t);

    t = Wots2_NowMs(); GsDevice_SetVu1Program(dev, 1);
    Wots2_AT_Add(WOTS2_AT_VU1, Wots2_NowMs() - t);

    t = Wots2_NowMs(); Camera_Apply(*gCamera, dev);
    Wots2_AT_Add(WOTS2_AT_CAM, Wots2_NowMs() - t);

    t = Wots2_NowMs();
    int result = SceneCall<int>(SceneOf(app->scene), kSceneDraw);
    Wots2_AT_Add(WOTS2_AT_DRAW, Wots2_NowMs() - t);

    t = Wots2_NowMs(); WindowMgr_Draw(*gWindowMgr, dev, *gFont);
    Wots2_AT_Add(WOTS2_AT_WINDRAW, Wots2_NowMs() - t);

    t = Wots2_NowMs(); RenderMgr_DrawEffects(*gRenderMgrPtr);
    Wots2_AT_Add(WOTS2_AT_FX, Wots2_NowMs() - t);

    t = Wots2_NowMs();
    if (*gLoadingActive)
        App_DrawLoadingText(app);
    Wots2_AT_Add(WOTS2_AT_LOADING, Wots2_NowMs() - t);

    Profiler_End(*gProfiler);

    t = Wots2_NowMs(); GsDevice_EndFrame(dev);
    Wots2_AT_Add(WOTS2_AT_END, Wots2_NowMs() - t);

    app->drawTicks = T0_COUNT;
    Profiler_Begin(*gProfiler);

    t = Wots2_NowMs(); sceGsSyncPath(0, 0);
    Wots2_AT_Add(WOTS2_AT_SYNC, Wots2_NowMs() - t);
    app->syncTicks = T0_COUNT;

    t = Wots2_NowMs(); GsDevice_SwapBuffers(dev, 0);
    Wots2_AT_Add(WOTS2_AT_SWAP, Wots2_NowMs() - t);

    t = Wots2_NowMs(); GsDevice_SetDisplay(dev, 0x80, 1, 1);
    Wots2_AT_Add(WOTS2_AT_DISP, Wots2_NowMs() - t);

    ++*gFrameCount;
    Wots2_AT_Flush();
    return result;
}
"""

def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)

def main():
    if not PATH.exists():
        fail(f"{PATH} not found")
    src = PATH.read_text()

    if MARKER in src:
        print(f"Already patched ({MARKER} present), skipping")
        return 0

    anchor = '#include "engine/window.h"\n'
    if src.count(anchor) != 1:
        fail(f'anchor "window.h include" count={src.count(anchor)}, expected 1')
    src = src.replace(anchor, anchor + "\n" + HELPER, 1)

    for name, old in [("OLD_LOOP_HEAD", OLD_LOOP_HEAD),
                      ("OLD_UPDATE",    OLD_UPDATE),
                      ("OLD_RENDER",    OLD_RENDER)]:
        c = src.count(old)
        if c != 1:
            fail(f'{name} count={c}, expected 1')

    src = src.replace(OLD_LOOP_HEAD, NEW_LOOP_HEAD, 1)
    src = src.replace(OLD_UPDATE,    NEW_UPDATE,    1)
    src = src.replace(OLD_RENDER,    NEW_RENDER,    1)

    PATH.write_text(src)
    print(f"Patched {PATH}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
