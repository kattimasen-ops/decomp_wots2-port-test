#!/usr/bin/env python3
"""
patches/wots2-gs-shader-cache.py   (v3 — 2026-10-22)

Shader-Programm-Cache mit glProgramBinary (Mali-G31).

Bug (v2): Der Patch hat drei Probleme, die in der aktuellen gs.cpp stehen:
  1. wots2_link_cached() rief sich selbst auf (Endlosrekursion)
  2. link() rief wots2_link_cached() NIE auf — der Cache war toter Code
  3. s_program und s_program3d wurden in init() inline kompiliert,
     gingen also am Cache vorbei

v3 MIGRIERT den kaputten Zustand in deiner aktuellen gs.cpp:
  - wots2_link_cached  -> echte Funktion (load, sonst compile+link+store)
  - link               -> return wots2_link_cached(vsSrc, fsSrc)
  - init() s_program   -> wots2_shader_cache_init VOR link()
  - init() s_program3d -> link(kVertexShader3d, kFragmentShader3d)
  - die 6 Post-Programme in lighting_init() rufen bereits link() auf,
    profitieren automatisch

Hinweis zur Erwartung: Das ist Startzeit-Optimierung, keine FPS-Aenderung.
Bei GLES-Treibern ohne glGetProgramBinary (len <= 0) faellt der Cache
still zurueck auf "immer kompilieren" — kein Absturz.

Idempotent: prueft auf 's_program = link(kVertexShader, kFragmentShader)'
als Korrektheitsmarker.

Zieldatei: src/hal/gs.cpp
"""
import re
import sys
import pathlib


