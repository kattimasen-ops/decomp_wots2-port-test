#!/usr/bin/env python3
"""
patches/wots2-gs-perf-trace-v3.py — [perf]-Zeile mit Frame-Zeit + Draw-Zahlen.
Patcht src/hal/gs.cpp. Idempotent ueber Marker "wots2_perf_trace_v3".
"""
import sys
import pathlib

MARKER = "wots2_perf_trace_v3"

OLD = '''    play(s_cur, nullptr, 1.0f);
    debug_frame_hooks();
'''

NEW = '''    play(s_cur, nullptr, 1.0f);
    // wots2_perf_trace_v3
    {
        static const bool s_perf_on = getenv("WOTS2_PERF_TRACE") != nullptr;
        static double s_perf_last = 0.0;
        if (s_perf_on) {
            const double s_now =
                (double)SDL_GetPerformanceCounter() * 1000.0 / (double)SDL_GetPerformanceFrequency();
            if (s_perf_last > 0.0 && (s_frame % 30) == 0) {
                const double s_dt = s_now - s_perf_last;
                if (s_dt > 0.0) {
                    printf("[perf] frame %d: %.2f ms (%.1f fps), draw/cull %d/%d\\n",
                           s_frame, s_dt, 1000.0 / s_dt, s_drawn, s_culled);
                    fflush(stdout);
                }
            }
            s_perf_last = s_now;
        }
    }
    debug_frame_hooks();
'''

def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    if MARKER in t:
        print('  Perf-Trace v3 bereits vorhanden.')
        return
    if OLD not in t:
        print('  FEHLER: Anker nicht gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t.replace(OLD, NEW, 1)
    p.write_text(t)
    print('  Perf-Trace v3 eingebaut.')

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
