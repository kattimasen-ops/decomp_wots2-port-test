// ══════════════════════════════════════════════════════════════════════
//  Way of the Samurai 2 — M9 Pro (RK3326) Port
//  port_options.cpp — liest port.ini und wendet die Werte an.
//
//  Decompilation:  acklavidian (github.com/acklavidian/decomp_wots2)
//  RK3326-Port:    St0len-One
//  Target:         Rockchip RK3326 / Cortex-A35 / Mali-G31 MP2
// ══════════════════════════════════════════════════════════════════════
#include "native/port_options.h"

#include "hal/gs.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

namespace {

std::string trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t\r\n");
    size_t b = s.find_last_not_of(" \t\r\n");
    return a == std::string::npos ? "" : s.substr(a, b - a + 1);
}

bool parse_bool(const std::string& v) {
    return v == "1" || v == "true" || v == "on" || v == "yes";
}

float parse_float(const std::string& v, float fallback) {
    char* end = nullptr;
    float r = std::strtof(v.c_str(), &end);
    return (end && *end == 0) ? r : fallback;
}

int parse_int(const std::string& v, int fallback) {
    char* end = nullptr;
    long r = std::strtol(v.c_str(), &end, 10);
    return (end && *end == 0) ? (int)r : fallback;
}

}  // namespace

