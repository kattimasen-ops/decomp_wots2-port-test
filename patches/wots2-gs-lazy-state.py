#!/usr/bin/env python3
"""
patches/wots2-gs-lazy-state.py   (v1)

Weniger GL-Aufrufe beim Wechsel zwischen 2D und 3D in src/hal/gs.cpp.

Im Frame-Replay (play) startet jede 3D-Ansicht mit Begin3D -> state_3d() und
endet mit End3D -> state_2d(). hle_chara.cpp ruft begin_3d() je Figur mehrfach
auf (Koerper, Ausruestung, Schatten, Props), also viele Paare pro Frame. Jedes
Paar kostet rund 25 GL-Aufrufe, darunter zwei glUseProgram:

  state_3d: glUseProgram, 6 x glUniform*, VAO, VBO, Tiefentest an, Tiefenfunktion, Tiefenmaske
  state_2d: Polygon-Offset aus, Tiefenmaske, glUniform, Tiefentest aus, glUseProgram, VAO, VBO

Neu:
  * End3D macht nur noch die billigen Teile von state_2d() sofort (bias(0),
    overlay(false)). Programm, VAO, VBO und Tiefentest wechseln erst, wenn
    wirklich eine 2D-Operation kommt (wots2_ensure_2d()).
  * Folgt auf eine 3D-Ansicht gleich wieder eine mit derselben 'kind', laeuft
    state_3d() auf einem Schnellpfad: nur das Noetige (mvp, geaenderte
    Uniforms, Tiefenmaske) wird gesetzt. Bei jeder anderen kind laeuft der
    unveraenderte Original-Pfad.
  * Ein Zaehler schreibt mit WOTS2_TIMING=1 alle 30 Frames eine Zeile
    '[gcount] begin3d=... fast=... state2d_real=...'.

Wichtig fuer die Reihenfolge in der .yml: Dieser Patch muss VOR
wots2-gs-backface-cull.py laufen. Er prueft den Rumpf von state_3d() streng
und bricht sonst mit PATCH-FEHLER ab (ein fremder Eingriff in state_3d koennte
im Schnellpfad uebersprungen werden).

Notausschalter: WOTS2_NO_LAZYSTATE=1 (Originalverhalten).

Idempotent: Marker 'wots2_gs_lazy_state_v1'.
Zieldatei: src/hal/gs.cpp
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wots2_patchlib as pl  # noqa: E402

MARKER = "wots2_gs_lazy_state_v1"

STATE3D_SIG = r'static\s+void\s+state_3d\s*\(\s*const\s+float\s*\*\s*mvp\s*,\s*float\s+xscale\s*,\s*int\s+kind\s*=\s*0\s*\)'
STATE2D_SIG = r'static\s+void\s+state_2d\s*\(\s*\)'
PLAY_SIG = r'static\s+void\s+play\s*\(\s*const\s+Frame\s*&\s*f\s*,\s*const\s+Frame\s*\*\s*before\s*,\s*float\s+t\s*\)'
END_SIG = r'^void\s+end_frame\s*\(\s*\)'

# So sieht der state_3d-Rumpf im Original aus (Whitespace egal). Erlaubt ist auch die
# Variante mit der Zeile von wots2-gs-backface-cull.py am Ende.
EXPECTED_BODY = '''
    s_viewDist = kind == (int)hal::gs::View::Map || kind == (int)hal::gs::View::Model;
    dist_buffers(s_viewDist);
    glUseProgram(s_program3d);
    glUniform1i(s_uKind, s_litFrame && !s_inTarget ? kind : 0);
    glUniformMatrix4fv(s_uMvp, 1, GL_FALSE, mvp);
    glUniform1f(s_uXScale, xscale);
    glUniform1f(s_uAlphaRef3d, 0.5f);
    glUniform4fv(s_uFog, 1, s_fog);
    glUniform3fv(s_uFogColor, 1, s_fogColor);
    glBindVertexArray(s_vao3d);
    glBindBuffer(GL_ARRAY_BUFFER, s_vbo3d);
    glEnable(GL_DEPTH_TEST);
    glDepthFunc(GL_LEQUAL);
    glDepthMask(GL_TRUE);
'''
EXPECTED_STATE2D = '''
    s_viewDist = false;
    bias(0);
    overlay(false);
    glDisable(GL_DEPTH_TEST);
    glUseProgram(s_program);
    glBindVertexArray(s_vao);
    glBindBuffer(GL_ARRAY_BUFFER, s_vbo);
'''


def norm(s):
    """Whitespace und Kommentare entfernen, damit nur der Code verglichen wird."""
    s = re.sub(r'//[^\n]*', '', s)
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    return re.sub(r'\s+', '', s)


HELPER1 = '''// wots2_gs_lazy_state_v1 (wots2-gs-lazy-state.py)
static inline bool wots2_lazy_state_on() {
    static const bool on = (getenv("WOTS2_NO_LAZYSTATE") == nullptr);
    return on;
}
static bool  s_wots2In3d = false;       // Programm, VAO, VBO und Tiefentest des 3D-Zustands sind gesetzt
static bool  s_wots2Pend2d = false;     // End3D hat den Wechsel in den 2D-Zustand aufgeschoben
static int   s_wots2LastKind = -1;      // kind des letzten vollen state_3d
static int   s_wots2UKind = -1;         // zuletzt gesetztes uKind
static float s_wots2XScale = -1.0f;
static float s_wots2Fog[4], s_wots2FogColor[3];
static long  s_wots2cBegin3d = 0, s_wots2cFast = 0, s_wots2c2dReal = 0;     // Zaehler fuer [gcount]

// Schnellpfad: laeuft schon der 3D-Zustand mit derselben kind, genuegt das Noetige.
static inline bool wots2_state3d_fast(const float* mvp, float xscale, int kind) {
    s_wots2cBegin3d++;
    if (!wots2_lazy_state_on() || !s_wots2In3d || kind != s_wots2LastKind)
        return false;
    s_wots2cFast++;
    s_wots2Pend2d = false;
    s_viewDist = kind == (int)hal::gs::View::Map || kind == (int)hal::gs::View::Model;
    dist_buffers(s_viewDist);
    const int uk = s_litFrame && !s_inTarget ? kind : 0;
    if (uk != s_wots2UKind) {
        glUniform1i(s_uKind, uk);
        s_wots2UKind = uk;
    }
    glUniformMatrix4fv(s_uMvp, 1, GL_FALSE, mvp);
    if (xscale != s_wots2XScale) {
        glUniform1f(s_uXScale, xscale);
        s_wots2XScale = xscale;
    }
    glUniform1f(s_uAlphaRef3d, 0.5f);
    if (memcmp(s_fog, s_wots2Fog, sizeof(s_wots2Fog)) != 0) {
        glUniform4fv(s_uFog, 1, s_fog);
        memcpy(s_wots2Fog, s_fog, sizeof(s_wots2Fog));
    }
    if (memcmp(s_fogColor, s_wots2FogColor, sizeof(s_wots2FogColor)) != 0) {
        glUniform3fv(s_uFogColor, 1, s_fogColor);
        memcpy(s_wots2FogColor, s_fogColor, sizeof(s_wots2FogColor));
    }
    glDepthMask(GL_TRUE);
    return true;
}
// Am Ende des vollen state_3d: merken, was jetzt gesetzt ist.
static inline void wots2_state3d_done(float xscale, int kind) {
    s_wots2In3d = wots2_lazy_state_on();
    s_wots2Pend2d = false;
    s_wots2LastKind = kind;
    s_wots2UKind = s_litFrame && !s_inTarget ? kind : 0;
    s_wots2XScale = xscale;
    memcpy(s_wots2Fog, s_fog, sizeof(s_wots2Fog));
    memcpy(s_wots2FogColor, s_fogColor, sizeof(s_wots2FogColor));
}
// Am Anfang des echten state_2d().
static inline void wots2_state2d_real() {
    s_wots2In3d = false;
    s_wots2Pend2d = false;
    s_wots2c2dReal++;
}

'''

HELPER2 = '''
// (wots2_gs_lazy_state_v1) Ende einer 3D-Ansicht: der Wechsel in den 2D-Zustand wird aufgeschoben.
static inline void wots2_end3d() {
    if (!wots2_lazy_state_on()) {
        state_2d();
        return;
    }
    s_viewDist = false;
    bias(0);
    overlay(false);
    s_wots2Pend2d = true;
}
static inline void wots2_ensure_2d() {
    if (s_wots2Pend2d) {
        s_wots2Pend2d = false;
        state_2d();
    }
}
'''

REPORT = '''// wots2_gs_lazy_state_v1: Zaehler alle 30 Frames (nur mit WOTS2_TIMING=1)
static void wots2_gcount_report() {
    static const bool on = (getenv("WOTS2_TIMING") != nullptr);
    if (!on || s_frame % 30 != 0)
        return;
    printf("[gcount] 30 frames: begin3d=%ld fast=%ld state2d_real=%ld\\n", s_wots2cBegin3d, s_wots2cFast, s_wots2c2dReal);
    fflush(stdout);
    s_wots2cBegin3d = s_wots2cFast = s_wots2c2dReal = 0;
}

'''


def insert_before_function(t, sig, text):
    hit = pl.find_function(t, sig)
    if hit is None:
        return None
    ins = hit[0]
    while True:                                 # Kommentarblock vor der Funktion zusammenlassen
        prev_end = ins - 1
        if prev_end < 0:
            break
        prev_start = t.rfind('\n', 0, prev_end) + 1
        if t[prev_start:prev_end].lstrip().startswith('//'):
            ins = prev_start
        else:
            break
    return t[:ins] + text + t[ins:]


def patch(path):
    p = pathlib.Path(path)
    if not p.exists():
        pl.fail('Zieldatei %s existiert nicht' % path)
        return
    t = p.read_text()
    if MARKER in t:
        print('  Lazy-State bereits vorhanden (Marker: %s).' % MARKER)
        return

    # ---------- Vorpruefung: alles muss passen, sonst wird nichts geschrieben ----------
    h3 = pl.find_function(t, STATE3D_SIG)
    h2 = pl.find_function(t, STATE2D_SIG)
    hp = pl.find_function(t, PLAY_SIG)
    he = pl.find_function(t, END_SIG)
    missing = [n for n, h in (('state_3d', h3), ('state_2d', h2), ('play', hp), ('end_frame', he)) if h is None]
    if missing:
        pl.fail('nicht gefunden: %s' % ', '.join(missing))
        return
    body3 = t[h3[1] + 1:h3[2] - 1]
    body2 = t[h2[1] + 1:h2[2] - 1]
    ok3 = norm(body3) in (norm(EXPECTED_BODY), norm(EXPECTED_BODY + '\n    wots2_cull_3d(kind);'))
    if not ok3:
        pl.fail('state_3d() sieht anders aus als erwartet (anderer Patch war davor?). Dieser Patch muss vor '
                'wots2-gs-backface-cull.py laufen und rechnet nur mit dem Original-Rumpf.')
        return
    if norm(body2) != norm(EXPECTED_STATE2D):
        pl.fail('state_2d() sieht anders aus als erwartet')
        return
    pbody = t[hp[1]:hp[2]]
    sites = {
        'End3D':    (r'(case\s+Op::End3D\s*:(?:\s*wots2_fade_reset\s*\(\s*\)\s*;)?\s*)state_2d\s*\(\s*\)\s*;', r'\1wots2_end3d();'),
        'AlphaRef': (r'(case\s+Op::AlphaRef\s*:)', r'\1\n            wots2_ensure_2d();'),
        'Draw2D':   (r'(case\s+Op::Draw2D\s*:\s*\{)', r'\1\n            wots2_ensure_2d();'),
        'Post':     (r'(case\s+Op::Post\s*:)', r'\1\n            wots2_ensure_2d();'),
    }
    new_pbody = pbody
    for name, (pat, rep) in sites.items():
        found = list(re.finditer(pat, new_pbody))
        if len(found) != 1:
            pl.fail('play(): case Op::%s: %d Treffer statt genau 1' % (name, len(found)))
            return
        new_pbody = re.sub(pat, rep, new_pbody, count=1)
    hook = pl.flex('debug_frame_hooks(); s_frame++;')
    ebody = t[he[1]:he[2]]
    mh = list(re.finditer(hook, ebody))
    if len(mh) != 1:
        pl.fail('end_frame: "debug_frame_hooks(); s_frame++;" %d Treffer statt genau 1' % len(mh))
        return

    # ---------- Schreiben (von hinten nach vorn, damit Positionen stimmen) ----------
    # 1. end_frame: Zaehler-Hook
    new_ebody = ebody[:mh[0].end()] + '\n    wots2_gcount_report();' + ebody[mh[0].end():]
    t = t[:he[1]] + new_ebody + t[he[2]:]
    # 2. play: End3D/ensure_2d
    hp = pl.find_function(t, PLAY_SIG)
    t = t[:hp[1]] + new_pbody + t[hp[2]:]
    # 3. state_2d: Anfang
    h2 = pl.find_function(t, STATE2D_SIG)
    t = t[:h2[1] + 1] + '\n    wots2_state2d_real();' + t[h2[1] + 1:]
    # 4. HELPER2 hinter state_2d
    h2 = pl.find_function(t, STATE2D_SIG)
    t = t[:h2[2]] + '\n' + HELPER2 + t[h2[2]:]
    # 5. state_3d: Schnellpfad vorn, Merker hinten
    h3 = pl.find_function(t, STATE3D_SIG)
    b3s, b3e = h3[1], h3[2]
    t = (t[:b3s + 1] + '\n    if (wots2_state3d_fast(mvp, xscale, kind))\n        return;' + t[b3s + 1:b3e - 1]
         + '    wots2_state3d_done(xscale, kind);\n' + t[b3e - 1:])
    # 6. HELPER1 vor state_3d, Report vor end_frame
    t = insert_before_function(t, STATE3D_SIG, HELPER1)
    t = insert_before_function(t, END_SIG, REPORT)
    p.write_text(t)
    print('  Lazy-State eingebaut: End3D verschiebt den 2D-Wechsel, state_3d hat einen Schnellpfad.')
    print('  Notausschalter: WOTS2_NO_LAZYSTATE=1;  Zaehler: WOTS2_TIMING=1 -> [gcount]')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    pl.finish()
    print('Fertig.')
