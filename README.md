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

## Table of contents

- [What runs](#what-runs)
- [What this port adds on the RK3326](#what-this-port-adds-on-the-rk3326)
- [Optimisations in detail](#optimisations-in-detail)
- [Mods, built in](#mods-built-in)
- [Play it](#play-it)
- [Configuration](#configuration)
- [Performance](#performance)
- [Controls](#controls)
- [How it works](#how-it-works)
- [Honest status](#honest-status)
- [Poking around](#poking-around)
- [Legal](#legal)
- [Credits](#credits)

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
bandwidth budget and no desktop GL support. The M9 Pro shares 1 GB of DDR3
between the CPU, the GPU and the OS. This port is a full retarget from the
ground up — every layer between the game's decompiled code and the SoC's
memory bus has been measured and tuned.

**Graphics and CPU**

- **OpenGL ES 3.2 backend** — every shader rewritten to `#version 320 es`,
  sampled through EGL + libmali (`libmali-bifrost-g31-rxp0-gbm`), with
  explicit sampler bindings and `mediump` for colour maths where the
  half-float ALU is twice as fast.
- **NEON throughout the hot paths** — the vertex-lerp
  (`wots2_lerp_vertex`, `wots2_lerp_vertex3`), frustum culling
  (`wots2_box_outside`), the collision matrix multiply (`wots2_apply_neon`),
  the direction normaliser (`wots2_towards_neon`) and the pairwise
  `Relative()` in the collision world are all hand-written NEON, with the
  load/store operations interleaved into the arithmetic so the A35's single
  load port never stalls the FMA pipeline.
- **Cortex-A35 code generation** — `-march=armv8-a+crc -mcpu=cortex-a35
  -mtune=cortex-a35 -mno-outline-atomics -fprefetch-loop-arrays`. The
  `-mno-outline-atomics` flag is critical: without it GCC emits calls to
  `__aarch64_ldadd4_acq_rel`, which is an LSE sequence the A35 does not
  implement and turns every atomic into a SIGILL. The prefetch flag hides
  memory latency on the A35's single load/store port.

**Mali-G31-specific tune-ups**

- **`glInvalidateFramebuffer`** on the depth buffer at the end of the frame,
  and on the post-process colour target after the composite pass. On a
  tile-based GPU every buffer that is not explicitly invalidated is written
  back to DDR3, even if no one will read it — this eliminates those writes
  for the depth buffer and for the post-FBO.
- **`glTexStorage2D`** for all framebuffer textures. `glTexImage2D` lets the
  texture's size and format change at any time, which forces the driver to
  allocate defensively; `glTexStorage2D` declares them immutable, so the
  driver can plan tile-local storage up front.
- **2D draw-call batching** — successive 2D draws that share a texture are
  merged into a single `glDrawArrays`. ARM's guidance for Mali is to keep
  the frame under ~500 draw calls; this is where most of the menu and HUD
  overhead goes away.
- **Shader-binary cache with LRU unload** — compiled shader programs are
  retrieved with `glGetProgramBinary`, stored on disk keyed by a hash of
  `GL_VERSION` + `GL_RENDERER`, and reloaded with `glProgramBinary` on
  subsequent launches. Programs unused for a while (default 600 frames) are
  freed with `glDeleteProgram`. The Halo CE RK3326 port uses the same
  approach on the identical GPU to release roughly 50 MB after several
  levels; on a 1 GB system this is about memory stability as much as
  startup time.
- **AFBC** (Arm Frame Buffer Compression) explicitly enabled. It is
  integrated into the Mali-G31's memory path; the driver usually turns it
  on, but the launcher sets `MALI_AFBC=1` so it applies even when the EGL
  config was chosen without the usual attributes.
- **SDL2 KMSDRM pageflip fix** — the Mali driver advertises
  `DRM_CAP_ASYNC_PAGE_FLIP` but rejects the actual `drmModePageFlip` call
  with `-EINVAL`; every frame is dropped and the picture tears. The build
  patches SDL2 to retry without the async flag and disable it for the
  session.

**Runtime tuning**

- **CPU and GPU governors pinned to `performance`** by `WOTS2.sh` at launch,
  and restored on exit. `schedutil` reacts too slowly for a fixed-30-FPS
  game on this SoC; the frame time is much steadier when the clocks sit at
  the top.
- **ZRAM with the `lz4` compressor**. `lz4` compresses and decompresses
  noticeably faster than the default `lzo` on the in-order A35, and on a
  1 GB system page faults are constant enough that the difference is
  measurable.
- **Glibc allocator tuned** — `MALLOC_TRIM_THRESHOLD_` and
  `MALLOC_MMAP_THRESHOLD_` raised to 131072 bytes so glibc does not return
  memory to the kernel and immediately ask for it back, which fragments the
  1 GB of RAM over a long session.
- **Audio callback frequency reduced** — the SDL2 audio buffer is raised
  to 2048 samples. WOTS2 is single-player; latency does not matter, but the
  audio callback firing four times less often does.
- **`-static-libstdc++ -static-libgcc`** linked in. The `libc.so.6` stays
  dynamic so the GLIBC 2.31 compatibility with ArkOS is untouched; only the
  C++ and GCC runtimes are baked into the binary, which removes a whole
  class of `GLIBCXX_3.4.x not found` failures without changing the
  distribution compatibility.

- **A `port.ini` for runtime tuning** — resolution, frame rate, every
  lighting option, and fog distance are read at startup. The *Recommended*
  preset is also baked into the header defaults
  (`include/native/port_options.h`), so the port starts well even without
  the file being present.

## Optimisations in detail

Every change is implemented as a small, idempotent Python patch that runs
from the CI workflow before `cmake` configures the build. The patches never
touch the game's own source logic — they only extend the renderer, the
collision world, and the launcher.

### Where the RK3326 is slow, and what the port does about it

| Bottleneck | What the port does | Where |
|---|---|---|
| **CPU, hot loops** | `-fprefetch-loop-arrays`, `-funroll-loops`, NEON vertex-lerp, NEON frustum culling, NEON collision matrix multiply, NEON direction normaliser, NEON pairwise `Relative()`. | `cmake/aarch64-arkos.cmake`, `patches/wots2-neon.py`, `patches/wots2-collision-neon.py`, `patches/wots2-collision-relative-neon.py` |
| **GPU, bandwidth** | `glInvalidateFramebuffer` on depth and post-FBO, `glTexStorage2D` for framebuffer textures, AFBC enabled, async-buffer count bounded at 2. | `patches/wots2-gs-invalidate.py`, `patches/wots2-gs-tex-storage.py`, `WOTS2.sh` |
| **Draw calls** | 2D sprites sharing a texture batched into a single `glDrawArrays`; 3D meshes frustum-culled and fog-culled by their bounding box before the vertex-buffer upload. | `patches/wots2-gs-batch-2d.py`, `src/hal/gs.cpp` |
| **Shader compilation stalls** | Shader binaries cached on disk and reloaded by hash on the next launch; programs unused for 600 frames freed. | `patches/wots2-gs-shader-cache.py` |
| **Memory pressure** | Shader cache with LRU unload, glibc trim/mmap thresholds raised, ZRAM with `lz4`. | `patches/wots2-gs-shader-cache.py`, `WOTS2.sh` |
| **Audio CPU** | SDL2 buffer raised to 2048 samples so the callback fires four times less often. | `WOTS2.sh` |
| **Scheduling jitter** | CPU and GPU governors pinned to `performance`, restored on exit; `tailscaled` stopped during play. | `WOTS2.sh` |

### Which optimisations came from where

The RK3326 is well-trodden ground. Several of these techniques are adapted
directly from **the Halo CE RK3326 port** (`kattimasen-ops/halo-ce-rk3326-Port`),
which runs on the same Mali-G31 MP2 in the same class of handheld:

- The **KMSDRM pageflip workaround** for the Mali driver's async-flip bug.
- The **`-mno-outline-atomics`** insight — without it every atomic on the
  A35 traps into an LSE sequence the CPU does not implement.
- The **shader-program management** pattern that frees roughly 50 MB after
  several levels.
- The **audio-mixer reduction** that cuts the callback's CPU cost.
- The general **RK3326 tuning** (governors, ZRAM, allocator thresholds).

Where a technique is already in the upstream `decomp_wots2` code path
(widescreen, the modern-lighting passes, the in-between-frame
interpolation, the texture-pack loader), it is **left alone** — the port
only replaces or extends the parts that were written for desktop OpenGL.

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
lighting option on, a busy fight scene drops below 20 FPS. The recommended
preset for the M9 Pro keeps shadows, AO, god rays and dust off, bloom low,
and renders at 448×336. See [Performance](#performance).

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
