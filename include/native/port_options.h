// ══════════════════════════════════════════════════════════════════════
//  Way of the Samurai 2 — M9 Pro (RK3326) Port
//  port_options.h — port.ini-Loader
//
//  Decompilation:  acklavidian (github.com/acklavidian/decomp_wots2)
//  RK3326-Port:    St0len-One
//  Target:         Rockchip RK3326 / Cortex-A35 / Mali-G31 MP2
// ══════════════════════════════════════════════════════════════════════
#pragma once

namespace port_options {

struct Options {
    // ── Video ────────────────────────────────────────────────────────
    float aspect = 0.0f;         // 0 = 4:3, >0 = festes Verhältnis, <0 = Fenster
    int   height = 448;          // Bildzeilen; 224 (320×224), 336 (448×336), 448 (640×448)
    int   fps    = 0;            // 0 = 30 (Spiel), >0 = fest, <0 = Display-Rate
    bool  vsync  = true;
    bool  fullscreen = false;
    int   window_w = 0;
    int   window_h = 0;

    // ── Lighting ─────────────────────────────────────────────────────
    bool  shadows          = false;
    bool  map_shadows      = false;
    float model_shadow     = 0.6f;
    int   shadow_size      = 1024;    // 256…2048; auf RK3326 max. 512 sinnvoll
    float shadow_reach     = 16.0f;
    float shadow_strength  = 0.55f;
    bool  ao               = false;
    float ao_strength      = 1.0f;
    float ao_radius        = 0.35f;
    float bloom            = 0.0f;
    float bloom_threshold  = 0.78f;
    float god_rays         = 0.0f;
    float dust             = 0.0f;
    bool  grade            = false;
    bool  lanterns         = false;
    bool  lantern_shadows  = false;
    int   weather          = 1;       // 0 = Zufall, 1 = immer klar, 2 = immer Regen
    float bump             = 0.0f;
    float dof              = 0.0f;

    // ── Fog / Sichtweite ─────────────────────────────────────────────
    float fog_far_scale = 1.0f;       // 1.0 = Xbox-Sichtweite, <1.0 = kürzer
};

Options load(const char* path);
void    apply(const Options& o);

}  // namespace port_options
