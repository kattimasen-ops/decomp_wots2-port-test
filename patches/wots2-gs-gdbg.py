#!/usr/bin/env python3
"""
patches/wots2-gs-gdbg.py   (v1, Diagnose)

Findet und dokumentiert den 'schwarzen Bildschirm' selbst. Mit WOTS2_GDBG=1
(der Launcher setzt es bei WOTS2_ANALYSE=1) passiert Folgendes:

  1. Bild-Helligkeit: Alle 30 Frames werden 24 Pixel aus s_fbo gelesen. Bleibt das
     Bild ueber 20 Messpunkte (etwa 20 s bei 30 FPS, laenger bei weniger) dunkel
     (Mittelwert < 6 von 255), schreibt das Spiel eine [gdbg]-Zeile mit dem Zustand
     und einen Screenshot shot_schwarz_NNNNN.png nach WOTS2_SHOT_DIR (Standard: .).
  2. Eingefrorene Szene: Bleiben drawn/culled 240 Frames lang exakt gleich, gibt es
     dieselbe Zeile und shot_stall_NNNNN.png (danach alle 1800 Frames wieder eine Zeile).
  3. read_frame(): Jeder Aufruf wird gemeldet. read_frame() ist der Weg des
     Standbilds in Effect.Monotone (Erzaehl-Szenen).

Die [gdbg]-Zeile enthaelt: Frame, Grund, drawn/culled, Anzahl je Befehlsart des
letzten Frames, Nebel (Werte und Farbe), Zahl der Vollbild-2D-Quads (und wie viele
davon schwarz), Farbe des letzten, uFade, Render-Target/Lichter-Flags und die Zahl
der read_frame()-Aufrufe.

Kostet nur mit WOTS2_GDBG=1 etwas (24 Pixel-Reads alle 30 Frames). Ohne die
Variable ist der Zusatzcode ein einziger Vergleich pro Frame.

Idempotent: Marker 'wots2_gs_gdbg_v1'.
Zieldatei: src/hal/gs.cpp
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wots2_patchlib as pl  # noqa: E402

MARKER = "wots2_gs_gdbg_v1"

HELPER = r'''// wots2_gs_gdbg_v1 (wots2-gs-gdbg.py): Diagnose fuer den schwarzen Bildschirm
@OPNAMES@
static long s_wots2ReadFrames = 0;
static int  s_wots2StallRun = 0, s_wots2LastDrawn = -1, s_wots2LastCulled = -1;
static int  s_wots2BlackRun = 0, s_wots2Shots = 0;
static inline bool wots2_gdbg_on() {
    static const bool on = (getenv("WOTS2_GDBG") != nullptr);
    return on;
}
static void wots2_gdbg_shot(const char* tag) {
    if (s_wots2Shots >= 8)
        return;                                     // hoechstens 8 Bilder pro Lauf
    const int w = s_physW, h = s_physH;
    std::vector<u8> px((size_t)w * h * 3);
    GLint was = 0;
    glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &was);
    glBindFramebuffer(GL_READ_FRAMEBUFFER, s_fbo);
    glPixelStorei(GL_PACK_ALIGNMENT, 1);
    glReadPixels(0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE, px.data());
    glBindFramebuffer(GL_READ_FRAMEBUFFER, (GLuint)was);
    const char* dir = getenv("WOTS2_SHOT_DIR");
    char path[512];
    snprintf(path, sizeof(path), "%s/shot_%s_%05d.png", dir ? dir : ".", tag, s_frame);
    if (write_png(path, px.data(), w, h)) {
        s_wots2Shots++;
        printf("[gdbg] Bild geschrieben: %s\n", path);
    }
}
// Mittlere Helligkeit (0..255) aus einem groben Raster von s_fbo.
static float wots2_gdbg_brightness() {
    const int w = s_physW, h = s_physH;
    GLint was = 0;
    glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &was);
    glBindFramebuffer(GL_READ_FRAMEBUFFER, s_fbo);
    double sum = 0;
    int n = 0;
    for (int gy = 0; gy < 4; gy++)
        for (int gx = 0; gx < 6; gx++) {
            u8 p[4] = {0, 0, 0, 0};
            glReadPixels((gx * 2 + 1) * w / 12, (gy * 2 + 1) * h / 8, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, p);
            sum += (p[0] + p[1] + p[2]) / 3.0;
            n++;
        }
    glBindFramebuffer(GL_READ_FRAMEBUFFER, (GLuint)was);
    return n > 0 ? (float)(sum / n) : -1.0f;
}
static void wots2_gdbg_dump(const char* why, float brightness) {
    long ops[32] = {0};
    int full = 0, blackFull = 0;
    float lr = -1, lg = -1, lb = -1, la = -1;
    for (const Cmd& c : s_cur.cmds) {
        const int k = (int)c.op;
        if (k >= 0 && k < 32)
            ops[k]++;
        if (c.op == Op::Draw2D && c.count >= 3 && c.first + (u32)c.count <= s_cur.v2.size()) {
            const Vertex* v = verts2(s_cur, c, nullptr, 1.0f);
            float x0 = v[0].x, x1 = v[0].x, y0 = v[0].y, y1 = v[0].y;
            for (int i = 1; i < c.count; i++) {
                if (v[i].x < x0) x0 = v[i].x;
                if (v[i].x > x1) x1 = v[i].x;
                if (v[i].y < y0) y0 = v[i].y;
                if (v[i].y > y1) y1 = v[i].y;
            }
            if (x1 - x0 >= 0.9f * s_lw && y1 - y0 >= 0.9f * (float)s_height) {
                full++;
                lr = v[0].r; lg = v[0].g; lb = v[0].b; la = v[0].a;
                if (v[0].r < 0.1f && v[0].g < 0.1f && v[0].b < 0.1f && v[0].a > 0.5f)
                    blackFull++;
            }
        }
    }
    printf("[gdbg] frame %d (%s): hell=%.1f drawn=%d culled=%d ops{", s_frame, why, brightness, s_drawn, s_culled);
    for (int k = 0; k < kWots2OpCount; k++)
        if (ops[k])
            printf("%s=%ld ", kWots2OpNames[k], ops[k]);
    printf("} fog=(%.2f,%.2f,%.2f,%.2f) fogc=(%.2f,%.2f,%.2f) full2d=%d schwarz_full2d=%d letzter=(%.2f,%.2f,%.2f,%.2f) uFade=@UFADE@ target=%d lit=%d read_frame_calls=%ld\n",
           s_fog[0], s_fog[1], s_fog[2], s_fog[3], s_fogColor[0], s_fogColor[1], s_fogColor[2],
           full, blackFull, lr, lg, lb, la, @UFADEVAL@(int)s_inTarget, (int)s_litFrame, s_wots2ReadFrames);
    fflush(stdout);
}
// Einmal pro Frame, am Anfang von debug_frame_hooks() (s_drawn/s_culled gelten noch fuer diesen Frame).
static void wots2_gdbg_frame() {
    if (!wots2_gdbg_on())
        return;
    static const int kStall = []() -> int {
        const char* e = getenv("WOTS2_GDBG_STALL");
        const int v = (e != nullptr && *e != '\0') ? atoi(e) : 240;
        return v > 30 ? v : 240;
    }();
    if (s_drawn == s_wots2LastDrawn && s_culled == s_wots2LastCulled && s_drawn + s_culled > 0)
        s_wots2StallRun++;
    else
        s_wots2StallRun = 0;
    s_wots2LastDrawn = s_drawn;
    s_wots2LastCulled = s_culled;
    if (s_wots2StallRun == kStall || (s_wots2StallRun > kStall && (s_wots2StallRun - kStall) % 1800 == 0)) {
        wots2_gdbg_dump("Szene eingefroren", -1.0f);
        wots2_gdbg_shot("stall");
    }
    if (s_frame % 30 == 0) {
        const float avg = wots2_gdbg_brightness();
        if (avg >= 0.0f && avg < 6.0f) {
            s_wots2BlackRun++;
            if (s_wots2BlackRun == 20 || (s_wots2BlackRun > 20 && (s_wots2BlackRun - 20) % 120 == 0)) {
                wots2_gdbg_dump("Bild dunkel", avg);
                wots2_gdbg_shot("schwarz");
            }
        } else {
            if (s_wots2BlackRun >= 20)
                printf("[gdbg] frame %d: Bild wieder hell (hell=%.1f) nach %d Messpunkten\n", s_frame, avg, s_wots2BlackRun);
            s_wots2BlackRun = 0;
        }
    }
}
static void wots2_gdbg_readframe() {
    s_wots2ReadFrames++;
    if (wots2_gdbg_on()) {
        printf("[gdbg] frame %d: read_frame() Aufruf Nr. %ld (Standbild fuer Effect.Monotone)\n", s_frame, s_wots2ReadFrames);
        fflush(stdout);
    }
}

'''

HOOK_SIG = r'static\s+void\s+debug_frame_hooks\s*\(\s*\)'
READ_SIG = r'void\s+read_frame\s*\(\s*std::vector<u8>\s*&\s*rgba\s*\)'
ENUM_RE = re.compile(r'enum\s+class\s+Op\s*:\s*u8\s*\{([^}]*)\}')


def patch(path):
    p = pathlib.Path(path)
    if not p.exists():
        pl.fail('Zieldatei %s existiert nicht' % path)
        return
    t = p.read_text()
    if MARKER in t:
        print('  GDBG bereits vorhanden (Marker: %s).' % MARKER)
        return

    me = ENUM_RE.search(t)
    if not me:
        pl.fail('enum class Op nicht gefunden')
        return
    names = [n.strip() for n in me.group(1).split(',') if n.strip()]
    if not names or len(names) > 30:
        pl.fail('Op-Liste unplausibel (%d Eintraege)' % len(names))
        return

    hh = pl.find_function(t, HOOK_SIG)
    hr = pl.find_function(t, READ_SIG)
    if hh is None or hr is None:
        pl.fail('debug_frame_hooks() oder read_frame() nicht gefunden')
        return
    hbody = t[hh[1]:hh[2]]
    mh = list(re.finditer(pl.flex('s_drawn = s_culled = 0;'), hbody))
    if len(mh) != 1:
        pl.fail('debug_frame_hooks: "s_drawn = s_culled = 0;" %d Treffer statt genau 1' % len(mh))
        return
    if hr[0] < hh[0]:
        pl.fail('read_frame() steht vor debug_frame_hooks() - Reihenfolge unerwartet')
        return
    for need in ('s_cur', 's_fbo', 's_physW', 's_physH', 's_lw', 's_height', 's_fog', 's_fogColor',
                 's_inTarget', 's_litFrame', 's_drawn', 's_culled', 'write_png', 'verts2', 's_frame'):
        if not re.search(r'\b%s\b' % need, t[:hh[0]]):
            pl.fail('%s ist vor debug_frame_hooks() nicht deklariert' % need)
            return

    has_fade = 's_wots2Fade' in t[:hh[0]]
    helper = HELPER.replace('@OPNAMES@',
        'static const char* const kWots2OpNames[] = {%s};\nstatic const int kWots2OpCount = %d;' %
        (', '.join('"%s"' % n for n in names), len(names)))
    helper = helper.replace('@UFADE@', '%.2f' if has_fade else 'n/a').replace(
        '@UFADEVAL@', '(double)s_wots2Fade, ' if has_fade else '')

    # von hinten nach vorn schreiben
    rbody_open = hr[1]
    t = t[:rbody_open + 1] + '\n    wots2_gdbg_readframe();' + t[rbody_open + 1:]
    hh = pl.find_function(t, HOOK_SIG)
    hbody = t[hh[1]:hh[2]]
    mh = list(re.finditer(pl.flex('s_drawn = s_culled = 0;'), hbody))
    new_hbody = hbody[:mh[0].start()] + 'wots2_gdbg_frame();\n    ' + hbody[mh[0].start():]
    t = t[:hh[1]] + new_hbody + t[hh[2]:]
    hh = pl.find_function(t, HOOK_SIG)
    ins = hh[0]
    while True:
        prev_end = ins - 1
        if prev_end < 0:
            break
        prev_start = t.rfind('\n', 0, prev_end) + 1
        if t[prev_start:prev_end].lstrip().startswith('//'):
            ins = prev_start
        else:
            break
    t = t[:ins] + helper + t[ins:]
    p.write_text(t)
    print('  GDBG eingebaut (%d Befehlsarten, uFade %s).' % (len(names), 'ja' if has_fade else 'nein'))
    print('  Aktiv mit WOTS2_GDBG=1; Bilder nach WOTS2_SHOT_DIR.')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    pl.finish()
    print('Fertig.')
