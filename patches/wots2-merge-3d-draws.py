#!/usr/bin/env python3
"""
patches/wots2-merge-3d-draws.py  (v2)

Fasst aufeinanderfolgende draw_mesh()-Aufrufe in src/hal/gs.cpp zu einem
einzigen Cmd::Mesh zusammen — solange Textur, Primitive, Owner (Begin3D)
und Vertex-Bereich zusammenhaengen.

v2: KEIN std::vector::insert mehr.  v1 hat die Stitch-Vertices mitten in
den Vektor geschoben (O(n) memmove pro Merge), was bei vielen Merges den
gesamten Speicher-Bus gesaettigt hat.  v2 pusht den Stitch zuerst (mit
einer Kopie des ersten neuen Vertex, aus der Quelle `verts[0]`, nicht aus
v3), dann die neuen Vertices hinten an.  Amortisiert O(count) statt
O(v3.size()).

TriangleStrips werden gestitcht (2 Degenerate-Vertices an der Naht: der
letzte Vertex des vorigen Strips und der erste des neuen). TriangleFans
werden NICHT gemergt.

WOTS2_NO_MERGE=1 schaltet es ab. WOTS2_TRACE_MERGE=1 zaehlt.

Idempotent ueber Marker 'wots2-merge-3d-draws.py' und den v2-Marker
'wots2_merge3d_v2', damit die v1-Version sauber ueberschrieben wird.

Zieldatei: src/hal/gs.cpp

Python 3.6+ kompatibel.
"""
import sys
import pathlib

MARKER_V2 = "wots2_merge3d_v2"

# ── v1-Block, der (falls vorhanden) komplett ersetzt wird ────────────────
V1_BLOCK = '''    if (!own_texture(tex))
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

# ── Urspruenglicher (ungepatchter) Block, der in v2 ersetzt wird ────────
ORIGINAL_BLOCK = '''    if (!own_texture(tex))
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

V2_BLOCK = '''    if (!own_texture(tex))
        check_live(tex, "a 3D draw with");
    // wots2-merge-3d-draws.py (wots2_merge3d_v2)
    // Aufeinanderfolgende Meshes mit gleicher Textur, Primitive, Owner
    // und lueckenlosem Vertex-Bereich werden zu einem Cmd::Mesh
    // zusammengefasst. TriangleStrips werden mit zwei Degenerate-Vertices
    // gestitcht. Kein std::vector::insert: der Stitch wird VOR den neuen
    // Vertices gepusht (aus einer Kopie des ersten neuen Vertex gebaut),
    // dann werden die neuen Vertices angehaengt. Amortisiert O(count).
    static const bool s_wots2_no_merge    = getenv("WOTS2_NO_MERGE") != nullptr;
    static const bool s_wots2_trace_merge = getenv("WOTS2_TRACE_MERGE") != nullptr;
    const u32 tid = tex ? tex : s_white;

    bool merge = false;
    Cmd* pprev = nullptr;
    if (!s_wots2_no_merge && !s_cur.cmds.empty() && prim != Prim::TriangleFan) {
        pprev = &s_cur.cmds.back();
        if (pprev->op == Op::Mesh && pprev->tex == tid && pprev->prim == (u8)prim
            && pprev->owner == s_recOwner && pprev->who == s_recWho
            && pprev->count > 0 && count > 0
            && (u64)pprev->first + (u64)pprev->count == (u64)first) {
            merge = true;
        }
    }

    if (merge) {
        if (prim == Prim::TriangleStrip) {
            // Stitch: [letzter Vertex des vorigen Strips, erster des neuen].
            Vertex3 stitch0;
            memcpy(&stitch0, &s_cur.v3[pprev->first + pprev->count - 1], sizeof(Vertex3));
            Vertex3 stitch1;
            {
                float c0[4];
                unpack(verts[0].rgba, c0, tid != s_white);
                stitch1.x = verts[0].x; stitch1.y = verts[0].y; stitch1.z = verts[0].z;
                stitch1.u = verts[0].u; stitch1.v = verts[0].v;
                stitch1.r = c0[0]; stitch1.g = c0[1]; stitch1.b = c0[2]; stitch1.a = c0[3];
            }
            // Erst den Stitch anhaengen, dann die neuen Vertices.
            const size_t s0 = s_cur.v3.size();
            s_cur.v3.resize(s0 + 2 + (size_t)count);
            memcpy(&s_cur.v3[s0],     &stitch0, sizeof(Vertex3));
            memcpy(&s_cur.v3[s0 + 1], &stitch1, sizeof(Vertex3));
            Vertex3* out2 = s_cur.v3.data() + s0 + 2;
            for (int i = 0; i < count; i++) {
                float c0[4];
                unpack(verts[i].rgba, c0, tid != s_white);
                out2[i] = {verts[i].x, verts[i].y, verts[i].z, verts[i].u, verts[i].v,
                           c0[0], c0[1], c0[2], c0[3]};
            }
            pprev->count += count + 2;
        } else {
            // Kein Stitch: die neuen Vertices direkt anhaengen.
            const size_t s0 = s_cur.v3.size();
            s_cur.v3.resize(s0 + (size_t)count);
            Vertex3* out2 = s_cur.v3.data() + s0;
            for (int i = 0; i < count; i++) {
                float c0[4];
                unpack(verts[i].rgba, c0, tid != s_white);
                out2[i] = {verts[i].x, verts[i].y, verts[i].z, verts[i].u, verts[i].v,
                           c0[0], c0[1], c0[2], c0[3]};
            }
            pprev->count += count;
        }
        for (int k = 0; k < 3; k++) {
            if (lo[k] < pprev->f[k])     pprev->f[k]     = lo[k];
            if (hi[k] > pprev->f[3 + k]) pprev->f[3 + k] = hi[k];
        }
        if (s_wots2_trace_merge) {
            static u32 s_merged = 0, s_frames = 0;
            s_merged++;
            if ((++s_frames & 0x3F) == 0)
                printf("[merge3d] %u meshes gemergt in %u frames\\n", s_merged, s_frames);
        }
        return;
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
    if MARKER_V2 in t:
        print('  Merge-3D-Draws v2 bereits vorhanden.')
        return
    if V1_BLOCK in t:
        # v1 durch v2 ersetzen
        t = t.replace(V1_BLOCK, V2_BLOCK, 1)
        p.write_text(t)
        print('  Merge-3D-Draws von v1 auf v2 aktualisiert (kein vector::insert).')
        return
    if ORIGINAL_BLOCK in t:
        # v2 direkt auf Original anwenden
        t = t.replace(ORIGINAL_BLOCK, V2_BLOCK, 1)
        p.write_text(t)
        print('  Merge-3D-Draws v2 eingebaut (Original war ungepatcht).')
        return
    print('  FEHLER: weder v1-Block noch Original draw_mesh()-Block gefunden.',
          file=sys.stderr)
    sys.exit(1)

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