HELPER = r'''
// ── Shader-Programm-Cache mit LRU-Unload (Mali-G31) ──────────────────
// Siehe patches/wots2-gs-shader-cache.py.
#include <cstdint>
#include <cstring>

struct Wots2ProgramEntry {
    GLuint program;
    uint64_t hash;
    int    last_used_frame;
    int    bind_count;
};
static std::vector<Wots2ProgramEntry> s_programCache;
static bool  s_shaderCacheEnabled = true;
static int   s_shaderLruFrames = 600;
static char  s_shaderCacheDir[512] = {};
static uint64_t s_shaderDriverKey = 0;

static uint64_t wots2_hash_str(const char* s) {
    uint64_t h = 1469598103934665603ULL;
    while (*s) { h ^= (uint64_t)(unsigned char)*s++; h *= 1099511628211ULL; }
    return h;
}

static void wots2_shader_cache_init(const char* data_root) {
    const char* env = getenv("WOTS2_SHADER_CACHE");
    if (env && env[0] == '0') {
        s_shaderCacheEnabled = false;
        fprintf(stderr, "[shader-cache] deaktiviert per Env\n");
        return;
    }
    if (const char* n = getenv("WOTS2_SHADER_LRU"))
        s_shaderLruFrames = atoi(n);
    if (data_root && data_root[0]) {
        snprintf(s_shaderCacheDir, sizeof(s_shaderCacheDir),
                 "%s/shader_cache", data_root);
        char cmd[600];
        snprintf(cmd, sizeof(cmd), "mkdir -p '%s' 2>/dev/null", s_shaderCacheDir);
        if (system(cmd) != 0) { /* ignorieren */ }
    }
    const char* ver = (const char*)glGetString(GL_VERSION);
    const char* ren = (const char*)glGetString(GL_RENDERER);
    s_shaderDriverKey = wots2_hash_str(ver ? ver : "?") ^ (wots2_hash_str(ren ? ren : "?") << 1);
    fprintf(stderr, "[shader-cache] aktiviert, dir=%s, driver=%08llx\n",
            s_shaderCacheDir, (unsigned long long)s_shaderDriverKey);
}

static void wots2_shader_cache_store(GLuint program, const char* tag) {
    if (!s_shaderCacheEnabled || s_shaderCacheDir[0] == 0)
        return;
    GLint len = 0;
    glGetProgramiv(program, GL_PROGRAM_BINARY_LENGTH, &len);
    if (len <= 0)
        return;
    std::vector<unsigned char> buf((size_t)len);
    GLenum fmt = 0;
    GLsizei got = 0;
    glGetProgramBinary(program, len, &got, &fmt, buf.data());
    if (got <= 0)
        return;
    char path[700];
    snprintf(path, sizeof(path), "%s/%s_%08llx.bin",
             s_shaderCacheDir, tag, (unsigned long long)(s_shaderDriverKey & 0xFFFFFFFF));
    FILE* f = fopen(path, "wb");
    if (!f)
        return;
    uint32_t magic = 0x574F5453;
    uint32_t glFmt = (uint32_t)fmt;
    uint32_t len32 = (uint32_t)got;
    fwrite(&magic, 4, 1, f);
    fwrite(&s_shaderDriverKey, sizeof(s_shaderDriverKey), 1, f);
    fwrite(&glFmt, 4, 1, f);
    fwrite(&len32, 4, 1, f);
    fwrite(buf.data(), 1, (size_t)got, f);
    fclose(f);
}

static bool wots2_shader_cache_load(GLuint program, const char* tag) {
    if (!s_shaderCacheEnabled || s_shaderCacheDir[0] == 0)
        return false;
    char path[700];
    snprintf(path, sizeof(path), "%s/%s_%08llx.bin",
             s_shaderCacheDir, tag, (unsigned long long)(s_shaderDriverKey & 0xFFFFFFFF));
    FILE* f = fopen(path, "rb");
    if (!f)
        return false;
    uint32_t magic = 0, glFmt = 0, len32 = 0;
    uint64_t key = 0;
    if (fread(&magic, 4, 1, f) != 1 || magic != 0x574F5453 ||
        fread(&key, sizeof(key), 1, f) != 1 || key != s_shaderDriverKey ||
        fread(&glFmt, 4, 1, f) != 1 ||
        fread(&len32, 4, 1, f) != 1 || len32 == 0 || len32 > (32u << 20)) {
        fclose(f);
        remove(path);
        return false;
    }
    std::vector<unsigned char> buf(len32);
    size_t got = fread(buf.data(), 1, len32, f);
    fclose(f);
    if (got != len32)
        return false;
    glProgramBinary(program, (GLenum)glFmt, buf.data(), (GLsizei)len32);
    GLint ok = 0;
    glGetProgramiv(program, GL_LINK_STATUS, &ok);
    if (ok)
        return true;
    remove(path);
    return false;
}

static void wots2_shader_cache_tick(int frame) {
    if (!s_shaderCacheEnabled || s_shaderLruFrames <= 0)
        return;
    if (frame < 60)
        return;
    for (size_t i = 0; i < s_programCache.size(); ) {
        if (frame - s_programCache[i].last_used_frame > s_shaderLruFrames) {
            glDeleteProgram(s_programCache[i].program);
            s_programCache[i] = s_programCache.back();
            s_programCache.pop_back();
        } else {
            ++i;
        }
    }
}

static void wots2_shader_cache_note_use(GLuint program, int frame) {
    for (auto& e : s_programCache) {
        if (e.program == program) {
            e.last_used_frame = frame;
            e.bind_count++;
            return;
        }
    }
    s_programCache.push_back({program, 0, frame, 1});
}

static void wots2_shader_cache_tag(const char* vs, const char* fs, char* out, size_t out_size) {
    uint64_t h = wots2_hash_str(vs ? vs : "") ^ (wots2_hash_str(fs ? fs : "") << 1);
    snprintf(out, out_size, "p%016llx", (unsigned long long)h);
}
'''

