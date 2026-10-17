#!/usr/bin/env python3
"""
patches/wots2-chara-pose-pool.py  (v3)

Ersetzt std::vector<float> pose/headPose in CharaModels_Draw und
hle_chara_shadow durch statische float-Arrays. Kein malloc/free pro
Frame pro Charakter mehr.

v2 behebt den Compile-Fehler aus v1:
    const float* bodyPose = pose.data();
blieb ungepatcht. v1 hatte nur die drei .data()-Aufrufe in den draw()-
Methoden ersetzt, nicht die Zuweisung an bodyPose.

v3 behebt den Konflikt mit wots2-chara-draw-lod.py: der hat in
CharaModels_Draw die Zeile
    if (i < 28 && i < (size_t)skeleton->count) {
zu
    if (!skip && i < 28 && i < (size_t)skeleton->count) {
erweitert. v2 kannte nur die Originalform und brach deshalb ab.
v3 versucht beide Varianten (skip zuerst, noskip als Fallback) und
behaelt das !skip in NEW_2_skip — sonst wuerde der Pose-Pool-Patch
die Draw-Skip-Logik rueckgaengig machen.

v3 ist pro Block idempotent: jeder OLD-Block wird durch seinen
NEW-Block ersetzt, wenn er noch da ist; ist er schon durch NEW
ersetzt, bleibt er. So laeuft der Patch sowohl auf frischem Source
als auch auf Source, das schon v2-gepatcht ist.

Patcht src/native/hle_chara.cpp. Marker "wots2_chara_pose_pool".
"""
import sys
import pathlib

MARKER = "wots2_chara_pose_pool"

OLD_1 = '''    // World matrices for the native renderer.  Bones the game moves with its
    // cloth code (top flag bits) hang rigidly off their parents here.
    static std::vector<float> pose, headPose;
    pose.resize((size_t)skeleton->count * 16);
'''

NEW_1 = '''    // World matrices for the native renderer.  Bones the game moves with its
    // cloth code (top flag bits) hang rigidly off their parents here.
    // wots2_chara_pose_pool: statische Puffer statt std::vector.
    static float s_pose_buf[64 * 16];
    static float s_head_buf[64 * 16];
    if (skeleton->count > 64 || set->head.bones.size() > 64) {
        fprintf(stderr, "[chara] zu viele Bones (%d)\\n", skeleton->count);
        return;
    }
    float* pose = s_pose_buf;
    float* headPose = s_head_buf;
'''

# Zwei Varianten von OLD_2/NEW_2:
#   _skip   = mit  !skip &&  (nach wots2-chara-draw-lod.py)
#   _noskip = ohne !skip &&   (frischer Source, ohne chara-draw-lod.py)
# Wichtig: NEW_2_skip behaelt !skip, sonst wuerde der Pose-Pool-Patch
# die Draw-Skip-Logik rueckgaengig machen.
OLD_2_skip = '''        const size_t count = set->head.bones.size();
        headPose.resize(count * 16);
        for (size_t i = 0; i < count; i++) {
            float* out = &headPose[i * 16];
            if (!skip && i < 28 && i < (size_t)skeleton->count) {
                memcpy(out, &pose[i * 16], 64);
            } else {
                const int parent = set->head.bones[i].parent;
                if (parent >= 0 && (size_t)parent < i)
                    mat_mul(set->head.bones[i].local, &headPose[(size_t)parent * 16], out);
                else
                    mat_mul(set->head.bones[i].local, matrix, out);
            }
        }
    }

    float mvp[16];
'''

NEW_2_skip = '''        const size_t count = set->head.bones.size();
        // wots2_chara_pose_pool: kein resize
        for (size_t i = 0; i < count; i++) {
            float* out = &headPose[i * 16];
            if (!skip && i < 28 && i < (size_t)skeleton->count) {
                memcpy(out, &pose[i * 16], 64);
            } else {
                const int parent = set->head.bones[i].parent;
                if (parent >= 0 && (size_t)parent < i)
                    mat_mul(set->head.bones[i].local, &headPose[(size_t)parent * 16], out);
                else
                    mat_mul(set->head.bones[i].local, matrix, out);
            }
        }
    }

    float mvp[16];
'''

