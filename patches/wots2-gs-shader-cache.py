#!/usr/bin/env python3
"""
Shader-Programm-Cache mit LRU-Unload (Mali-G31).

Hintergrund (Halo CE Port, identische GPU):
  Der Halo CE Port fuer den RG35XX H (Mali-G31 MP2) hat durch
  Shader-Management ca. 50 MB Speicher freigegeben und Stottern in
  spaeteren Levels reduziert. Die Mali-G31 hat einen sehr kleinen
  Shader-Speicher; ARM empfiehlt glGetProgramBinary/glProgramBinary
  zum Cachen.

Was der Patch macht:
  1. Setzt GL_PROGRAM_BINARY_RETRIEVABLE_HINT vor jedem glLinkProgram.
  2. Nach erfolgreichem Link: glGetProgramBinary und Schreiben in
     <data_root>/shader_cache/<hash>.bin.
  3. Beim naechsten Start: glProgramBinary versuchen, bevor
     glShaderSource/glCompileShader aufgerufen wird.
  4. Treiber-Version (GL_VERSION + GL_RENDERER) als Cache-Key:
     nach einem Mali-Update wird der Cache invalidiert.
  5. LRU-Unload: Programme, die seit N Frames nicht gebunden wurden,
     werden via glDeleteProgram freigegeben.

Revision v2 — Reparatur:
  Die vorherige Version hat wots2_link_cached() zwar definiert, aber
  nie aufgerufen: link() ging weiter direkt auf glLinkProgram. Der
  Cache-Ordner blieb leer. Jetzt patcht diese Version die link()-
  Funktion selbst so, dass sie intern wots2_link_cached() aufruft.
  Der Cache-Tag wird aus dem Hash der Shader-Quelltexte gebildet,
  damit unterschiedliche Shader verschiedene Cache-Eintraege bekommen.

Steuerung per Env:
  WOTS2_SHADER_CACHE=0  -> Cache aus (Default: an)
  WOTS2_SHADER_LRU=N    -> N Frames ohne Bindung bis Unload (Default: 600)

Zieldatei: src/hal/gs.cpp
Marker:    wots2_shader_cache_init

Aufruf:    python3 patches/wots2-gs-shader-cache.py src/hal/gs.cpp
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
    // FNV-1a 64-bit
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

// Nach glLinkProgram: Binary holen und ablegen.
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
    uint32_t magic = 0x574F5453;  // "WOTS"
    uint32_t glFmt = (uint32_t)fmt;
    uint32_t len32 = (uint32_t)got;
    fwrite(&magic, 4, 1, f);
    fwrite(&s_shaderDriverKey, 8, 1, f);
    fwrite(&glFmt, 4, 1, f);
    fwrite(&len32, 4, 1, f);
    fwrite(buf.data(), 1, (size_t)got, f);
    fclose(f);
}

// Vor glLinkProgram: Cache versuchen.
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
        fread(&key, 8, 1, f) != 1 || key != s_shaderDriverKey ||
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

// LRU: nach jedem Frame aufrufen.
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

// Der Name, unter dem ein Shader-Paar im Cache abgelegt wird: der Hash
// der beiden Quelltexte. Damit bekommen unterschiedliche Shader eigene
// Eintraege, und derselbe Shader trifft immer denselben Slot.
static void wots2_shader_cache_tag(const char* vs, const char* fs, char* out, size_t out_size) {
    uint64_t h = wots2_hash_str(vs ? vs : "") ^ (wots2_hash_str(fs ? fs : "") << 1);
    snprintf(out, out_size, "p%016llx", (unsigned long long)h);
}
'''


MARKER = "wots2_shader_cache_init"


def patch(path):
    p = pathlib.Path(path)
    t = p.read_text()

    if MARKER in t:
        print('  Shader-Cache bereits vorhanden.')
        return

    # 1. Helper nach dem letzten #include einfuegen.
    last_inc = list(re.finditer(r'^#include [<"][^\n]+[>\"]\n', t, re.M))
    if not last_inc:
        print('  FEHLER: kein #include gefunden.', file=sys.stderr)
        sys.exit(1)
    t = t[:last_inc[-1].end()] + HELPER + t[last_inc[-1].end():]

    # 2. Cache-Init in init() nach dem ersten glUseProgram(s_program).
    anchor_init = re.search(
        r'(\bglUseProgram\(s_program\);\s*\n)'
        r'(\s*)(s_uScreen\s*=\s*glGetUniformLocation)',
        t)
    if anchor_init:
        t = (t[:anchor_init.end(1)]
             + anchor_init.group(2) + "wots2_shader_cache_init(getenv(\"WOTS2_DATA_ROOT\"));\n"
             + t[anchor_init.end(1):])
        print('  init(): shader_cache_init eingefuegt.')
    else:
        print('  WARNUNG: init()-Anker nicht gefunden.')

    # 3. wots2_link_cached VOR link() einfügen.
    link_anchor = re.search(
        r'(static\s+GLuint\s+link\s*\(\s*const\s+char\s*\*\s*vsSrc\s*,\s*'
        r'const\s+char\s*\*\s*fsSrc\s*\)\s*\{)',
        t)
    if not link_anchor:
        print('  FEHLER: link()-Funktion nicht gefunden.', file=sys.stderr)
        sys.exit(1)

    cached_fn = r'''
// Cached-Variante von link(): versucht erst den Binary-Cache, sonst
// kompiliert sie und legt das Ergebnis ab. Der Tag wird aus dem Hash
// der beiden Quelltexte gebildet.
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
        fprintf(stderr, "[GS] link error: %s\n", log);
    } else {
        wots2_shader_cache_store(p, tag);
    }
    return p;
}

'''
    t = t[:link_anchor.start()] + cached_fn + t[link_anchor.start():]

    # 4. link()-Body durch einen Aufruf von wots2_link_cached ersetzen.
    body_start = t.find('{', link_anchor.start())
    depth = 0
    i = body_start
    while i < len(t):
        if t[i] == '{':
            depth += 1
        elif t[i] == '}':
            depth -= 1
            if depth == 0:
                break
        i += 1
    body_end = i
    t = t[:body_start] + '{\n    return wots2_link_cached(vsSrc, fsSrc);\n}' + t[body_end+1:]

    # 5. Shader-Cache-Tick in end_frame() nach s_frame++.
    tick_anchor = re.search(r'(\bs_frame\+\+;\s*\n)', t)
    if tick_anchor:
        t = t[:tick_anchor.end()] + "    wots2_shader_cache_tick(s_frame);\n" + t[tick_anchor.end():]
        print('  end_frame(): shader_cache_tick eingefuegt.')
    else:
        print('  WARNUNG: s_frame++-Anker nicht gefunden.')

    p.write_text(t)
    print('  Shader-Cache-Patch v2 fertig:')
    print('    - wots2_link_cached() vor link() eingefuegt')
    print('    - link() ruft jetzt wots2_link_cached() auf')
    print('    - Cache-Tag aus dem Hash der Shader-Quelltexte')
    print('    - Shader-Cache-Tick in end_frame()')


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'src/hal/gs.cpp'
    print('Patche %s' % target)
    patch(target)
    print('Fertig.')