# Der kaputte Funktionsblock in der aktuellen gs.cpp
LINK_BROKEN = """// Cached-Variante von link(): versucht erst den Binary-Cache, sonst
// kompiliert sie und legt das Ergebnis ab. Der Tag wird aus dem Hash
// der beiden Quelltexte gebildet.
static GLuint wots2_link_cached(const char* vsSrc, const char* fsSrc) {
    return wots2_link_cached(vsSrc, fsSrc);
}

static GLuint link(const char* vsSrc, const char* fsSrc) {
    GLuint vs = compile(GL_VERTEX_SHADER, vsSrc), fs = compile(GL_FRAGMENT_SHADER, fsSrc);
    GLuint p = glCreateProgram();
    glAttachShader(p, vs);
    glAttachShader(p, fs);
    glLinkProgram(p);
    glDeleteShader(vs);
    glDeleteShader(fs);
    GLint ok = 0;
    glGetProgramiv(p, GL_LINK_STATUS, &ok);
    if (!ok) {
        char log[512];
        glGetProgramInfoLog(p, sizeof log, nullptr, log);
        fprintf(stderr, "[GS] link error: %s\\n", log);
    }
    return p;
}"""

# Der Original-Fall: nur link() ohne wots2_link_cached (falls Quelle noch
# nicht kaputt gepatcht ist)
LINK_ORIGINAL = """static GLuint link(const char* vsSrc, const char* fsSrc) {
    GLuint vs = compile(GL_VERTEX_SHADER, vsSrc), fs = compile(GL_FRAGMENT_SHADER, fsSrc);
    GLuint p = glCreateProgram();
    glAttachShader(p, vs);
    glAttachShader(p, fs);
    glLinkProgram(p);
    glDeleteShader(vs);
    glDeleteShader(fs);
    GLint ok = 0;
    glGetProgramiv(p, GL_LINK_STATUS, &ok);
    if (!ok) {
        char log[512];
        glGetProgramInfoLog(p, sizeof log, nullptr, log);
        fprintf(stderr, "[GS] link error: %s\\n", log);
    }
    return p;
}"""

LINK_FIXED = """// (wots2_shader_cache_fix_v1) Cached-Variante von link(): versucht
// erst den Binary-Cache, sonst kompiliert+linkt sie frisch und legt das
// Ergebnis ab. Der Tag ist der Hash der beiden Quelltexte.
//
// Vorher kaputt: wots2_link_cached() rief sich selbst auf (Endlos-
// rekursion), und link() rief wots2_link_cached() NIE auf — der Cache
// war toter Code. Jetzt ruft link() die Cache-Funktion.
static GLuint wots2_link_cached(const char* vsSrc, const char* fsSrc) {
    char tag[24];
    wots2_shader_cache_tag(vsSrc, fsSrc, tag, sizeof tag);
    GLuint p = glCreateProgram();
    if (wots2_shader_cache_load(p, tag))
        return p;
    GLuint vs = compile(GL_VERTEX_SHADER, vsSrc);
    GLuint fs = compile(GL_FRAGMENT_SHADER, fsSrc);
    glAttachShader(p, vs);
    glAttachShader(p, fs);
    glProgramParameteri(p, GL_PROGRAM_BINARY_RETRIEVABLE_HINT, GL_TRUE);
    glLinkProgram(p);
    glDeleteShader(vs);
    glDeleteShader(fs);
    GLint ok = 0;
    glGetProgramiv(p, GL_LINK_STATUS, &ok);
    if (!ok) {
        char log[512];
        glGetProgramInfoLog(p, sizeof log, nullptr, log);
        fprintf(stderr, "[GS] link error: %s\\n", log);
    } else {
        wots2_shader_cache_store(p, tag);
    }
    return p;
}

static GLuint link(const char* vsSrc, const char* fsSrc) {
    return wots2_link_cached(vsSrc, fsSrc);
}"""

# init() s_program — kaputter Zustand (shader_cache_init steht NACH glUseProgram)
INIT_BROKEN = """    GLuint vs = compile(GL_VERTEX_SHADER, kVertexShader);
    GLuint fs = compile(GL_FRAGMENT_SHADER, kFragmentShader);
    s_program = glCreateProgram();
    glAttachShader(s_program, vs);
    glAttachShader(s_program, fs);
    glLinkProgram(s_program);
    glDeleteShader(vs);
    glDeleteShader(fs);
    glUseProgram(s_program);
    wots2_shader_cache_init(getenv("WOTS2_DATA_ROOT"));"""

