#!/usr/bin/env python3
"""
patches/wots2-merge-3d-draws.py  (v3)

Fasst aufeinanderfolgende draw_mesh()-Aufrufe mit gleicher Textur,
Primitive, Owner, who und lueckenlosem Vertex-Bereich zusammen.

v3 behebt den v2-Fehler: v2 hat die neuen Vertices ZWEIMAL in v3
abgelegt (einmal aus dem Top-Teil von draw_mesh, einmal aus dem
Merge-Block), und die Stitch-Reihenfolge war falsch. Ergebnis: der
Strip deckte nur prev + ungenutzte Kopie + Stitch ab; die korrekten
neuen Vertices lagen ausserhalb und wurden nie gezeichnet. v3 baut
den Vektor in einem Zug: [prev][dup(prev_last)][dup(new_first)][new*].
Kein vector::insert, alles per resize am Ende, amortisiert O(count).

Nur TriangleStrips bekommen den 2-Vertex-Stitch; Triangles und Lines
haengen einfach an. TriangleFans werden nicht gemergt.

Zusaetzlich: WOTS2_NO_MERGE wird jetzt KORREKT interpretiert — "0"
oder unset = Merge an, "1" = aus. Der alte getenv()-Bug (jedes
gesetzte env-Var, auch "0", deaktivierte den Merge) ist behoben.

Zieldatei: src/hal/gs.cpp
Python 3.6+ kompatibel.
"""
import sys
import pathlib

MARKER_V3 = "wots2_merge3d_v3"

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

# v1/v2-Bloecke werden durch v3 ersetzt (falls noch vorhanden).
V1_BLOCK_MARKER = "// wots2-merge-3d-draws.py\n"
V2_BLOCK_MARKER = "// wots2-merge-3d-draws.py (wots2_merge3d_v2)"

V3_BLOCK = '''    if (!own_texture(tex))
        check_live(tex, "a 3D draw with");
    // wots2-merge-3d-draws.py (wots2_merge3d_v3)
    // Merge-Bedingung: gleiche Textur, Primitive, Owner, who, und
    // lueckenloser Vertex-Bereich. WOTS2_NO_MERGE wird korrekt als
    // "0 oder unset = an, 1 = aus" interpretiert (der alte getenv()-
    // !=-nullptr-Bug ist behoben).
    // TriangleStrips: 2-Vertex-Stitch (dup letzter prev, dup erster new).
    // Triangles / Lines: direkt anhaengen.
    // TriangleFans: NICHT mergen (ein gemergter Fan ist kein Fan).
    const u32 tid = tex ? tex : s_white;
    bool merge = false;
    Cmd* pprev = nullptr;
    {
        const char* v = getenv("WOTS2_NO_MERGE");
        const bool no_merge = v != nullptr && v[0] != 0 && v[0] != '0';
        if (!no_merge && !s_cur.cmds.empty() && prim != Prim::TriangleFan) {
            pprev = &s_cur.cmds.back();
            if (pprev->op == Op::Mesh && pprev->tex == tid && pprev->prim == (u8)prim
                && pprev->owner == s_recOwner && pprev->who == s_recWho
                && pprev->count > 0 && count > 0
                && (u64)pprev->first + (u64)pprev->count == (u64)s_cur.v3.size()) {
                merge = true;
            }
        }
    }

    if (merge) {
        if (prim == Prim::TriangleStrip) {
            // [prev .. prev_last][dup prev_last][dup new_first][new*]
            const size_t s0 = s_cur.v3.size();
            s_cur.v3.resize(s0 + 2 + (size_t)count);
            Vertex3* out = s_cur.v3.data() + s0;
            out[0] = s_cur.v3[s0 - 1];
            {
                float c0[4];
                unpack(verts[0].rgba, c0, tid != s_white);
                out[1] = {verts[0].x, verts[0].y, verts[0].z,
                          verts[0].u, verts[0].v, c0[0], c0[1], c0[2], c0[3]};
            }
            out += 2;
            for (int i = 0; i < count; i++) {
                float c0[4];
                unpack(verts[i].rgba, c0, tid != s_white);
                out[i] = {verts[i].x, verts[i].y, verts[i].z,
                          verts[i].u, verts[i].v, c0[0], c0[1], c0[2], c0[3]};
            }
            pprev->count += count + 2;
        } else {
            const size_t s0 = s_cur.v3.size();
            s_cur.v3.resize(s0 + (size_t)count);
            Vertex3* out = s_cur.v3.data() + s0;
            for (int i = 0; i < count; i++) {
                float c0[4];
                unpack(verts[i].rgba, c0, tid != s_white);
                out[i] = {verts[i].x, verts[i].y, verts[i].z,
                          verts[i].u, verts[i].v, c0[0], c0[1], c0[2], c0[3]};
            }
            pprev->count += count;
        }
        for (int k = 0; k < 3; k++) {
            if (lo[k] < pprev->f[k])     pprev->f[k]     = lo[k];
            if (hi[k] > pprev->f[3 + k]) pprev->f[3 + k] = hi[k];
        }
        static const bool trace = getenv("WOTS2_TRACE_MERGE") != nullptr;
        if (trace) {
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
    if MARKER_V3 in t:
        print('  Merge-3D-Draws v3 bereits vorhanden.')
        return
    # v2 erkennen
    if V2_BLOCK_MARKER in t:
        start = t.find("    if (!own_texture(tex))")
        if start < 0:
            print('  FEHLER: v2-Header gefunden, aber Block nicht.', file=sys.stderr)
            sys.exit(1)
        end = t.find("\n}\n", start)
        if end < 0:
            print('  FEHLER: v2-Ende nicht gefunden.', file=sys.stderr)
            sys.exit(1)
        t = t[:start] + V3_BLOCK.rstrip('\n') + t[end:]
        p.write_text(t)
        print('  v2 durch v3 ersetzt (korrekte Stitch-Reihenfolge, env-Fix).')
        return
    # v1 erkennen
    if V1_BLOCK_MARKER in t:
        print('  v1 erkannt — wird durch v3 ersetzt. Bitte manuell v1 entfernen und '
              'v3 auf das ungepatchte gs.cpp anwenden.', file=sys.stderr)
        sys.exit(1)
    # Original
    if ORIGINAL_BLOCK in t:
        t = t.replace(ORIGINAL_BLOCK, V3_BLOCK, 1)
        p.write_text(t)
        print('  v3 auf ungepatchtes gs.cpp angewendet.')
        return
    print('  FEHLER: weder Original- noch v1- noch v2-Block gefunden.', file=sys.stderr)
    sys.exit(1)

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