namespace port_options {

Options load(const char* path) {
    Options o;
    FILE* f = std::fopen(path, "rb");
    if (!f) {
        std::fprintf(stderr,
            "[port_options] %s nicht gefunden — Defaults aktiv\n", path);
        return o;
    }

    char line[512];
    int  lineno = 0;
    int  known  = 0;
    std::string section;
    while (std::fgets(line, sizeof(line), f)) {
        ++lineno;
        std::string s = trim(line);
        if (s.empty() || s[0] == '#' || s[0] == ';') continue;

        // Sektions-Header: [video], [lighting], [fog]
        if (s.size() >= 2 && s.front() == '[' && s.back() == ']') {
            section = trim(s.substr(1, s.size() - 2));
            continue;
        }

        size_t eq = s.find('=');
        if (eq == std::string::npos) {
            std::fprintf(stderr,
                "[port_options] Zeile %d: kein '=' — übersprungen\n", lineno);
            continue;
        }

        std::string key = trim(s.substr(0, eq));
        std::string val = trim(s.substr(eq + 1));

        // Wenn wir in einer Sektion sind und der Schlüssel keinen Punkt
        // enthaelt, mit dem Sektionsnamen praefixen.
        if (!section.empty() && key.find('.') == std::string::npos)
            key = section + "." + key;

        // ── Video ────────────────────────────────────────────────────
        if      (key == "video.aspect")        { o.aspect        = parse_float(val, o.aspect); ++known; }
        else if (key == "video.height")        { o.height        = parse_int(val, o.height); ++known; }
        else if (key == "video.fps")           { o.fps           = parse_int(val, o.fps); ++known; }
        else if (key == "video.vsync")         { o.vsync         = parse_bool(val); ++known; }
        else if (key == "video.fullscreen")    { o.fullscreen    = parse_bool(val); ++known; }
        else if (key == "video.window_width")  { o.window_w      = parse_int(val, o.window_w); ++known; }
        else if (key == "video.window_height") { o.window_h      = parse_int(val, o.window_h); ++known; }

        // ── Lighting ─────────────────────────────────────────────────
        else if (key == "lighting.shadows")          { o.shadows          = parse_bool(val); ++known; }
        else if (key == "lighting.map_shadows")      { o.map_shadows      = parse_bool(val); ++known; }
        else if (key == "lighting.model_shadow")     { o.model_shadow     = parse_float(val, o.model_shadow); ++known; }
        else if (key == "lighting.shadow_size")      { o.shadow_size      = parse_int(val, o.shadow_size); ++known; }
        else if (key == "lighting.shadow_reach")     { o.shadow_reach     = parse_float(val, o.shadow_reach); ++known; }
        else if (key == "lighting.shadow_strength")  { o.shadow_strength  = parse_float(val, o.shadow_strength); ++known; }
        else if (key == "lighting.ao")               { o.ao               = parse_bool(val); ++known; }
        else if (key == "lighting.ao_strength")      { o.ao_strength      = parse_float(val, o.ao_strength); ++known; }
        else if (key == "lighting.ao_radius")        { o.ao_radius        = parse_float(val, o.ao_radius); ++known; }
        else if (key == "lighting.bloom")            { o.bloom            = parse_float(val, o.bloom); ++known; }
        else if (key == "lighting.bloom_threshold")  { o.bloom_threshold  = parse_float(val, o.bloom_threshold); ++known; }
        else if (key == "lighting.god_rays")         { o.god_rays         = parse_float(val, o.god_rays); ++known; }
        else if (key == "lighting.dust")             { o.dust             = parse_float(val, o.dust); ++known; }
        else if (key == "lighting.grade")            { o.grade            = parse_bool(val); ++known; }
        else if (key == "lighting.lanterns")         { o.lanterns         = parse_bool(val); ++known; }
        else if (key == "lighting.lantern_shadows")  { o.lantern_shadows  = parse_bool(val); ++known; }
        else if (key == "lighting.weather")          { o.weather          = parse_int(val, o.weather); ++known; }
        else if (key == "lighting.bump")             { o.bump             = parse_float(val, o.bump); ++known; }
        else if (key == "lighting.dof")              { o.dof              = parse_float(val, o.dof); ++known; }

        // ── Fog / Sichtweite ─────────────────────────────────────────
        else if (key == "fog.far_scale")             { o.fog_far_scale    = parse_float(val, o.fog_far_scale); ++known; }

        else
            std::fprintf(stderr,
                "[port_options] unbekannter Schlüssel: %s\n", key.c_str());
    }

    std::fclose(f);
    std::fprintf(stderr,
        "[port_options] %s geladen: %d Schlüssel, %d Zeilen\n",
        path, known, lineno);
    return o;
}

void apply(const Options& o) {
    // Video
    hal::gs::Video v = hal::gs::video();
    v.aspect       = o.aspect;
    v.height       = o.height;
    v.fps          = o.fps;
    v.vsync        = o.vsync;
    v.fullscreen   = o.fullscreen;
    v.windowWidth  = o.window_w;
    v.windowHeight = o.window_h;
    hal::gs::set_video(v);

    // Lighting
    hal::gs::Lighting l = hal::gs::lighting();
    l.shadows            = o.shadows;
    l.mapShadows         = o.map_shadows;
    l.modelShadow        = o.model_shadow;
    l.shadowSize         = o.shadow_size;
    l.shadowReach        = o.shadow_reach;
    l.shadowStrength     = o.shadow_strength;
    l.ao                 = o.ao;
    l.aoStrength         = o.ao_strength;
    l.aoRadius           = o.ao_radius;
    l.bloom              = o.bloom;
    l.bloomThreshold     = o.bloom_threshold;
    l.godRays            = o.god_rays;
    l.dust               = o.dust;
    l.grade              = o.grade;
    l.lanterns           = o.lanterns;
    l.lanternShadows     = o.lantern_shadows;
    l.weather            = o.weather;
    l.bump               = o.bump;
    l.dof                = o.dof;
    hal::gs::set_lighting(l);

    std::fprintf(stderr,
        "[port_options] angewendet: render=%dx%d, fps=%d, "
        "shadows=%d, ao=%d, bloom=%.2f, god_rays=%.2f\n",
        o.height * 4 / 3, o.height, o.fps,
        o.shadows ? 1 : 0, o.ao ? 1 : 0, o.bloom, o.god_rays);
}

}  // namespace port_options
