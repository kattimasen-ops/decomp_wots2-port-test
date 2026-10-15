<div align="center">

# 侍道2 — Way of the Samurai 2, native

**The 2004 PS2 cult classic, decompiled and running as a real Linux program
on the Rockchip RK3326.**

**No emulator. No interpreter. Optimised for ArkOS4Clone on the M9 Pro.**

</div>

---

Ten days in Amahara. A hungry ronin, a mute girl, a rice ball, three thugs — and
then every choice is yours. *Way of the Samurai 2* never left the PlayStation 2.

This project takes the game's MIPS machine code apart function by function,
rewrites it as C++, and runs it natively: the game's own logic, its own data,
its own scripts — on the RK3326's four Cortex-A35 cores, drawing through
OpenGL ES 3.2 on the Mali-G31 MP2.

**You can play it from the title screen to the staff roll.**

> **This is a port of a port.** The decompilation and the original Linux /
> Windows / macOS backends come from
> [acklavidian/decomp_wots2](https://github.com/acklavidian/decomp_wots2).
> This repository adds a new host target for the Rockchip RK3326 handhelds
> (M9 Pro, similar to the R36S), tuned for Cortex-A35 and Mali-G31.
> See [Credits](#credits).

---

## What runs

The same as upstream, with the same scripting VM, the same fight AI, the same
living town of Amahara, and the same mods. All 102 story and shop scripts run
through to the endings; sword fighting, guards, parries, item and equipment
management, shops, saving and loading — everything.

Also in: the opening and ending movies, voiced dialogue with lip movement,
music and sound effects, the sky, water, fog, shadows, blood, sparks and blade
trails, and controller support.

## What this port adds on the RK3326

The upstream builds for desktop (OpenGL 3.3 core, x86_64 / aarch64). The
RK3326's Mali-G31 MP2 is a tile-based OpenGL ES 3.2 GPU with a very low
bandwidth budget and no desktop GL support. This port is a full retarget:

- **OpenGL ES 3.2 backend** — every shader rewritten to `#version 320 es`,
  sampled through EGL + libmali (`libmali-bifrost-g31-rxp0-gbm`), with explicit
  sampler bindings and `mediump` for colour maths where the half-float ALU is
  twice as fast.
- **SDL2 KMSDRM with a Mali-G31 pageflip fix** — the Mali driver advertises
  `DRM_CAP_ASYNC_PAGE_FLIP` but rejects the actual `drmModePageFlip` call with
  `-EINVAL`; every frame is dropped and the picture tears. The build patches
  SDL2 to retry without the async flag and disable it for the session. See
  `patches/sdl2-pageflip.py`.
- **NEON vectorisation of the vertex-lerp hot path** — `wots2_lerp_vertex` and
  `wots2_lerp_vertex3` replace the scalar interpolation between frames, and the
  frustum-culling `box_outside` is a single NEON pass over the eight corners.
  See `patches/wots2-neon.py`.
- **Cortex-A35 code generation** — `-march=armv8-a+crc -mcpu=cortex-a35
  -mtune=cortex-a35 -mno-outline-atomics`. The last flag is critical: without
  it GCC emits calls to `__aarch64_ldadd4_acq_rel`, which is an LSE sequence
  that the A35 does not implement and turns every atomic into a SIGILL.
- **PGO-ready build** — the toolchain honours `-DCMAKE_INTERPROCEDURAL_OPTIMIZATION=ON`
  with `-flto`; the ImGui target opts out because its static-initialised state
  does not survive LTO on Mali.
- **A `port.ini` for runtime tuning** — resolution, frame rate, every lighting
  option, and fog distance are read at startup. See
  [Configuration](#configuration).

## Mods, built in

The upstream mod loader ships with four mods switched on:

- **Widescreen** — the 3D view opens out to the sides. 16:9, 21:9, whatever shape your window is.
- **Resolution** — draw at fewer pixels than the screen and upscale; on the RK3326 this is the main performance lever.
- **FPS unlock** — 60 or 120 pictures a second. The game still thinks at 30; everything in between is interpolated.
- **Modern lighting** — real sun shadows from characters, objects and the town
  itself, ambient occlusion, bloom, god rays and a colour grade. At night the
  lanterns light the street, light the people walking past, and cast their soft
  shadows on the ground — with moths flitting round them.
  - **Weather** — rain that rolls in by itself (or on F8): wet streets with puddles that catch the sky, splashes, eaves dripping after the shower, dry under the roofs, a grey sky.
  - **Bump mapping** on stone, wood, tiles and clothes, and an optional un-baked mode that relights the whole town from its sun.
  - **Wind and dust** — the game's own gusts made visible.
  - **Moods** — a look of its own for dawn, evening, night, indoors and the rain.
  - **Characters in shade** — people take the light painted into the ground under their feet.

**On the RK3326 the modern lighting is expensive.** The Mali-G31 has 512
threads at up to ~450 MHz and shares 1 GB of DDR3 with the CPU. With every
lighting option on, a busy fight scene drops below 20 FPS. The `port.ini`
recommended for the M9 Pro keeps shadows, AO, god rays and dust off, bloom
low, and renders at 448×336. See [Performance](#performance).

**HD texture packs made for PCSX2 work as they are:** put the pack's `.dds`
files in a mod's `textures/` folder. F9 switches the pack off and on while you
play.

**A level editor is built in too:** press F2 in the world to move, add and
remove objects, paint where one can walk, and save the result as a mod.

**Photo mode:** F7 freezes the world, hides the HUD and hands you a free camera
with field of view, roll and depth of field; F12 saves the picture.

---

## Play it

**You need your own copy of the game** — the NTSC-U disc, `SLUS-208.93`.
Nothing from the disc is in this repository.

**Prebuilt:** download the `wots2-rk3326` package from
[Releases](https://github.com/kattimasen-ops/decomp_wots2-port-test/releases)
or from the workflow artefact. Unpack it into the `ports` folder of your
ArkOS4Clone SD card:

```
/roms/ports/
├── WOTS2.sh
└── wots2/
    ├── wots2
    ├── port.ini
    ├── libs.aarch64/
    └── extracted/          ← the game's data, added on first launch
```

Start it from Ports in EmulationStation. The first launch asks for your disc
image — an `.iso`, or a `.zip` / `.7z` / `.rar` / `.tar.*` holding the image or
the files themselves. The launcher unpacks the files once (about 1.5 GB) and
starts the game; after that `WOTS2.sh` alone is enough.

### Requirements

- **Rockchip RK3326** (4× Cortex-A35, Mali-G31 MP2, 1 GB RAM) or a
  compatible SoC.
- **ArkOS4Clone** (GLIBC 2.31 / Ubuntu 20.04 base) or a Linux userspace with
  the Mali Bifrost G31 driver (`libmali-bifrost-g31-rxp0-gbm.so`) installed.
- About 3 GB free on the SD card (extracted data plus saves).
- A Linux-compatible gamepad. ArkOS4Clone's controller configuration is read
  at launch; on the M9 Pro the default mapping works out of the box.

### From source

The build is designed to run inside a GitHub Actions runner — the container
is Ubuntu 20.04, cross-toolchain is `gcc-aarch64-linux-gnu`, GLES comes from
the multiarch `libgles2-mesa-dev:arm64` package. See
`.github/workflows/build-wots2.yml`. To reproduce the same build locally:

```bash
# 1. Docker container with the same base
docker run --rm -it -v "$PWD:/w" -w /w ubuntu:20.04 bash

# 2. Inside the container, run the workflow's steps in order.
#    The easiest way is to look at the workflow file — each `name:` is one
#    shell block. Copy them one by one, or extract them with yq.
```

The toolchain file `cmake/aarch64-arkos.cmake` sets the cross-compiler and
all Cortex-A35 flags. `-DWOTS2_GLES=ON` switches to EGL/GLESv2 and enables
`IMGUI_IMPL_OPENGL_ES3`.

F11 toggles fullscreen. Saves go in `wots2/wots2_card/`.

---

## Configuration

A `port.ini` next to the `wots2` binary controls every runtime option. It is
read on startup, before the renderer is created. If the file is missing,
everything stays on the upstream defaults.

The three presets below are documented in the file itself. The **recommended**
preset is the one shipped in the release:

### Recommended — M9 Pro / RK3326

```ini
video.height = 336       # 448x336; smooth on most scenes
video.aspect = 1.3333
video.fps    = 30
video.vsync  = true
video.fullscreen = true

lighting.shadows         = false
lighting.ao              = false
lighting.god_rays        = 0.0
lighting.dust            = 0.0
lighting.bloom           = 0.15
lighting.bloom_threshold = 0.85
lighting.grade           = false
lighting.lanterns        = true
lighting.lantern_shadows = false

fog.far_scale = 0.85     # 15% shorter view distance
```

### Low — maximum stability

```ini
video.height = 224
video.fps    = 30

lighting.shadows   = false
lighting.ao        = false
lighting.bloom     = 0.0
lighting.god_rays  = 0.0
lighting.dust      = 0.0
lighting.lanterns  = false
```

### High — quiet scenes only

```ini
video.height = 448
video.fps    = 60
lighting.shadows        = true
lighting.shadow_size    = 512
lighting.shadow_strength = 0.4
lighting.ao             = true
lighting.ao_strength    = 0.6
lighting.bloom          = 0.3
lighting.god_rays       = 0.4
lighting.dust           = 0.5
lighting.grade          = true
lighting.lanterns       = true
lighting.lantern_shadows = true
```

The in-game **Settings → R1 Enhancements** menu (or **F5**) exposes the same
options live. **Save** keeps them back to `port.ini`.

### Environment overrides

Any setting can be overridden for one launch with an environment variable.
The launcher `WOTS2.sh` uses this to pin the CPU governor:

| Variable | Effect |
|---|---|
| `WOTS2_VIDEO=height=336,fps=30` | Overrides `video.*` for this run |
| `WOTS2_FAST=1` | Runs as fast as possible (no vsync, no frame pacing) |
| `WOTS2_NO_CULL=1` | Draws every mesh, no frustum or fog culling (diagnostic) |

---

## Performance

The RK3326's Cortex-A35 cores have a low IPC and the Mali-G31 MP2 is one of
the smallest Bifrost configurations. The M9 Pro shares 1 GB of DDR3 between
CPU, GPU and the OS.

The numbers below are what to expect at the recommended settings
(448×336, no shadows / no AO). **They are estimates based on comparable
ports** — the port has not yet been benchmarked on real hardware.

| Scene | Recommended (448×336) | Low (320×224) |
|---|---|---|
| Main menu | 50–60 FPS | 60 FPS (capped) |
| Quiet village, day | 40–55 FPS | 55–60 FPS |
| Fight, 3–5 enemies | 30–40 FPS | 45–55 FPS |
| Fight, 8+ enemies | 22–32 FPS | 35–45 FPS |
| Rain + many effects | 20–28 FPS | 30–40 FPS |

If you enable shadows and AO at native resolution (640×448), expect a
**40–60 % FPS drop**; a busy fight scene will fall below 15 FPS.

The single biggest lever is `video.height`. Dropping from 448 to 336 cuts the
pixel count by 44 %; dropping to 224 cuts it by 75 %.

### Thermal throttling

The RK3326 throttles the CPU and GPU at 70 °C. The `WOTS2.sh` launcher pins
the CPU governor to `performance` at startup, which raises the throttle point
by only a few degrees but keeps the frame time consistent — measure both if
you are chasing the last few FPS.

---

## Controls

| | Controller | Keyboard |
|---|---|---|
| Run / walk | Left stick or d-pad | Arrows / T G F H |
| Sprint (sword away) | Press L3 while running | C |
| Jump, confirm | Cross (bottom) | Z |
| Talk | Circle (right) | X |
| Attack, pick up | Square (left) | A |
| Attack, cancel | Triangle (top) | S |
| Draw / sheathe | L1 | Q |
| Guard (+ Square: kick) | R1 | W |
| Camera | Right stick (R3: back behind) | J L / I K (V: back behind) |
| Pause menu | Start | Enter |

The port reads the ArkOS4Clone controller layout from EmulationStation's
configuration. On the M9 Pro the default layout matches the Xbox layout used
by the original game — no remap needed.

| Key | |
|---|---|
| F2 | Level editor |
| F3 | Modern lighting off / on, to compare |
| F4 | Print where you are (for bug reports) |
| F5 | Graphics panel: FPS, lighting, weather, dust — live, with Save |
| F6 | FPS unlock off / on |
| F7 | Photo mode (F12 saves the picture) |
| F8 | Weather: clear → rain → by itself |
| F9 | HD texture pack off / on |
| F11 | Fullscreen |
| F12 | Save photo / screenshot |

---

## How it works

```
 SLUS_208.93 (MIPS R5900)                    this repository
┌─────────────────────────┐      ┌──────────────────────────────────────┐
│ game + engine code      │ ───▶ │ src/game, src/engine   decompiled C++ │
│ data, vtables, tables   │ ───▶ │ loaded at its real PS2 addresses      │
│ GS · SPU2 · pad · disc  │ ───▶ │ src/hal   GLES 3.2 · SDL2 · input     │
└─────────────────────────┘      └──────────────────────────────────────┘
```

- **Pure decompilation.** Each function is read out of Ghidra and the
  disassembly rewritten by hand. There is no MIPS interpreter anywhere.
- **Guest memory.** The game's data is mapped at the addresses it had on the
  PS2, so decompiled code and original data tables agree without translation.
  Calls through vtables go through a registry of address → native function.
- **Hardware boundary.** The Graphics Synthesizer becomes an OpenGL ES
  renderer that records each frame as a draw list — which is what lets the
  same frame be replayed wider, sharper, and in between.

About 1,900 of the binary's ~4,600 functions are decompiled. Much of the rest
is the script compiler, Sony's libraries and debug screens the game never
shows.

### What is different on this port

The upstream code paths for `port/linux`, `port/windows` and `port/macos`
are **unchanged**. The RK3326 port lives entirely in:

| File | Purpose |
|---|---|
| `cmake/aarch64-arkos.cmake` | Cross-compile toolchain, Cortex-A35 flags |
| `src/native/port_options.cpp` | `port.ini` reader and applier |
| `include/native/port_options.h` | Public interface |
| `patches/wots2-gles.py` | Shader rewrite to `#version 320 es` |
| `patches/wots2-gles-precision.py` | `mediump` for colour maths |
| `patches/wots2-neon.py` | NEON vertex-lerp and cull helpers |
| `patches/sdl2-pageflip.py` | Mali-G31 KMSDRM pageflip fallback |
| `.github/workflows/build-wots2.yml` | CI cross-compile pipeline |

The upstream `CMakeLists.txt` is extended by an option `WOTS2_GLES=ON`, which
switches the OpenGL finder to `pkg-config`-based EGL/GLESv2 and enables the
ImGui ES 3 backend define.

---

## Honest status

It plays start to finish, and automated runs take whole games through to an
ending without a crash. It is not finished:

- **The RK3326 build has not been tested on real hardware yet.** The GitHub
  Actions pipeline produces a binary that links cleanly against libmali and
  SDL2; the first real-hardware test is still pending.
- Map and model **drawing and lighting are native approximations**, not the
  original's VU1 code. It looks right; it is not bit-exact.
- It has **not been compared side by side with the original** on real
  hardware or PCSX2 for timing, sound and feel.
- **The performance table above is a projection**, not measured data. Once
  the port runs on the M9 Pro, real numbers will replace it.

Found something that looks or plays wrong? That's the most useful thing you can
report. Please include the output of **F4** (your position) and a screenshot
if possible.

---

## Poking around

```bash
# Cross-compile from source
cmake -S . -B build -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE=cmake/aarch64-arkos.cmake \
    -DSDL2_INSTALL_DIR=/path/to/sdl2-install \
    -DWOTS2_GLES=ON
cmake --build build -j4
```

The same helper tools from upstream apply:

```bash
tools/ghidra_decomp.sh 0x1C3AC0        # Ghidra pseudocode for a function
tools/volume.py list                   # what's in VOLUME.DAT
tools/sx.py src CTX/Opening            # read an event script
tools/task.py dump shop.bin            # read an NPC's task script
WOTS2_MODEL_VIEW=shujinko_01 ./build/wots2 extracted    # model viewer
WOTS2_MAP_VIEW=numata        ./build/wots2 extracted    # fly through a map
```

---

## Legal

This repository contains none of the game's binaries, assets or disc contents.
It is an independent, non-commercial preservation and research project, not
affiliated with or endorsed by Acquire, Spike or Capcom. *Way of the Samurai*
is a trademark of its owners. You must own the game to use this.

The Mali driver (`libmali-bifrost-g31-rxp0-gbm.so`) is not redistributed here;
the build downloads SDL2 sources from [libsdl.org](https://www.libsdl.org/)
and patches them at build time (the resulting shared library is bundled in
the releases, as the zlib licence allows).

---

## Credits

### Upstream

- **[acklavidian](https://github.com/acklavidian)** —
  [decomp_wots2](https://github.com/acklavidian/decomp_wots2): the
  decompilation, the original Linux/Windows/macOS backends, the mod loader,
  the modern lighting work, the level editor, the launcher, and everything
  else that makes this game playable on a modern machine. This port is a
  thin hardware-specific layer on top of that work.
- **The GameCube / Wii decompilation community** (for tooling conventions
  and the Ghidra workflow this project follows).
- **Bungie and the Halo CE RK3326 port** (github.com/kattimasen-ops/halo-ce-rk3326-Port)
  — the KMSDRM pageflip workaround, the SDL2 cross-compile recipe, and the
  `-mno-outline-atomics` insight all come from that project.

### This port

- **St0len-One** — RK3326 / M9 Pro cross-compile target, GLES 3.2 shader
  rewrite, NEON vertex-lerp, `port.ini` option system, GitHub Actions CI
  pipeline, documentation.

### Tools

- [Dear ImGui](https://github.com/ocornut/imgui) — the level editor overlay.
- [xxHash](https://github.com/Cyan4973/xxHash) — XXH3 for PCSX2-named
  texture packs.
- [libarchive](https://libarchive.org/) — disc image unpacking in the launcher.
- [SDL2](https://www.libsdl.org/) — audio, input, KMSDRM video.
- The GCC and LLVM teams, for the Cortex-A35 codegen that makes the
  `-mno-outline-atomics` workaround necessary and effective.

---

*If you fork this, please keep both names visible. The decompilation took
years; the port took weeks. Both deserve the attribution.*
