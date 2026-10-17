#!/usr/bin/env python3
"""
patches/wots2-gs-perf-trace-v2.py

Misst die tatsaechliche Frame-Zeit im end_frame()-Loop von gs.cpp und
schreibt alle 30 Frames eine Zeile nach stdout:

  [perf] frame N: X.XX ms (YY.Y fps)

Damit sehen wir zum ersten Mal, ob die 15 FPS aus 64 ms echter Arbeit
kommen oder aus dem Limiter. Ersetzt den alten wots2-gs-perf-trace.py,
falls er nicht greift.

WOTS2_PERF_TRACE=1 aktiviert.

Patcht src/hal/gs.cpp. Idempotent ueber Marker "wots2_perf_trace_v2".
"""
import sys
import pathlib

MARKER = "wots2_perf_trace_v2"

OLD = '''void end_frame() {
    static double t0 = 0.0;             // when the frame before was shown (ms)
    const double period = 1000.0 / (double)(s_fps > 0 ? s_fps : 30);
    const auto now = []() { return (double)SDL_GetPerformanceCounter() * 1000.0 / (double)SDL_GetPerformanceFrequency(); };
'''

NEW = '''void end_frame() {
    static double t0 = 0.0;             // when the frame before was shown (ms)
    static double wots2_perf_last = 0.0;
    static const bool wots2_perf_on = getenv("WOTS2_PERF_TRACE") != nullptr;  // wots2_perf_trace_v2
    const double period = 1000.0 / (double)(s_fps > 0 ? s_fps : 30);
    const auto now = []() { return (double)SDL_GetPerformanceCounter() * 1000.0 / (double)SDL_GetPerformanceFrequency(); };
    if (wots2_perf_on) {
        const double wots2_tnow = now();
        if (wots2_perf_last > 0.0) {
            const double dt = wots2_tnow - wots2_perf_last;
            if ((s_frame % 30) == 0 && dt > 0.0) {
                printf("[perf] frame %d: %.2f ms (%.1f fps)\\n",
                       s_frame, dt, 1000.0 / dt);
                fflush(stdout);
            }
        }
        wots2_perf_last = wots2_tnow;
    }
'''

def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    if MARKER in t:
        print('  Perf-Trace v2 bereits vorhanden.')
        return
    if OLD not in t:
        print('  FEHLER: end_frame()-Anker nicht gefunden.', file=sys.stderr)
        print('  Erwartet: "void end_frame()" mit "static double t0 = 0.0".', file=sys.stderr)
        sys.exit(1)
    t = t.replace(OLD, NEW, 1)
    p.write_text(t)
    print('  Perf-Trace v2 eingebaut (end_frame, 1 Stelle).')

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
