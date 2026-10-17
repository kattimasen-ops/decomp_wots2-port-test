#!/usr/bin/env python3
"""patches/wots2-gs-frame-timing.py  (v1)

Zerlegt die Frame-Zeit in die drei Phasen record / play / swap und
misst in play() separat lighting, post und loop. Misst zusaetzlich in
model.cpp, wie viel Zeit Model::draw fuer Map-, NPC- und Objekt-Batches
braucht.

Der Env-Var ist derselbe wie beim bestehenden chara_mgr-Timing:
WOTS2_TIMING=1 aktiviert alle drei Timer ([timing], [gtiming], [mtiming]).

Idempotent (Marker wots2_gs_frame_timing_v1). Bricht ab, wenn in gs.cpp
kein einziger Anker gefunden wird — ein Build, der vorgibt zu messen,
aber nichts tut, waere schlimmer als kein Build.

Patcht:
  - src/hal/gs.cpp
  - src/native/model.cpp

Marker: wots2_gs_frame_timing_v1
"""

import sys
import pathlib

MARKER = "wots2_gs_frame_timing_v1"

GS_HELPER = r'''
// [WOTS2-PORT] wots2_gs_frame_timing_v1
// Frame-Timing fuer hal::gs: record/play/swap + lighting/post/loop.
// Aktiv, wenn WOTS2_TIMING gesetzt ist (gleicher Env-Var wie chara_mgr).
#include <ctime>
static u64 wots2_g_t_now_ns() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (u64)ts.tv_sec * 1000000000ULL + (u64)ts.tv_nsec;
}
static bool wots2_g_t_enabled() {
    static const bool on = getenv("WOTS2_TIMING") != nullptr;
    return on;
}
static u64 wots2_g_t_record_start = 0;
static u64 wots2_g_t_record = 0, wots2_g_t_play = 0, wots2_g_t_lighting = 0;
static u64 wots2_g_t_post = 0, wots2_g_t_swap = 0;
static int wots2_g_t_frame_count = 0;
static void wots2_g_t_report() {
    if (!wots2_g_t_enabled()) return;
    if (++wots2_g_t_frame_count < 30) return;
    const u64 loop = wots2_g_t_play > (wots2_g_t_lighting + wots2_g_t_post)
                   ? wots2_g_t_play - wots2_g_t_lighting - wots2_g_t_post : 0;
    printf("[gtiming] %d frames: record=%.2f play=%.2f lighting=%.2f post=%.2f loop=%.2f swap=%.2f total=%.2f ms\n",
           wots2_g_t_frame_count,
           wots2_g_t_record / 1e6, wots2_g_t_play / 1e6, wots2_g_t_lighting / 1e6,
           wots2_g_t_post / 1e6, loop / 1e6, wots2_g_t_swap / 1e6,
           (wots2_g_t_record + wots2_g_t_play + wots2_g_t_swap) / 1e6);
    fflush(stdout);
    wots2_g_t_record = wots2_g_t_play = wots2_g_t_lighting = 0;
    wots2_g_t_post = wots2_g_t_swap = 0;
    wots2_g_t_frame_count = 0;
}
'''

MODEL_HELPER = r'''
// [WOTS2-PORT] wots2_gs_frame_timing_v1 (mtiming)
// Misst Model::draw separat fuer Map-, NPC- und Objekt-Batches.
// Aktiv, wenn WOTS2_TIMING gesetzt ist (gleicher Env-Var wie gs).
#include <ctime>
static u64 wots2_mt_now_ns() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (u64)ts.tv_sec * 1000000000ULL + (u64)ts.tv_nsec;
}
static bool wots2_mt_enabled() {
    static const bool on = getenv("WOTS2_TIMING") != nullptr;
    return on;
}
static u64 wots2_mt_map = 0, wots2_mt_npc = 0, wots2_mt_other = 0;
static int wots2_mt_frame_count = 0;
static void wots2_mt_report() {
    if (!wots2_mt_enabled()) return;
    if (++wots2_mt_frame_count < 30) return;
    printf("[mtiming] %d frames: map=%.2f npc=%.2f other=%.2f total=%.2f ms\n",
           wots2_mt_frame_count,
           wots2_mt_map / 1e6, wots2_mt_npc / 1e6, wots2_mt_other / 1e6,
           (wots2_mt_map + wots2_mt_npc + wots2_mt_other) / 1e6);
    fflush(stdout);
    wots2_mt_map = wots2_mt_npc = wots2_mt_other = 0;
    wots2_mt_frame_count = 0;
}
'''


