#!/usr/bin/env python3
"""
patches/wots2-map-batching.py

Batches map meshes by (texture, bias) instead of (texture, bias, tile).
Ranges within a batch keep per-tile bounding boxes; culling happens per range
at draw time.

The single glBufferData per batch replaces ~N per-tile glBufferData calls.
For 124 draws in the town that's ~124 buffer uploads down to ~15.

Files changed (idempotent, marker wots2_map_batching_v1):
  include/native/model.h    — Batch struct gets `ranges`
  include/hal/gs.h          — MeshRange struct, draw_mesh_ranged decl
  src/native/model.cpp      — batching logic + ranged draw call
  src/hal/gs.cpp            — draw_mesh_ranged impl, ranged Op::Mesh handling

WOTS2_NO_MAP_BATCHING=1 disables the ranged path (map draws as one batch,
no per-tile culling — correct image, slower than pre-patch).

Called with the repo root:
    python3 wots2-map-batching.py .
"""
import sys
import pathlib
import re

MARKER = "wots2_map_batching_v1"


# ══════════════════════════════════════════════════════════════════════════
def patch_h_model_h(root):
    path = root / "include" / "native" / "model.h"
    if not path.exists():
        print(f"  FEHLER: {path} nicht gefunden", file=sys.stderr)
        return False
    t = path.read_text()
    if MARKER in t:
        print(f"  {path.name}: bereits gepatcht.")
        return True

    old = '''    struct Batch {
        u32 tex = 0;
        int bias = 0;
        int tile = 0;               // a map's: which 16 × 16 square it lies in (so that it can be culled)
        bool overlay = false;
        std::vector<hal::gs::Vtx3> verts;
    };'''
    new = '''    // wots2_map_batching_v1: a map's batch is keyed only by (tex, bias);
    // `ranges` carries per-tile vertex ranges used for culling.
    struct Batch {
        u32 tex = 0;
        int bias = 0;
        bool overlay = false;
        std::vector<hal::gs::Vtx3> verts;
        std::vector<hal::gs::MeshRange> ranges;  // empty = draw all verts
    };'''
    if old not in t:
        print(f"  FEHLER: Batch-Struct in {path.name} nicht gefunden", file=sys.stderr)
        return False
    t = t.replace(old, new, 1)
    path.write_text(t)
    print(f"  {path.name}: Batch um ranges erweitert.")
    return True


# ══════════════════════════════════════════════════════════════════════════
def patch_h_gs_h(root):
    path = root / "include" / "hal" / "gs.h"
    if not path.exists():
        print(f"  FEHLER: {path} nicht gefunden", file=sys.stderr)
        return False
    t = path.read_text()
    if MARKER in t:
        print(f"  {path.name}: bereits gepatcht.")
        return True

    # 1. MeshRange after Vtx3
    m = re.search(r'(struct\s+Vtx3\s*\{[^{}]*\};)', t)
    if not m:
        print(f"  FEHLER: struct Vtx3 in {path.name} nicht gefunden", file=sys.stderr)
        return False
    decl = m.group(1)
    newdecl = decl + '''

// wots2_map_batching_v1
struct MeshRange {
    u32 first;      // vertex offset within the batch
    u32 count;      // vertex count
    int tile;       // grouping tag (used by model batching, ignored by gs)
    float box[6];   // world AABB: lo xyz then hi xyz
};'''
    t = t.replace(decl, newdecl, 1)

    # 2. draw_mesh_ranged after draw_mesh
    m = re.search(r'(void\s+draw_mesh\s*\([^;{}]*\)\s*;)', t)
    if not m:
        print(f"  FEHLER: void draw_mesh(...) in {path.name} nicht gefunden", file=sys.stderr)
        return False
    dm = m.group(1)
    newdm = dm + '''

// wots2_map_batching_v1
void draw_mesh_ranged(u32 tex, const Vtx3* verts, int count, Prim prim,
                      const MeshRange* ranges, int range_count);'''
    t = t.replace(dm, newdm, 1)

    path.write_text(t)
    print(f"  {path.name}: MeshRange + draw_mesh_ranged hinzugefuegt.")
    return True


