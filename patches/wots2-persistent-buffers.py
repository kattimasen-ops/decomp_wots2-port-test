#!/usr/bin/env python3
"""
Ersetzt glBufferData in draw-Pfaden durch persistent gemappte Buffer.
Quelle: Halo CE Port host_gl.c, GL_EXT_buffer_storage.
"""
import re, sys, pathlib

def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()
    if 'wots2_persistent_init' in t:
        print('  Persistent Buffers bereits vorhanden.')
        return

    helper = '''
// ── Persistent Mapped Buffers ────────────────────────────────────────────
static bool wots2_has_extension(const char* name) {
    static const char* ext = nullptr;
    if (!ext) ext = (const char*)glGetString(GL_EXTENSIONS);
    return ext && strstr(ext, name) != nullptr;
}

struct PersistentBuffer {
    GLuint buffer = 0;
    uint8_t* mapping = nullptr;
    size_t capacity = 0;
    bool ready = false;
};

static bool wots2_persistent_init(PersistentBuffer& pb, size_t size) {
    if (pb.ready && pb.capacity >= size) return true;
    if (!wots2_has_extension("GL_EXT_buffer_storage")) return false;
    if (!pb.buffer) glGenBuffers(1, &pb.buffer);
    glBindBuffer(GL_ARRAY_BUFFER, pb.buffer);
    typedef void (*BufferStorageFn)(GLenum, GLsizeiptr, const void*, GLbitfield);
    auto fn = (BufferStorageFn)SDL_GL_GetProcAddress("glBufferStorageEXT");
    if (!fn) return false;
    fn(GL_ARRAY_BUFFER, size, nullptr,
       GL_MAP_WRITE_BIT | GL_MAP_PERSISTENT_BIT_EXT | GL_MAP_COHERENT_BIT_EXT);
    pb.mapping = (uint8_t*)glMapBufferRange(GL_ARRAY_BUFFER, 0, size,
       GL_MAP_WRITE_BIT | GL_MAP_PERSISTENT_BIT_EXT | GL_MAP_COHERENT_BIT_EXT);
    if (!pb.mapping) return false;
    pb.capacity = size;
    pb.ready = true;
    return true;
}

static void wots2_persistent_upload(PersistentBuffer& pb, const void* data, size_t size) {
    if (pb.ready && size <= pb.capacity) {
        memcpy(pb.mapping, data, size);
    } else {
        glBindBuffer(GL_ARRAY_BUFFER, pb.buffer);
        glBufferSubData(GL_ARRAY_BUFFER, 0, size, data);
    }
}
'''
    last_inc = list(re.finditer(r'^#include [^\n]+\n', t, re.M))[-1]
    t = t[:last_inc.end()] + helper + t[last_inc.end():]
    p.write_text(t)
    print('  Persistent-Buffer-Helfer eingefügt. Manuelle Verwendung in draw-Aufrufen nötig.')

if __name__ == '__main__':
    patch(sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp')
