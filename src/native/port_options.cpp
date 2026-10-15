// Liest port.ini aus dem Spielverzeichnis und wendet es auf Video +
// Lighting an, bevor der Renderer startet. Die Datei ist optional;
// fehlt sie, bleibt alles auf Upstream-Default.
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
        std::fprintf(stderr, "[port_options] %s nicht gefunden; Defaults aktiv\n", path);
        return o;
    }

    char line[512];
    int  lineno = 0;
    while (std::fgets(line, sizeof(line), f)) {
        ++lineno;
        std::string s = trim(line);
        if (s.empty() || s[0] == '#' || s[0] == ';') continue;

        size_t eq = s.find('=');
        if (eq == std::string::npos) {
            std::fprintf(stderr, "[port_options] Zeile %d: kein '=' — übersprungen\n", lineno);
            continue;
        }

        std::string key = trim(s.substr(0, eq));
        std::string val = trim(s.substr(eq + 1));

        // ── Video ──────────────────────────────────────────────────
        if      (key == "video.aspect")           o.aspect = parse_float(val, o.aspect);
        else if (key == "video.height")           o.height = parse_int(val, o.height);
        else if (key == "video.fps")              o.fps = parse_int(val, o.fps);
        else if (key == "video.vsync")            o.vsync = parse_bool(val);
        else if (key == "video.fullscreen")       o.fullscreen = parse_bool(val);
        else if (key == "video.window_width")     o.window_w = parse_int(val, o.window_w);
        else if (key == "video.window_height")    o.window_h = parse_int(val, o.window_h);

        // ── Lighting ────────────────────────────────────────────────
        else if (key == "lighting.shadows")            o.shadows = parse_bool(val);
        else if (key == "lighting.map_shadows")        o.map_shadows = parse_bool(val);
        else if (key == "lighting.model_shadow")       o.model_shadow = parse_float(val, o.model_shadow);
        else if (key == "lighting.shadow_size")        o.shadow_size = parse_int(val, o.shadow_size);
        else if (key == "lighting.shadow_reach")       o.shadow_reach = parse_float(val, o.shadow_reach);
        else if (key == "lighting.shadow_strength")    o.shadow_strength = parse_float(val, o.shadow_strength);
        else if (key == "lighting.ao")                 o.ao = parse_bool(val);
        else if (key == "lighting.ao_strength")        o.ao_strength = parse_float(val, o.ao_strength);
        else if (key == "lighting.ao_radius")          o.ao_radius = parse_float(val, o.ao_radius);
        else if (key == "lighting.bloom")              o.bloom = parse_float(val, o.bloom);
        else if (key == "lighting.bloom_threshold")    o.bloom_threshold = parse_float(val, o.bloom_threshold);
        else if (key == "lighting.god_rays")           o.god_rays = parse_float(val, o.god_rays);
        else if (key == "lighting.dust")               o.dust = parse_float(val, o.dust);
        else if (key == "lighting.grade")              o.grade = parse_bool(val);
        else if (key == "lighting.lanterns")           o.lanterns = parse_bool(val);
        else if (key == "lighting.lantern_shadows")    o.lantern_shadows = parse_bool(val);
        else if (key == "lighting.weather")            o.weather = parse_int(val, o.weather);
        else if (key == "lighting.bump")               o.bump = parse_float(val, o.bump);
        else if (key == "lighting.dof")                o.dof = parse_float(val, o.dof);

        // ── Fog / Sichtweite ────────────────────────────────────────
        else if (key == "fog.far_scale")               o.fog_far_scale = parse_float(val, o.fog_far_scale);

        else
            std::fprintf(stderr, "[port_options] unbekannt: %s\n", key.c_str());
    }

    std::fclose(f);
    std::fprintf(stderr, "[port_options] %s geladen (%d Zeilen)\n", path, lineno);
    return o;
}

void apply(const Options& o) {
    hal::gs::Video v = hal::gs::video();
    v.aspect     = o.aspect;
    v.height     = o.height;
    v.fps        = o.fps;
    v.vsync      = o.vsync;
    v.fullscreen = o.fullscreen;
    v.windowWidth  = o.window_w;
    v.windowHeight = o.window_h;
    hal::gs::set_video(v);

    hal::gs::Lighting l = hal::gs::lighting();
    l.shadows              = o.shadows;
    l.mapShadows           = o.map_shadows;
    l.modelShadow          = o.model_shadow;
    l.shadowSize           = o.shadow_size;
    l.shadowReach          = o.shadow_reach;
    l.shadowStrength       = o.shadow_strength;
    l.ao                   = o.ao;
    l.aoStrength           = o.ao_strength;
    l.aoRadius             = o.ao_radius;
    l.bloom                = o.bloom;
    l.bloomThreshold       = o.bloom_threshold;
    l.godRays              = o.god_rays;
    l.dust                 = o.dust;
    l.grade                = o.grade;
    l.lanterns             = o.lanterns;
    l.lanternShadows       = o.lantern_shadows;
    l.weather              = o.weather;
    l.bump                 = o.bump;
    l.dof                  = o.dof;
    hal::gs::set_lighting(l);

    std::fprintf(stderr,
        "[port_options] angewendet: %dx%d, fps=%d, shadows=%d, ao=%d, bloom=%.2f\n",
        o.height * 4 / 3, o.height, o.fps, o.shadows, o.ao, o.bloom);
}

}  // namespace port_options
