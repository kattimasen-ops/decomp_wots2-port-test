#!/usr/bin/env python3
"""
patches/wots2-gs-npc-fade.py   (v2)

Setzt in src/hal/gs.cpp das Ausblenden von Figuren am Ende der Sichtweite um
(Pop-in/Pop-out). Gegenstueck: wots2-chara-fade-flag.py (hle_chara.cpp).

Wie es funktioniert
-------------------
  * hle_chara.cpp setzt direkt vor begin_3d() einer Figur (Koerper und
    Schwert-Teile) die Variablen g_wots2_chara_view = 1 und g_wots2_chara_fade
    (Faktor 1 = voll ... 0 = weg, berechnet aus Chara::cameraDistance).
  * begin_3d() merkt sich das am Befehl: Bit 16 in Cmd.flags, der Faktor als
    Float in Cmd.z (bei Begin3D unbenutzt, und nicht Teil des Paarungs-Schluessels).
  * play() setzt den Faktor als Uniform uFade, sobald die Ansicht beginnt, und
    am Ende der Ansicht wieder auf 1. Ist er schon 1, kostet das keinen GL-Aufruf.
  * Der 3D-Fragment-Shader verwirft bei uFade < 1 pro Pixel nach einem festen
    Rauschmuster (Interleaved Gradient Noise) soviele Pixel, dass die Figur
    aufloest. Kein Blending, keine Sortierung, die Tiefe bleibt korrekt.

Die Parameter (WOTS2_NPC_FADE_END, WOTS2_NPC_FADE_LEN, WOTS2_NO_NPC_FADE) wertet
wots2-chara-fade-flag.py aus. Props und Schatten werden nie ausgeblendet.

Sicherheit: Alle Aenderungen werden zuerst geprueft und nur gemeinsam
geschrieben. Fehlt ein Anker, bleibt gs.cpp unberuehrt (der Shader wird nie
halb veraendert). Der Shader-Zusatz benutzt nur Standard-GLSL (ES 3.x und 3.3).

Idempotent: Marker 'wots2_gs_npc_fade_v2'.
Zieldatei: src/hal/gs.cpp
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wots2_patchlib as pl  # noqa: E402

MARKER = "wots2_gs_npc_fade_v2"

SHADER_UNIFORM_RE = re.compile(r'(uniform\s+(?:(?:lowp|mediump|highp)\s+)?int\s+uCutout\s*;)')
SHADER_DISCARD_RE = re.compile(r'(if\s*\(\s*c\.a\s*<\s*uAlphaRef\s*\)\s*discard\s*;)')
SHADER_UNIFORM_ADD = '\nuniform float uFade;     // 1 = voll sichtbar; kleiner: Figur loest sich auf (wots2-gs-npc-fade)'
SHADER_DISCARD_ADD = '''
    if (uFade < 1.0) {      // Aufloesen am Ende der Sichtweite (wots2-gs-npc-fade)
        highp float wots2n = fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715))));
        if (wots2n >= uFade) discard;
    }'''

DECL = '''
// wots2_gs_npc_fade_v2 (wots2-gs-npc-fade.py)
static GLint s_uFade = -1;
'''

LOCATION_RE = re.compile(r'(s_uCutout\s*=\s*glGetUniformLocation\(\s*s_program3d\s*,\s*"uCutout"\s*\)\s*;)')
LOCATION_ADD = '''
    s_uFade = glGetUniformLocation(s_program3d, "uFade");
    if (s_uFade >= 0)
        glUniform1f(s_uFade, 1.0f);'''

HELPER = '''// wots2_gs_npc_fade_v2 (wots2-gs-npc-fade.py)
// hle_chara.cpp setzt diese Variablen direkt vor begin_3d() einer Figur; begin_3d() merkt sie
// sich am Befehl und setzt sie zurueck. (C-Namen, damit hle_chara.cpp sie als schwache Symbole
// deklarieren kann: fehlt dieser Patch dort, bleibt alles beim Alten.)
extern "C" {
int g_wots2_chara_view = 0;
float g_wots2_chara_fade = 1.0f;
}
static float s_wots2Fade = 1.0f;       // zuletzt gesetzter uFade-Wert
static inline void wots2_fade_apply(const Cmd& c) {
    float f = 1.0f;
    if (s_uFade >= 0 && !s_inTarget && (c.flags & 16) != 0 && c.i == (int)hal::gs::View::Model) {
        memcpy(&f, &c.z, sizeof(f));
        if (!(f >= 0.0f && f <= 1.0f))
            f = 1.0f;
    }
    if (f != s_wots2Fade) {
        glUniform1f(s_uFade, f);
        s_wots2Fade = f;
    }
}
static inline void wots2_fade_reset() {
    if (s_wots2Fade != 1.0f && s_uFade >= 0) {
        glUniform1f(s_uFade, 1.0f);
        s_wots2Fade = 1.0f;
    }
}

'''

PLAY_SIG = r'static\s+void\s+play\s*\(\s*const\s+Frame\s*&\s*f\s*,\s*const\s+Frame\s*\*\s*before\s*,\s*float\s+t\s*\)'
BEGIN3D_SIG = r'^void\s+begin_3d\s*\(\s*const\s+float\s*\*\s*mvp\s*,\s*View\s+kind\s*,\s*u32\s+who\s*\)'


def patch(path):
    p = pathlib.Path(path)
    if not p.exists():
        pl.fail('Zieldatei %s existiert nicht' % path)
        return
    t = p.read_text()
    if MARKER in t:
        print('  NPC-Fade bereits vorhanden (Marker: %s).' % MARKER)
        return

    # ---------- 1. Shader (nur innerhalb des 3D-Fragment-Shaders) ----------
    m0 = re.search(r'kFragmentShader3d\s*=\s*R"\(', t)
    if not m0:
        pl.fail('kFragmentShader3d nicht gefunden')
        return
    end0 = t.index(')";', m0.end())
    shader = t[m0.end():end0]
    for name, rx in (('uniform int uCutout;', SHADER_UNIFORM_RE), ('if (c.a < uAlphaRef) discard;', SHADER_DISCARD_RE)):
        n = len(list(rx.finditer(shader)))
        if n != 1:
            pl.fail('Shader: "%s" %d Treffer statt genau 1 (hat wots2-gles/-precision die Zeile veraendert?)' % (name, n))
            return
    if 'uFade' in shader:
        pl.fail('Shader enthaelt schon uFade')
        return
    new_shader = SHADER_UNIFORM_RE.sub(lambda m: m.group(1) + SHADER_UNIFORM_ADD, shader, count=1)
    new_shader = SHADER_DISCARD_RE.sub(lambda m: m.group(1) + SHADER_DISCARD_ADD, new_shader, count=1)

    # ---------- 2. Uniform-Location ----------
    if len(list(LOCATION_RE.finditer(t))) != 1:
        pl.fail('s_uCutout = glGetUniformLocation(...): nicht genau 1 Treffer')
        return

    # ---------- 3. play(): Begin3D und End3D ----------
    hp = pl.find_function(t, PLAY_SIG)
    if hp is None:
        pl.fail('play() nicht gefunden')
        return
    pbody = t[hp[1]:hp[2]]
    b3 = list(re.finditer(r'(state_3d\s*\(\s*m\s*,\s*s_playXScale\s*,\s*c\.i\s*\)\s*;)', pbody))
    e3 = list(re.finditer(r'(case\s+Op::End3D\s*:)', pbody))
    if len(b3) != 1 or len(e3) != 1:
        pl.fail('play(): Begin3D-state_3d-Aufruf %d Treffer, case Op::End3D %d Treffer (erwartet je 1)' % (len(b3), len(e3)))
        return

    # ---------- 4. begin_3d() (Aufzeichnung) ----------
    hb = pl.find_function(t, BEGIN3D_SIG)
    if hb is None:
        pl.fail('begin_3d(const float*, View, u32) nicht gefunden')
        return
    bbody = t[hb[1]:hb[2]]
    cw = list(re.finditer(r'(c\.who\s*=\s*who\s*;)', bbody))
    if len(cw) != 1:
        pl.fail('begin_3d: "c.who = who;" %d Treffer statt genau 1' % len(cw))
        return

    # ---------- Schreiben, von hinten nach vorn ----------
    new_bbody = bbody[:cw[0].end()] + '\n    if (g_wots2_chara_view != 0) {            // wots2-gs-npc-fade: Ansicht einer Figur\n        c.flags |= 16;\n        memcpy(&c.z, &g_wots2_chara_fade, sizeof(float));   // z ist bei Begin3D frei\n        g_wots2_chara_view = 0;\n        g_wots2_chara_fade = 1.0f;\n    }' + bbody[cw[0].end():]
    t = t[:hb[1]] + new_bbody + t[hb[2]:]

    new_pbody = pbody
    new_pbody = new_pbody[:e3[0].end()] + '\n            wots2_fade_reset();' + new_pbody[e3[0].end():]
    b3 = list(re.finditer(r'(state_3d\s*\(\s*m\s*,\s*s_playXScale\s*,\s*c\.i\s*\)\s*;)', new_pbody))
    new_pbody = new_pbody[:b3[0].end()] + '\n            wots2_fade_apply(c);' + new_pbody[b3[0].end():]
    hp = pl.find_function(t, PLAY_SIG)
    t = t[:hp[1]] + new_pbody + t[hp[2]:]

    # Helfer vor play() (samt Kommentarblock)
    hp = pl.find_function(t, PLAY_SIG)
    ins = hp[0]
    while True:
        prev_end = ins - 1
        if prev_end < 0:
            break
        prev_start = t.rfind('\n', 0, prev_end) + 1
        if t[prev_start:prev_end].lstrip().startswith('//'):
            ins = prev_start
        else:
            break
    t = t[:ins] + HELPER + t[ins:]

    t = LOCATION_RE.sub(lambda m: m.group(1) + LOCATION_ADD, t, count=1)

    m0 = re.search(r'kFragmentShader3d\s*=\s*R"\(', t)
    end0 = t.index(')";', m0.end())
    t = t[:m0.end()] + new_shader + t[end0:]

    inc = pl.last_include_end(t)
    if inc < 0:
        pl.fail('kein #include gefunden')
        return
    t = t[:inc] + DECL + t[inc:]
    p.write_text(t)
    print('  NPC-Fade eingebaut (Shader, uFade, Markierung der Figuren-Ansichten).')
    print('  Einstellungen: WOTS2_NPC_FADE_END / WOTS2_NPC_FADE_LEN, aus mit WOTS2_NO_NPC_FADE=1')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    pl.finish()
    print('Fertig.')
