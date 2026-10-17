#!/usr/bin/env python3
"""
patches/wots2-merge-3d-draws.py

Fasst aufeinanderfolgende draw_mesh()-Aufrufe in src/hal/gs.cpp zu einem
einzigen Cmd::Mesh zusammen — solange Textur, Primitive, Owner (Begin3D)
und Vertex-Bereich zusammenhaengen.

Nur TriangleStrips werden gestitcht (zwei Degenerate-Vertices an der
Naht). TriangleFans werden NICHT gemergt.

WOTS2_NO_MERGE=1 schaltet es ab. WOTS2_TRACE_MERGE=1 zaehlt pro Frame.

Idempotent ueber Marker 'wots2-merge-3d-draws.py'.

Zieldatei: src/hal/gs.cpp

Python 3.6+ kompatibel.
"""
import sys
import pathlib

MARKER = "wots2-merge-3d-draws.py"

OLD = '''    if (!own_texture(tex))
        check_live(tex, "a 3D draw with");
    Cmd& c = push(Op::Mesh);
    memcpy(c.f, lo, sizeof lo);
    memcpy(c.f + 3, hi, sizeof hi);
    c.tex = tex ? tex : s_white;
    c.prim = (u8)prim;
    c.first = first;
    c.count = count;
    c.owner = s_recOwner;
    c.who = s_recWho;
}
'''

NEW = '''    if (!own_texture(tex))
        check_live(tex, "a 3D draw with");
    // wots2-merge-3d-draws.py
    // Zwei aufeinanderfolgende Meshes mit gleicher Textur, Primitive,
    // Owner und lueckenlosem Vertex-Bereich werden zu einem Cmd::Mesh
    // zusammengefasst. TriangleStrips werden mit zwei Degenerate-Vertices
    // gestitcht (letzter des vorigen Strips, erster des neuen). Fan
    // bleibt aussen vor — ein gemergter Fan ist kein Fan.
    static const bool s_wots2_no_merge   = getenv("WOTS2_NO_MERGE") != nullptr;
    static const bool s_wots2_trace_merge = getenv("WOTS2_TRACE_MERGE") != nullptr;
    const u32 tid = tex ? tex : s_white;
    if (!s_wots2_no_merge && !s_cur.cmds.empty() && prim != Prim::TriangleFan) {
        Cmd& prev = s_cur.cmds.back();
        if (prev.op == Op::Mesh && prev.tex == tid && prev.prim == (u8)prim
            && prev.owner == s_recOwner && prev.who == s_recWho
            && (u64)prev.first + (u64)prev.count == (u64)first
            && prev.count > 0 && count > 0) {
            if (prim == Prim::TriangleStrip) {
                Vertex3 stitch[2];
                stitch[0] = s_cur.v3[first - 1];
                stitch[1] = s_cur.v3[first];
                s_cur.v3.insert(s_cur.v3.begin() + first, stitch, stitch + 2);
                prev.count += count + 2;
            } else {
                prev.count += count;
            }
            for (int k = 0; k < 3; k++) {
                if (lo[k] < prev.f[k])     prev.f[k]     = lo[k];
                if (hi[k] > prev.f[3 + k]) prev.f[3 + k] = hi[k];
            }
            if (s_wots2_trace_merge) {
                static u32 s_merged = 0, s_frames = 0;
                s_merged++;
                if ((++s_frames & 0x3F) == 0)
                    printf("[merge3d] %u meshes gemergt in %u frames\\n", s_merged, s_frames);
            }
            return;
        }
    }
    Cmd& c = push(Op::Mesh);
    memcpy(c.f, lo, sizeof lo);
    memcpy(c.f + 3, hi, sizeof hi);
    c.tex = tid;
    c.prim = (u8)prim;
    c.first = first;
    c.count = count;
    c.owner = s_recOwner;
    c.who = s_recWho;
}
'''

def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    if MARKER in t:
        print('  Merge-3D-Draws bereits vorhanden.')
        return
    if OLD not in t:
        print('  FEHLER: draw_mesh()-Block nicht gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t.replace(OLD, NEW, 1)
    p.write_text(t)
    print('  Merge-3D-Draws eingebaut (draw_mesh, 1 Stelle).')

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