OLD_2_noskip = '''        const size_t count = set->head.bones.size();
        headPose.resize(count * 16);
        for (size_t i = 0; i < count; i++) {
            float* out = &headPose[i * 16];
            if (i < 28 && i < (size_t)skeleton->count) {
                memcpy(out, &pose[i * 16], 64);
            } else {
                const int parent = set->head.bones[i].parent;
                if (parent >= 0 && (size_t)parent < i)
                    mat_mul(set->head.bones[i].local, &headPose[(size_t)parent * 16], out);
                else
                    mat_mul(set->head.bones[i].local, matrix, out);
            }
        }
    }

    float mvp[16];
'''

NEW_2_noskip = '''        const size_t count = set->head.bones.size();
        // wots2_chara_pose_pool: kein resize
        for (size_t i = 0; i < count; i++) {
            float* out = &headPose[i * 16];
            if (i < 28 && i < (size_t)skeleton->count) {
                memcpy(out, &pose[i * 16], 64);
            } else {
                const int parent = set->head.bones[i].parent;
                if (parent >= 0 && (size_t)parent < i)
                    mat_mul(set->head.bones[i].local, &headPose[(size_t)parent * 16], out);
                else
                    mat_mul(set->head.bones[i].local, matrix, out);
            }
        }
    }

    float mvp[16];
'''

OLD_6 = '''    const float* bodyPose = pose.data();
    if (set->body.bones.size() > (size_t)skeleton->count)
        bodyPose = nullptr;
'''

NEW_6 = '''    const float* bodyPose = pose;   // wots2_chara_pose_pool
    if (set->body.bones.size() > (size_t)skeleton->count)
        bodyPose = nullptr;
'''

OLD_3 = '''    if (bodyPose)
        set->body.draw(bodyPose, set->hasShared ? &set->shared : nullptr, &light);
    if (set->hasHead)
        set->head.draw(headPose.data(), set->hasShared ? &set->shared : nullptr, &light);
    hal::gs::end_3d();
}
'''

NEW_3 = '''    if (bodyPose)
        set->body.draw(bodyPose, set->hasShared ? &set->shared : nullptr, &light);
    if (set->hasHead)
        set->head.draw(headPose, set->hasShared ? &set->shared : nullptr, &light);
    hal::gs::end_3d();
}
'''

OLD_4 = '''    std::vector<float> pose((size_t)skeleton->count * 16), headPose;
    for (int i = 0; i < skeleton->count; i++)
        memcpy(&pose[(size_t)i * 16], bones[i].world, 64);
    if (set->body.bones.size() > (size_t)skeleton->count)
        return;
    if (set->hasHead) {
        const size_t count = set->head.bones.size();
        headPose.resize(count * 16);
        for (size_t i = 0; i < count; i++) {
            float* out = &headPose[i * 16];
            if (i < 28 && i < (size_t)skeleton->count) {
                memcpy(out, &pose[i * 16], 64);
            } else {
                const int parent = set->head.bones[i].parent;
                if (parent >= 0 && (size_t)parent < i)
                    mat_mul(set->head.bones[i].local, &headPose[(size_t)parent * 16], out);
                else
                    mat_mul(set->head.bones[i].local, p->matrix, out);
            }
        }
    }
'''