# init() s_program — Original-Zustand (kein Cache-Init)
INIT_ORIGINAL = """    GLuint vs = compile(GL_VERTEX_SHADER, kVertexShader);
    GLuint fs = compile(GL_FRAGMENT_SHADER, kFragmentShader);
    s_program = glCreateProgram();
    glAttachShader(s_program, vs);
    glAttachShader(s_program, fs);
    glLinkProgram(s_program);
    glDeleteShader(vs);
    glDeleteShader(fs);
    glUseProgram(s_program);"""

INIT_FIXED = """    // (wots2_shader_cache_fix_v1) Cache-Init VOR dem ersten link(),
    // damit der Binary-Cache auch fuer das Hauptprogramm greift.
    wots2_shader_cache_init(getenv("WOTS2_DATA_ROOT"));
    s_program = link(kVertexShader, kFragmentShader);
    glUseProgram(s_program);"""

INIT3D_ORIGINAL = """    GLuint vs3 = compile(GL_VERTEX_SHADER, kVertexShader3d);
    GLuint fs3 = compile(GL_FRAGMENT_SHADER, kFragmentShader3d);
    s_program3d = glCreateProgram();
    glAttachShader(s_program3d, vs3);
    glAttachShader(s_program3d, fs3);
    glLinkProgram(s_program3d);
    glDeleteShader(vs3);
    glDeleteShader(fs3);
    glUseProgram(s_program3d);"""

INIT3D_FIXED = """    // (wots2_shader_cache_fix_v1) Auch das 3D-Programm ueber den Cache.
    s_program3d = link(kVertexShader3d, kFragmentShader3d);
    glUseProgram(s_program3d);"""


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()

    # 1. Korrekt?
    if "s_program = link(kVertexShader, kFragmentShader)" in t:
        print("  bereits korrekt (v3-Marker) — skip")
        return

    # 2. Helper einbauen, falls noch nicht da
    if "wots2_shader_cache_init" not in t:
        last_inc = list(re.finditer(r'^#include [<"][^\n]+[>\"]\n', t, re.M))
        if not last_inc:
            print("  FEHLER: kein #include gefunden.", file=sys.stderr)
            sys.exit(1)
        t = t[:last_inc[-1].end()] + HELPER + t[last_inc[-1].end():]
        print("  Helper eingefuegt")
    else:
        print("  Helper bereits vorhanden — ueberspringe")

    # 3. wots2_link_cached + link ersetzen
    if LINK_BROKEN in t:
        t = t.replace(LINK_BROKEN, LINK_FIXED, 1)
        print("  wots2_link_cached + link: kaputt -> korrekt")
    elif LINK_ORIGINAL in t:
        t = t.replace(LINK_ORIGINAL, LINK_FIXED, 1)
        print("  link(): Original -> cached")
    else:
        print("  WARNUNG: weder kaputte noch Original-link() gefunden")

    # 4. init() s_program
    if INIT_BROKEN in t:
        t = t.replace(INIT_BROKEN, INIT_FIXED, 1)
        print("  init() s_program: kaputt -> link()")
    elif INIT_ORIGINAL in t:
        t = t.replace(INIT_ORIGINAL, INIT_FIXED, 1)
        print("  init() s_program: Original -> link()")
    else:
        print("  WARNUNG: weder kaputte noch Original-s_program-Init gefunden")

    # 5. init() s_program3d
    if INIT3D_ORIGINAL in t:
        t = t.replace(INIT3D_ORIGINAL, INIT3D_FIXED, 1)
        print("  init() s_program3d: inline -> link()")
    else:
        print("  WARNUNG: s_program3d-Init nicht gefunden")

    # 6. Tick in end_frame() (falls noch nicht da)
    if "wots2_shader_cache_tick(s_frame);" not in t:
        m = re.search(r'(\bs_frame\+\+;\s*\n)', t)
        if m:
            t = t[:m.end()] + "    wots2_shader_cache_tick(s_frame);\n" + t[m.end():]
            print("  end_frame(): shader_cache_tick eingefuegt")
        else:
            print("  WARNUNG: s_frame++-Anker nicht gefunden")

    p.write_text(t)
    print("  gs.cpp gepatcht")


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