def find_anchor(text, pattern):
    """Sucht `pattern` (ein Substring) und gibt seinen Offset zurueck oder -1."""
    i = text.find(pattern)
    return i


def find_block_end(text, start):
    """Findet das schliessende `}` eines Blocks, der bei `start` (auf `{` zeigend) oeffnet."""
    if text[start] != '{':
        return -1
    depth = 0
    i = start
    while i < len(text):
        c = text[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def patch_gs(path):
    p = pathlib.Path(path)
    t = p.read_text(encoding="utf-8", errors="replace")
    if MARKER + " (gs)" in t:
        print("  gs.cpp: bereits gepatcht.")
        return True

    if "#include <ctime>" not in t:
        if "#include <cstdio>" in t:
            t = t.replace("#include <cstdio>", "#include <cstdio>\n#include <ctime>", 1)
        else:
            print("  gs.cpp: FEHLER: kein <cstdio>-Include als Anker gefunden.")
            return False

    if "#include <cstring>" in t:
        t = t.replace("#include <cstring>", GS_HELPER + "\n#include <cstring>", 1)
    else:
        print("  gs.cpp: FEHLER: kein <cstring>-Include als Anker fuer HELPER.")
        return False

    found = []

    # 1. begin_frame: record_start setzen
    anchor = "void begin_frame() {"
    i = find_anchor(t, anchor)
    if i < 0:
        print("  gs.cpp: WARNUNG: begin_frame nicht gefunden.")
    else:
        insert_at = i + len(anchor)
        t = t[:insert_at] + "\n    wots2_g_t_record_start = wots2_g_t_enabled() ? wots2_g_t_now_ns() : 0;" + t[insert_at:]
        found.append("begin_frame")

    # 2. play: Zeit um den Body
    anchor = "static void play(const Frame& f, const Frame* before, float t) {"
    i = find_anchor(t, anchor)
    if i < 0:
        print("  gs.cpp: WARNUNG: play() nicht gefunden.")
    else:
        body_open = t.index("{", i)
        body_close = find_block_end(t, body_open)
        if body_close < 0:
            print("  gs.cpp: WARNUNG: play()-Blockende nicht gefunden.")
        else:
            t = (t[:body_open + 1]
                 + "\n    const u64 _wots2_g_play_t0 = wots2_g_t_enabled() ? wots2_g_t_now_ns() : 0;"
                 + t[body_open + 1:body_close]
                 + "\n    if (wots2_g_t_enabled()) wots2_g_t_play += wots2_g_t_now_ns() - _wots2_g_play_t0;"
                 + t[body_close:])
            found.append("play")

    # 3. lighting_begin: Zeit um den Body (mit zwei Returns)
    anchor = "static void lighting_begin(const Frame& f, const Frame* before, float t) {"
    i = find_anchor(t, anchor)
    if i < 0:
        print("  gs.cpp: WARNUNG: lighting_begin nicht gefunden.")
    else:
        body_open = t.index("{", i)
        body_close = find_block_end(t, body_open)
        if body_close < 0:
            print("  gs.cpp: WARNUNG: lighting_begin-Blockende nicht gefunden.")
        else:
            body = t[body_open + 1:body_close]
            # Vor dem ersten `return;` messen, und am Ende.
            body = body.replace(
                "    if (!s_litFrame)\n        return;",
                "    if (!s_litFrame) {\n        if (wots2_g_t_enabled()) wots2_g_t_lighting += wots2_g_t_now_ns() - _wots2_g_lighting_t0;\n        return;\n    }",
                1)
            t = (t[:body_open + 1]
                 + "\n    const u64 _wots2_g_lighting_t0 = wots2_g_t_enabled() ? wots2_g_t_now_ns() : 0;"
                 + body
                 + "\n    if (wots2_g_t_enabled()) wots2_g_t_lighting += wots2_g_t_now_ns() - _wots2_g_lighting_t0;"
                 + t[body_close:])
            found.append("lighting_begin")

    # 4. post_pass: Zeit um den Body
    anchor = "static void post_pass(const Frame& f) {"
    i = find_anchor(t, anchor)
    if i < 0:
        print("  gs.cpp: WARNUNG: post_pass nicht gefunden.")
    else:
        body_open = t.index("{", i)
        body_close = find_block_end(t, body_open)
        if body_close < 0:
            print("  gs.cpp: WARNUNG: post_pass-Blockende nicht gefunden.")
        else:
            body = t[body_open + 1:body_close]
            body = body.replace(
                "    if (!(s_light.ao || s_light.bloom > 0.0f || s_light.grade || s_light.dof > 0.0f || s_light.godRays > 0.0f))\n        return;",
                "    if (!(s_light.ao || s_light.bloom > 0.0f || s_light.grade || s_light.dof > 0.0f || s_light.godRays > 0.0f)) {\n        if (wots2_g_t_enabled()) wots2_g_t_post += wots2_g_t_now_ns() - _wots2_g_post_t0;\n        return;\n    }",
                1)
            t = (t[:body_open + 1]
                 + "\n    const u64 _wots2_g_post_t0 = wots2_g_t_enabled() ? wots2_g_t_now_ns() : 0;"
                 + body
                 + "\n    if (wots2_g_t_enabled()) wots2_g_t_post += wots2_g_t_now_ns() - _wots2_g_post_t0;"
                 + t[body_close:])
            found.append("post_pass")

    # 5. present: swap messen
    anchor = "static void present() {"
    i = find_anchor(t, anchor)
    if i < 0:
        print("  gs.cpp: WARNUNG: present nicht gefunden.")
    else:
        body_open = t.index("{", i)
        body_close = find_block_end(t, body_open)
        if body_close < 0:
            print("  gs.cpp: WARNUNG: present-Blockende nicht gefunden.")
        else:
            t = (t[:body_open + 1]
                 + "\n    const u64 _wots2_g_swap_t0 = wots2_g_t_enabled() ? wots2_g_t_now_ns() : 0;"
                 + t[body_open + 1:body_close]
                 + "\n    if (wots2_g_t_enabled()) wots2_g_t_swap += wots2_g_t_now_ns() - _wots2_g_swap_t0;"
                 + t[body_close:])
            found.append("present")

    # 6. end_frame: record abschliessen und Report ausloesen
    anchor = "void end_frame() {"
    i = find_anchor(t, anchor)
    if i < 0:
        print("  gs.cpp: WARNUNG: end_frame nicht gefunden.")
    else:
        body_open = t.index("{", i)
        body_close = find_block_end(t, body_open)
        if body_close < 0:
            print("  gs.cpp: WARNUNG: end_frame-Blockende nicht gefunden.")
        else:
            body = t[body_open + 1:body_close]
            # record abschliessen: am Anfang des end_frame-Bodys
            body = ("\n    if (wots2_g_t_enabled() && wots2_g_t_record_start) {\n"
                    "        wots2_g_t_record += wots2_g_t_now_ns() - wots2_g_t_record_start;\n"
                    "        wots2_g_t_record_start = 0;\n"
                    "    }" + body)
            # report: am Ende des end_frame-Bodys
            body = body + "\n    if (wots2_g_t_enabled()) wots2_g_t_report();\n"
            t = t[:body_open + 1] + body + t[body_close:]
            found.append("end_frame")

    if not found:
        print("  gs.cpp: FEHLER: kein einziger Anker gefunden.")
        return False

    t += "\n/* " + MARKER + " (gs) */\n"
    p.write_text(t, encoding="utf-8")
    print(f"  gs.cpp: {len(found)} Anker gepatcht ({', '.join(found)})")
    return True


def patch_model(path):
    p = pathlib.Path(path)
    t = p.read_text(encoding="utf-8", errors="replace")
    if MARKER + " (model)" in t:
        print("  model.cpp: bereits gepatcht.")
        return True

    if "#include <ctime>" not in t:
        if "#include <cstdio>" in t:
            t = t.replace("#include <cstdio>", "#include <cstdio>\n#include <ctime>", 1)
        else:
            print("  model.cpp: FEHLER: kein <cstdio>-Include.")
            return False

    if "#include <cstdlib>" in t:
        t = t.replace("#include <cstdlib>", MODEL_HELPER + "\n#include <cstdlib>", 1)
    else:
        print("  model.cpp: FEHLER: kein <cstdlib>-Include als Anker.")
        return False

    anchor = "void Model::draw(const float* pose, sprites::Sheet* shared, const Lighting* light) {"
    i = find_anchor(t, anchor)
    if i < 0:
        print("  model.cpp: WARNUNG: Model::draw nicht gefunden.")
        return False
    body_open = t.index("{", i)
    body_close = find_block_end(t, body_open)
    if body_close < 0:
        print("  model.cpp: WARNUNG: Model::draw-Blockende nicht gefunden.")
        return False

    t = (t[:body_open + 1]
         + "\n    const u64 _wots2_mt_t0 = wots2_mt_enabled() ? wots2_mt_now_ns() : 0;\n"
         + "    u64* _wots2_mt_target = nullptr;\n"
         + "    if (wots2_mt_enabled()) {\n"
         + "        if (pose == nullptr && light == nullptr) _wots2_mt_target = &wots2_mt_map;\n"
         + "        else if (pose != nullptr) _wots2_mt_target = &wots2_mt_npc;\n"
         + "        else _wots2_mt_target = &wots2_mt_other;\n"
         + "    }"
         + t[body_open + 1:body_close]
         + "\n    if (_wots2_mt_target) *_wots2_mt_target += wots2_mt_now_ns() - _wots2_mt_t0;\n"
         + "    if (wots2_mt_enabled()) wots2_mt_report();"
         + t[body_close:])

    t += "\n/* " + MARKER + " (model) */\n"
    p.write_text(t, encoding="utf-8")
    print("  model.cpp: Model::draw gepatcht.")
    return True


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "."
    root = pathlib.Path(arg.rstrip("/"))
    if not root.is_dir():
        print(f"FEHLER: {root} ist kein Verzeichnis.", file=sys.stderr)
        sys.exit(1)

    gs = root / "src/hal/gs.cpp"
    model = root / "src/native/model.cpp"
    if not gs.is_file():
        print(f"FEHLER: {gs} fehlt.", file=sys.stderr)
        sys.exit(1)
    if not model.is_file():
        print(f"FEHLER: {model} fehlt.", file=sys.stderr)
        sys.exit(1)

    print(f"Patche {gs}")
    if not patch_gs(gs):
        print("gs.cpp-Patch fehlgeschlagen; build stoppt.", file=sys.stderr)
        sys.exit(1)

    print(f"Patche {model}")
    if not patch_model(model):
        print("model.cpp-Patch fehlgeschlagen; build stoppt.", file=sys.stderr)
        sys.exit(1)

    print("Fertig.")


if __name__ == "__main__":
    main()