# ══════════════════════════════════════════════════════════════════════════
def patch_cpp_model(root):
    path = root / "src" / "native" / "model.cpp"
    if not path.exists():
        print(f"  FEHLER: {path} nicht gefunden", file=sys.stderr)
        return False
    t = path.read_text()
    if MARKER in t:
        print(f"  {path.name}: bereits gepatcht.")
        return True

    # 1. Batch key: drop tile, add ranges
    old = '''            Batch* batch = nullptr;
            const int tile = fixed && !strip.verts.empty()
                           ? (int)floorf(strip.verts[0].p1[0] / 16.0f) * 4096 + (int)floorf(strip.verts[0].p1[2] / 16.0f)
                           : 0;
            if (fixed) {
                for (Batch& b : batches)
                    if (b.tex == tex && b.bias == bias && b.tile == tile && b.overlay == (pass == 1)) {
                        batch = &b;
                        break;
                    }
            } else if (!batches.empty() && batches.back().tex == tex && batches.back().bias == bias &&
                       batches.back().overlay == (pass == 1)) {
                batch = &batches.back();
            }
            if (batch == nullptr) {
                batches.emplace_back();
                batch = &batches.back();
                batch->tex = tex;
                batch->bias = bias;
                batch->tile = tile;
                batch->overlay = pass == 1;
            }'''
    new = '''            // wots2_map_batching_v1: batches group by (tex, bias);
            // tile info lives in `ranges`.
            Batch* batch = nullptr;
            const int tile = fixed && !strip.verts.empty()
                           ? (int)floorf(strip.verts[0].p1[0] / 16.0f) * 4096 + (int)floorf(strip.verts[0].p1[2] / 16.0f)
                           : 0;
            if (fixed) {
                for (Batch& b : batches)
                    if (b.tex == tex && b.bias == bias && b.overlay == (pass == 1)) {
                        batch = &b;
                        break;
                    }
            } else if (!batches.empty() && batches.back().tex == tex && batches.back().bias == bias &&
                       batches.back().overlay == (pass == 1)) {
                batch = &batches.back();
            }
            if (batch == nullptr) {
                batches.emplace_back();
                batch = &batches.back();
                batch->tex = tex;
                batch->bias = bias;
                batch->overlay = pass == 1;
            }
            hal::gs::MeshRange* current_range = nullptr;
            if (fixed) {
                if (!batch->ranges.empty() && batch->ranges.back().tile == tile)
                    current_range = &batch->ranges.back();
                if (!current_range) {
                    batch->ranges.emplace_back();
                    current_range = &batch->ranges.back();
                    current_range->first = (u32)batch->verts.size();
                    current_range->count = 0;
                    current_range->tile = tile;
                    current_range->box[0] = 1e30f;
                    current_range->box[1] = 1e30f;
                    current_range->box[2] = 1e30f;
                    current_range->box[3] = -1e30f;
                    current_range->box[4] = -1e30f;
                    current_range->box[5] = -1e30f;
                }
            }'''
    if old not in t:
        print(f"  FEHLER: Batch-Key-Block in {path.name} nicht gefunden", file=sys.stderr)
        return False
    t = t.replace(old, new, 1)

    # 2. Vertex pushes routed through push_ranged
    old = '''                const hal::gs::Vtx3 point = {p[0], p[1], p[2], v.u, v.v, rgba};
                if (strip.list) {
                    batch->verts.push_back(point);
                } else {
                    if (index >= 2) {
                        batch->verts.push_back(window[0]);
                        batch->verts.push_back(window[1]);
                        batch->verts.push_back(point);
                    }
                    window[0] = window[1];
                    window[1] = point;
                }
                index++;'''
    new = '''                const hal::gs::Vtx3 point = {p[0], p[1], p[2], v.u, v.v, rgba};
                // wots2_map_batching_v1
                auto push_ranged = [&](const hal::gs::Vtx3& p3) {
                    batch->verts.push_back(p3);
                    if (current_range) {
                        current_range->count++;
                        if (p3.x < current_range->box[0]) current_range->box[0] = p3.x;
                        if (p3.y < current_range->box[1]) current_range->box[1] = p3.y;
                        if (p3.z < current_range->box[2]) current_range->box[2] = p3.z;
                        if (p3.x > current_range->box[3]) current_range->box[3] = p3.x;
                        if (p3.y > current_range->box[4]) current_range->box[4] = p3.y;
                        if (p3.z > current_range->box[5]) current_range->box[5] = p3.z;
                    }
                };
                if (strip.list) {
                    push_ranged(point);
                } else {
                    if (index >= 2) {
                        push_ranged(window[0]);
                        push_ranged(window[1]);
                        push_ranged(point);
                    }
                    window[0] = window[1];
                    window[1] = point;
                }
                index++;'''
    if old not in t:
        print(f"  FEHLER: Vertex-Push-Block in {path.name} nicht gefunden", file=sys.stderr)
        return False
    t = t.replace(old, new, 1)

    # 3. Ranged draw at the end
    old = '''    for (const Batch& batch : batches) {
        if (batch.verts.empty())
            continue;
        hal::gs::set_depth_bias(batch.bias);
        hal::gs::set_overlay(batch.overlay);
        hal::gs::draw_mesh(batch.tex, batch.verts.data(), (int)batch.verts.size(), hal::gs::Prim::Triangles);
    }'''
    new = '''    const bool no_batch = getenv("WOTS2_NO_MAP_BATCHING") != nullptr;   // wots2_map_batching_v1
    for (const Batch& batch : batches) {
        if (batch.verts.empty())
            continue;
        hal::gs::set_depth_bias(batch.bias);
        hal::gs::set_overlay(batch.overlay);
        if (!no_batch && !batch.ranges.empty())
            hal::gs::draw_mesh_ranged(batch.tex, batch.verts.data(), (int)batch.verts.size(),
                                      hal::gs::Prim::Triangles,
                                      batch.ranges.data(), (int)batch.ranges.size());
        else
            hal::gs::draw_mesh(batch.tex, batch.verts.data(), (int)batch.verts.size(), hal::gs::Prim::Triangles);
    }'''
    if old not in t:
        print(f"  FEHLER: Draw-Block in {path.name} nicht gefunden", file=sys.stderr)
        return False
    t = t.replace(old, new, 1)

    t = t.replace('#include "native/model.h"',
                  '#include "native/model.h"\n// ' + MARKER, 1)
    path.write_text(t)
    print(f"  {path.name}: Batching + ranged draw.")
    return True


