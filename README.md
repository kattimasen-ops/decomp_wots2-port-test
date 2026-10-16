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
living town of Amahara, and the same mods. The story and shop scripts run
through to the endings; sword fighting, guards, parries, item and equipment
management, shops, saving and loading all work.

Also in: the opening and ending movies, voiced dialogue, music and sound
effects, the sky, water, fog, and controller support.

The port has been booted on an M9 Pro (ArkOS4Clone 20260825) and confirmed to
launch, load a save, walk through Amahara, run scripted scenes, play audio,
and exit cleanly.

**Honest caveat:** the interactive parts of the town are not yet running at a
comfortable frame rate. Menus, cutscenes and scripted scenes are fine;
walking around town with several NPCs visible still drops well below the
target 30 FPS. See [Honest status](#honest-status).

## What this port adds on the RK3326

The upstream builds for desktop (OpenGL 3.3 core, x86_64 / aarch64). The
RK3326's Mali-G31 MP2 is a tile-based OpenGL ES 3.2 GPU with a very low
bandwidth budget and no desktop GL support. The M9 Pro shares 1 GB of DDR3
between the CPU, the GPU and the OS. This port is a full retarget from the
ground up.

**Graphics and CPU**

- **OpenGL ES 3.2 backend** — every shader rewritten to `#version 320 es`,
  sampled through EGL + libmali (`libmali-bifrost-g31-rxp0-gbm`), with
  explicit sampler bindings and `mediump` for colour maths where the
  half-float ALU is twice as fast.
- **NEON throughout the hot paths** — the vertex-lerp
  (`wots2_lerp_vertex`, `wots2_lerp_vertex3`), frustum culling
  (`wots2_box_outside`), the collision matrix multiply (`wots2_apply_neon`),
  the direction normaliser (`wots2_towards_neon`) and the pairwise
  `Relative()` in the collision world are hand-written NEON, with the
  load/store operations interleaved into the arithmetic so the A35's single
  load port never stalls the FMA pipeline.
- **Cortex-A35 code generation** — `-march=armv8-a+crc -mcpu=cortex-a35
  -mtune=cortex-a35 -mno-outline-atomics -fprefetch-loop-arrays`. The
  `-mno-outline-atomics` flag is critical: without it GCC emits calls to
  `__aarch64_ldadd4_acq_rel`, which is an LSE sequence the A35 does not
  implement, and every atomic becomes a SIGILL. The prefetch flag hides
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
- **2D draw-call batching** — successive 2D draws that share a texture and
  primitive type are merged into a single `glDrawArrays`, including the
  font glyphs. ARM's guidance for Mali is to keep the frame under ~500 draw
  calls; this is where most of the menu and HUD overhead goes away.
- **8 point lights per pixel, not 16.** The map's fragment shader used to
  loop over sixteen lanterns per pixel; the port caps that at eight, which
  is well past the point where the further lights contribute to the visible
  area, and halves the fragment-shader cost on the ground and walls.
- **SDL2 KMSDRM pageflip fix** — the Mali driver advertises
  `DRM_CAP_ASYNC_PAGE_FLIP` but rejects the actual `drmModePageFlip` call
  with `-EINVAL`; every frame is dropped and the picture tears. The build
  patches SDL2 to fall back to a synchronous flip for the session.

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
  memory to the kernel and immediately ask for it back.
- **Audio callback frequency reduced** — the SDL2 audio buffer is raised
  to 2048 samples. WOTS2 is single-player; latency does not matter, but the
  audio callback firing four times less often does.
- **`-static-libstdc++ -static-libgcc`** linked in. The `libc.so.6` stays
  dynamic so GLIBC 2.31 compatibility with ArkOS is untouched; only the
  C++ and GCC runtimes are baked into the binary, which removes a whole
  class of `GLIBCXX_3.4.x not found` failures without changing the
  distribution compatibility.
- **A `port.ini` for runtime tuning** — resolution, frame rate, every
  lighting option, and fog distance are read at startup. The *Recommended*
  preset is also baked into the header defaults
  (`include/native/port_options.h`).

**Controller mapping**

- **PS2 button layout, applied at the driver level.** On the R36S and its
  clones (the M9 Pro is one), the firmware's `GO-Super Gamepad` reports the
  face buttons in a different order from the physical labels. The port
  patches `src/hal/pad.cpp` so that the physical button the user presses is
  the PS2 button the game expects — see [Controls](#controls).

## Optimisations in detail

Every change is implemented as a small, idempotent Python patch that runs
from the CI workflow before `cmake` configures the build. The patches never
touch the game's own source logic — they only extend the renderer, the
collision world, and the launcher.

### Where the RK3326 is slow, and what the port does about it

| Bottleneck | What the port does | Where |
|---|---|---|
| **CPU, hot loops** | `-fprefetch-loop-arrays`, `-funroll-loops`, NEON vertex-lerp, NEON frustum culling, NEON collision matrix multiply, NEON direction normaliser, NEON pairwise `Relative()`. | `cmake/aarch64-arkos.cmake`, `patches/wots2-neon.py`, `patches/wots2-collision-neon.py`, `patches/wots2-collision-relative-neon.py` |
| **GPU, bandwidth** | `glInvalidateFramebuffer` on depth and post-FBO, `glTexStorage2D` for framebuffer textures, AFBC enabled, async-buffer count bounded. | `patches/wots2-gs-invalidate.py`, `patches/wots2-gs-tex-storage.py`, `WOTS2.sh` |
| **Draw calls** | 2D sprites sharing a texture batched into a single `glDrawArrays`; 3D meshes frustum-culled and fog-culled by their bounding box before the vertex-buffer upload. | `patches/wots2-gs-batch-2d.py`, `src/hal/gs.cpp` |
| **Fragment-shader cost** | Map point lights capped at 8 per pixel instead of 16. | `patches/wots2-gs-combat.py` |
| **Scheduling jitter** | CPU and GPU governors pinned to `performance`, restored on exit; `tailscaled` stopped during play. | `WOTS2.sh` |
| **Input mismatch** | PS2 button layout enforced in `pad.cpp`, independent of SDL's internal database. | `patches/wots2-pad-swap.py` |
| **Memory pressure** | Glibc trim/mmap thresholds raised, ZRAM with `lz4`. | `WOTS2.sh` |
| **Audio CPU** | SDL2 buffer raised to 2048 samples so the callback fires four times less often. | `WOTS2.sh` |

### Patches that are deliberately switched off

- **`wots2-persistent-buffers.py` — permanently disabled.** This patch
  replaces `glBufferData` with `glMapBufferRange` + `memcpy` on the vertex
  buffers. On the Mali-G31 driver, `glMapBufferRange` frequently returns a
  pointer that does not reflect the buffer's real contents, so the CPU
  writes vertex data into memory the GPU never reads. The result on the M9
  was a completely black title screen and a fully white in-game screen —
  the game was running, the sound and controls were fine, but every vertex
  in every mesh was garbage. This behaviour matches ARM's own Mali Best
  Practices, which recommends `glBufferSubData` and not `glMapBufferRange`
  for exactly this reason. `WOTS2.sh` exports
  `WOTS2_PERSISTENT_BUFFERS=0` and it must stay that way.

### Which optimisations came from where

Several of these techniques are adapted directly from **the Halo CE RK3326
port** (`kattimasen-ops/halo-ce-rk3326-Port`), which runs on the same
Mali-G31 MP2 in the same class of handheld:

- The **KMSDRM pageflip workaround** for the Mali driver's async-flip bug.
- The **`-mno-outline-atomics`** insight — without it every atomic on the
  A35 traps into an LSE sequence the CPU does not implement.
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
  shadows on the ground.
  - **Weather** — rain that rolls in by itself (or on F8): wet streets with puddles that catch the sky, splashes, eaves dripping after the shower, dry under the roofs, a grey sky.
  - **Bump mapping** on stone, wood, tiles and clothes, and an optional un-baked mode that relights the whole town from its sun.
  - **Wind and dust** — the game's own gusts made visible.
  - **Moods** — a look of its own for dawn, evening, night, indoors and the rain.

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
