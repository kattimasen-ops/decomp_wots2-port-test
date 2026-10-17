#!/usr/bin/env python3
"""
patches/wots2-chara-pose-pool.py — statische Puffer statt std::vector in
CharaModels_Draw und hle_chara_shadow.
Patcht src/native/hle_chara.cpp. Idempotent ueber Marker "wots2_chara_pose_pool".
"""
import sys
import pathlib

MARKER = "wots2_chara_pose_pool"

OLD_1 = '''    // World matrices for the native renderer.  Bones the game moves with its
    // cloth code (top flag bits) hang rigidly off their parents here.
    static std::vector<float> pose, headPose;
    pose.resize((size_t)skeleton->count * 16);
'''

NEW_1 = '''    // wots2_chara_pose_pool: statische Puffer statt std::vector.
    static float s_pose_buf[64 * 16];
    static float s_head_buf[64 * 16];
    if (skeleton->count > 64 || set->head.bones.size() > 64) {
        fprintf(stderr, "[chara] zu viele Bones (%d)\\n", skeleton->count);
        return;
    }
    float* pose = s_pose_buf;
    float* headPose = s_head_buf;
'''

OLD_2 = '''        const size_t count = set->head.bones.size();
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

NEW_2 = '''        const size_t count = set->head.bones.size();
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

def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    if MARKER in t:
        print('  Pose-Pool bereits vorhanden.')
        return
    for old, new, name in [(OLD_1, NEW_1, 'CharaModels_Draw vector'),
                           (OLD_2, NEW_2, 'CharaModels_Draw headPose.resize'),
                           (OLD_3, NEW_3, 'CharaModels_Draw draw'),
                           (OLD_4, NEW_4, 'shadow vector'),
                           (OLD_5, NEW_5, 'shadow draw')]:
        if old not in t:
            print('  FEHLER: Anker %s nicht gefunden.' % name, file=sys.stderr)
            sys.exit(1)
        t = t.replace(old, new, 1)
    p.write_text(t)
    print('  Pose-Pool eingebaut.')

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/native/hle_chara.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