NEW_4 = '''    // wots2_chara_pose_pool
    static float s_shadow_pose[64 * 16];
    static float s_shadow_head[64 * 16];
    if (skeleton->count > 64 || set->head.bones.size() > 64)
        return;
    float* pose = s_shadow_pose;
    float* headPose = s_shadow_head;
    for (int i = 0; i < skeleton->count; i++)
        memcpy(&pose[(size_t)i * 16], bones[i].world, 64);
    if (set->body.bones.size() > (size_t)skeleton->count)
        return;
    if (set->hasHead) {
        const size_t count = set->head.bones.size();
        for (size_t i = 0; i < count; i++) {
            float* out = &headPose[i * 16];
            if (i < 28 && i < (size_t)skeleton->count) {
                memcpy(out, &pose[i * 16], 64);
            } else {
                const int parent = set->head.bones[i].parent;
                if (parent >= 0 && (size_t)parent < i)
                    mat_mul(set->head.bones[i].local, &headPose[(size_t)parent * 16], out);
                else
                    mat_mul(set->head.bones[i].local, p->matrix, out);
            }
        }
    }
'''

OLD_5 = '''    hal::gs::begin_target(256);
    hal::gs::begin_3d(fromLight);
    set->body.draw(pose.data(), set->hasShared ? &set->shared : nullptr, &black);
    if (set->hasHead)
        set->head.draw(headPose.data(), set->hasShared ? &set->shared : nullptr, &black);
    hal::gs::end_3d();
'''

NEW_5 = '''    hal::gs::begin_target(256);
    hal::gs::begin_3d(fromLight);
    set->body.draw(pose, set->hasShared ? &set->shared : nullptr, &black);
    if (set->hasHead)
        set->head.draw(headPose, set->hasShared ? &set->shared : nullptr, &black);
    hal::gs::end_3d();
'''

# Blocks: [(name, [(old, new), (old_alt, new_alt), ...]), ...]
# Pro Name wird der erste passende OLD eingesetzt; wenn keiner passt,
# aber ein NEW schon drin ist, gilt der Block als "bereits vorhanden".
BLOCKS = [
    ('CharaModels_Draw vector decl', [
        (OLD_1, NEW_1),
    ]),
    ('CharaModels_Draw headPose.resize', [
        (OLD_2_skip,   NEW_2_skip),
        (OLD_2_noskip, NEW_2_noskip),
    ]),
    ('CharaModels_Draw bodyPose (pose.data)', [
        (OLD_6, NEW_6),
    ]),
    ('CharaModels_Draw head draw', [
        (OLD_3, NEW_3),
    ]),
    ('shadow vector decl', [
        (OLD_4, NEW_4),
    ]),
    ('shadow draw', [
        (OLD_5, NEW_5),
    ]),
]


def apply_block(t, name, variants):
    # Erst alle OLD-Varianten durchprobieren.
    for old, new in variants:
        if old in t:
            t = t.replace(old, new, 1)
            print(f'  {name}: ersetzt')
            return t, True
    # Falls keiner passt, pruefen ob schon gepatcht.
    for _, new in variants:
        if new in t:
            print(f'  {name}: bereits vorhanden')
            return t, True
    print(f'  FEHLER: {name} nicht gefunden', file=sys.stderr)
    return t, False


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()

    if MARKER in t and 'const float* bodyPose = pose;' in t:
        # Bestehender Marker + vollstaendig eingebaut. Nichts zu tun.
        # Aber pruefen, ob die Skip-Variante noch drin ist, falls
        # chara-draw-lod.py danach nochmal drueber lief.
        if '!skip && i < 28' in t:
            print('  Pose-Pool bereits vollstaendig vorhanden.')
        else:
            print('  Pose-Pool-Marker da, aber skip-Variante fehlt — neu bauen.')
        return

    all_ok = True
    for name, variants in BLOCKS:
        t, ok = apply_block(t, name, variants)
        if not ok:
            all_ok = False
            break  # Abbruch vor dem Schreiben — kein halb gepatchtes Binary.

    if not all_ok:
        sys.exit(1)

    if MARKER not in t:
        t = t.replace('#include "native/model.h"',
                      '#include "native/model.h"\n// ' + MARKER, 1)

    p.write_text(t)
    print('  Pose-Pool eingebaut/aktualisiert.')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/native/hle_chara.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