# ══════════════════════════════════════════════════════════════════════════
def patch_cpp_gs(root):
    path = root / "src" / "hal" / "gs.cpp"
    if not path.exists():
        print(f"  FEHLER: {path} nicht gefunden", file=sys.stderr)
        return False
    t = path.read_text()
    if MARKER in t:
        print(f"  {path.name}: bereits gepatcht.")
        return True

    # 1. kRanged flag
    old = 'enum : u8 { kHasZ = 1, kUvRect = 2, kFrameTex = 4, kSpan = 8 };'
    new = 'enum : u8 { kHasZ = 1, kUvRect = 2, kFrameTex = 4, kSpan = 8, kRanged = 16 };  // wots2_map_batching_v1'
    if old not in t:
        print(f"  FEHLER: Flag-Enum in {path.name} nicht gefunden", file=sys.stderr)
        return False
    t = t.replace(old, new, 1)

    # 2. Frame::ranges3
    old = '''    std::vector<Vertex3> v3;
    std::unordered_map<u64, std::vector<u32>> index;'''
    new = '''    std::vector<Vertex3> v3;
    std::vector<hal::gs::MeshRange> ranges3;   // wots2_map_batching_v1
    std::unordered_map<u64, std::vector<u32>> index;'''
    if old not in t:
        print(f"  FEHLER: Frame-Struct in {path.name} nicht gefunden", file=sys.stderr)
        return False
    t = t.replace(old, new, 1)

    # 3. Frame::clear
    old = 'cmds.clear(); v2.clear(); v3.clear(); index.clear();'
    new = 'cmds.clear(); v2.clear(); v3.clear(); ranges3.clear(); index.clear();'
    if old not in t:
        print(f"  FEHLER: Frame::clear in {path.name} nicht gefunden", file=sys.stderr)
        return False
    t = t.replace(old, new, 1)

    # 4. draw_mesh_ranged after draw_mesh
    old = '''    c.owner = s_recOwner;
    c.who = s_recWho;
}

// (Kept as the game gave them — screen positions with a depth each, and
// turned into clip space when played.)'''
    new = '''    c.owner = s_recOwner;
    c.who = s_recWho;
}

// wots2_map_batching_v1
void draw_mesh_ranged(u32 tex, const Vtx3* verts, int count, Prim prim,
                      const MeshRange* ranges, int range_count) {
    const u32 first = (u32)s_cur.v3.size();
    s_cur.v3.resize((size_t)first + (size_t)count);
    Vertex3* out = s_cur.v3.data() + first;
    float lo[3] = {1e30f, 1e30f, 1e30f}, hi[3] = {-1e30f, -1e30f, -1e30f};
    for (int i = 0; i < count; i++) {
        float c[4];
        unpack(verts[i].rgba, c, tex != 0);
        out[i] = {verts[i].x, verts[i].y, verts[i].z, verts[i].u, verts[i].v, c[0], c[1], c[2], c[3]};
        const float p[3] = {verts[i].x, verts[i].y, verts[i].z};
        for (int k = 0; k < 3; k++) {
            lo[k] = p[k] < lo[k] ? p[k] : lo[k];
            hi[k] = p[k] > hi[k] ? p[k] : hi[k];
        }
    }
    if (!own_texture(tex))
        check_live(tex, "a 3D draw with");
    const u32 range_offset = (u32)s_cur.ranges3.size();
    s_cur.ranges3.insert(s_cur.ranges3.end(), ranges, ranges + range_count);
    Cmd& c = push(Op::Mesh);
    c.flags |= kRanged;
    c.tex = tex ? tex : s_white;
    c.prim = (u8)prim;
    c.first = first;
    c.count = count;
    c.i = (int)range_offset;
    c.z = (u32)range_count;
    c.owner = s_recOwner;
    c.who = s_recWho;
    memcpy(c.f, lo, sizeof lo);
    memcpy(c.f + 3, hi, sizeof hi);
}

// (Kept as the game gave them — screen positions with a depth each, and
// turned into clip space when played.)'''
    if old not in t:
        print(f"  FEHLER: draw_mesh-Ende in {path.name} nicht gefunden", file=sys.stderr)
        return False
    t = t.replace(old, new, 1)

    # 5. Ranged handling in Op::Mesh
    old = '''        case Op::Mesh: {
            if (culled(c, before)) {
                s_culled++;
                break;
            }
            s_drawn++;
            const Vertex3* v = verts3(f, c, before, t);
            glBindTexture(GL_TEXTURE_2D, c.tex);
            const bool cutout = !s_overlayOn && s_cutout.count(c.tex);
            glUniform1i(s_uCutout, cutout ? 1 : 0);
            if (c.tex != s_white) {     // model textures tile
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT);
            }
            glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)((size_t)c.count * sizeof(Vertex3)), v, GL_STREAM_DRAW);
            glDrawArrays(gl_prim(c.prim), 0, c.count);'''
    new = '''        case Op::Mesh: {
            if (culled(c, before)) {
                s_culled++;
                break;
            }
            // wots2_map_batching_v1: ranged path
            static const bool s_no_map_batching = getenv("WOTS2_NO_MAP_BATCHING") != nullptr;
            if ((c.flags & kRanged) && !s_no_map_batching) {
                const hal::gs::MeshRange* ranges = f.ranges3.data() + c.i;
                const int range_count = (int)c.z;
                int visible = 0;
                for (int k = 0; k < range_count; k++)
                    if (!box_outside(ranges[k].box, ranges[k].box + 3, s_playMvp, s_playXScale))
                        visible++;
                if (visible == 0) {
                    s_culled += range_count;
                    break;
                }
                s_drawn += visible;
                s_culled += range_count - visible;
                const Vertex3* v = verts3(f, c, before, t);
                glBindTexture(GL_TEXTURE_2D, c.tex);
                const bool cutout = !s_overlayOn && s_cutout.count(c.tex);
                glUniform1i(s_uCutout, cutout ? 1 : 0);
                if (c.tex != s_white) {
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT);
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT);
                }
                glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)((size_t)c.count * sizeof(Vertex3)), v, GL_STREAM_DRAW);
                for (int k = 0; k < range_count; k++) {
                    if (box_outside(ranges[k].box, ranges[k].box + 3, s_playMvp, s_playXScale))
                        continue;
                    glDrawArrays(gl_prim(c.prim), (GLint)ranges[k].first, (GLsizei)ranges[k].count);
                }
                if (cutout) {
                    glUniform1i(s_uCutout, 2);
                    overlay(true);
                    for (int k = 0; k < range_count; k++) {
                        if (box_outside(ranges[k].box, ranges[k].box + 3, s_playMvp, s_playXScale))
                            continue;
                        glDrawArrays(gl_prim(c.prim), (GLint)ranges[k].first, (GLsizei)ranges[k].count);
                    }
                    overlay(false);
                    glUniform1i(s_uCutout, 0);
                }
                break;
            }
            s_drawn++;
            const Vertex3* v = verts3(f, c, before, t);
            glBindTexture(GL_TEXTURE_2D, c.tex);
            const bool cutout = !s_overlayOn && s_cutout.count(c.tex);
            glUniform1i(s_uCutout, cutout ? 1 : 0);
            if (c.tex != s_white) {     // model textures tile
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT);
            }
            glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)((size_t)c.count * sizeof(Vertex3)), v, GL_STREAM_DRAW);
            glDrawArrays(gl_prim(c.prim), 0, c.count);'''
    if old not in t:
        print(f"  FEHLER: Op::Mesh-Case in {path.name} nicht gefunden", file=sys.stderr)
        return False
    t = t.replace(old, new, 1)

    # 6. Skip pairing for ranged meshes
    old = '''        Cmd& c = f.cmds[j];
        if (c.op != Op::Mesh || c.match < 0 || p.cmds[(size_t)c.match].owner != owner || c.count == 0)
            continue;'''
    new = '''        Cmd& c = f.cmds[j];
        if (c.op != Op::Mesh || (c.flags & kRanged) || c.match < 0 ||
            p.cmds[(size_t)c.match].owner != owner || c.count == 0)
            continue;'''
    if old not in t:
        print(f"  FEHLER: pair_frames-Inner-Loop in {path.name} nicht gefunden", file=sys.stderr)
        return False
    t = t.replace(old, new, 1)

    t = t.replace('#include "hal/gs.h"',
                  '#include "hal/gs.h"\n// ' + MARKER, 1)
    path.write_text(t)
    print(f"  {path.name}: Ranged-Op::Mesh-Handling.")
    return True


# ══════════════════════════════════════════════════════════════════════════
def main():
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    print(f"Patche {root}")
    ok = True
    ok &= patch_h_model_h(root)
    ok &= patch_h_gs_h(root)
    ok &= patch_cpp_model(root)
    ok &= patch_cpp_gs(root)
    if not ok:
        print("Fertig mit Fehlern.", file=sys.stderr)
        sys.exit(1)
    print("Fertig.")


if __name__ == '__main__':
    main()
