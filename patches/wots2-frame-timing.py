#!/usr/bin/env python3
"""patches/wots2-frame-timing.py  (v1)

Misst mit CLOCK_MONOTONIC die Zeit in jedem CharaMgr-Schritt und loggt
alle 30 Frames eine [timing]-Zeile. Kein Eingriff in die Spiellogik.

Abschaltbar mit WOTS2_TIMING=0 (Default: an, weil der Overhead minimal ist:
ein Paar clock_gettime-Aufrufe pro Step, ~1 µs pro Frame).

Rollback: WOTS2_TIMING=0 in der WOTS2.sh.

Idempotent: Marker wots2_frame_timing_v1.
"""
import sys, pathlib, re

MARKER = "wots2_frame_timing_v1"

HELPER = r'''
// [WOTS2-PORT] wots2_frame_timing_v1
// Misst die Zeit in jedem CharaMgr-Schritt. Loggt alle 30 Frames eine
// [timing]-Zeile. Kein Eingriff in die Spiellogik.
#include <ctime>
static u64 wots2_timing_now_ns() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (u64)ts.tv_sec * 1000000000ULL + (u64)ts.tv_nsec;
}
static u64 wots2_timing_update = 0, wots2_timing_stepA = 0, wots2_timing_stepB = 0;
static u64 wots2_timing_stepC = 0, wots2_timing_stepD = 0, wots2_timing_stepMap = 0;
static u64 wots2_timing_draw = 0;
static int wots2_timing_frames = 0;
static bool wots2_timing_enabled() {
    static const bool on = getenv("WOTS2_TIMING") != nullptr;
    return on;
}
static void wots2_timing_report() {
    if (!wots2_timing_enabled())
        return;
    if (++wots2_timing_frames < 30)
        return;
    const u64 total = wots2_timing_update + wots2_timing_stepA + wots2_timing_stepB +
                      wots2_timing_stepC + wots2_timing_stepD + wots2_timing_stepMap +
                      wots2_timing_draw;
    printf("[timing] %d frames: update=%.2f stepA=%.2f stepB=%.2f stepC=%.2f stepD=%.2f stepMap=%.2f draw=%.2f total=%.2f ms\n",
           wots2_timing_frames,
           wots2_timing_update / 1e6, wots2_timing_stepA / 1e6, wots2_timing_stepB / 1e6,
           wots2_timing_stepC / 1e6, wots2_timing_stepD / 1e6, wots2_timing_stepMap / 1e6,
           wots2_timing_draw / 1e6, total / 1e6);
    fflush(stdout);
    wots2_timing_update = wots2_timing_stepA = wots2_timing_stepB = 0;
    wots2_timing_stepC = wots2_timing_stepD = wots2_timing_stepMap = 0;
    wots2_timing_draw = 0;
    wots2_timing_frames = 0;
}
'''


def timed_wrap(text, sig_pattern, varname):
    m = re.search(sig_pattern, text)
    if not m:
        return text, False
    start = m.end()
    depth = 1
    end = start
    while end < len(text) and depth > 0:
        c = text[end]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        end += 1
    body = text[start:end - 1]
    wrapped = (
        "\n    const u64 _wts2_t0 = wots2_timing_enabled() ? wots2_timing_now_ns() : 0;\n"
        + body +
        "\n    if (wots2_timing_enabled()) " + varname + " += wots2_timing_now_ns() - _wts2_t0;\n"
    )
    return text[:start] + wrapped + text[end - 1:], True


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text(encoding="utf-8", errors="replace")
    if MARKER in t:
        print("  bereits gepatcht.")
        return
    if "#include <cstddef>" not in t:
        print("  FEHLER: '#include <cstddef>' nicht gefunden.")
        sys.exit(1)
    t = t.replace("#include <cstddef>", HELPER + "\n#include <cstddef>", 1)

    steps = [
        ("CharaMgr_Update",    "wots2_timing_update"),
        ("CharaMgr_StepA",     "wots2_timing_stepA"),
        ("CharaMgr_StepB",     "wots2_timing_stepB"),
        ("CharaMgr_StepC",     "wots2_timing_stepC"),
        ("CharaMgr_StepD",     "wots2_timing_stepD"),
        ("CharaMgr_StepMap",   "wots2_timing_stepMap"),
    ]
    for fname, varname in steps:
        t, ok = timed_wrap(t, r'void ' + fname + r'\(CharaMgr\* mgr[^)]*\)\s*\{', varname)
        if not ok:
            print(f"  FEHLER: {fname} nicht gefunden.")
            sys.exit(1)
        print(f"  {fname}: Zeitmessung eingebaut.")

    t, ok = timed_wrap(t, r'void CharaMgr_Draw\(CharaMgr\* mgr, int pass\)\s*\{', "wots2_timing_draw")
    if not ok:
        print("  FEHLER: CharaMgr_Draw nicht gefunden.")
        sys.exit(1)
    print("  CharaMgr_Draw: Zeitmessung eingebaut.")

    # Add the report call at the end of CharaMgr_Draw
    m = re.search(r'(void CharaMgr_Draw\(CharaMgr\* mgr, int pass\)\s*\{.*?)\n\s*if \(wots2_timing_enabled\(\)\) wots2_timing_draw', t, re.DOTALL)
    if m:
        insert_at = m.end()
        # find end of the closing `}` of the Draw function
        search_from = insert_at
        depth = 0
        i = search_from
        while i < len(t):
            if t[i] == '{':
                depth += 1
            elif t[i] == '}':
                if depth == 0:
                    break
                depth -= 1
            i += 1
        t = t[:i] + "\n    wots2_timing_report();\n" + t[i:]

    t += "\n/* " + MARKER + " */\n"
    p.write_text(t, encoding="utf-8")
    print("  Timing-Patch eingebaut.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "src/game/chara_mgr.cpp"
    if not target.endswith(".cpp"):
        target = target.rstrip("/") + "/src/game/chara_mgr.cpp"
    print(f"Patche {target}")
    patch(target)
    print("Fertig.")
