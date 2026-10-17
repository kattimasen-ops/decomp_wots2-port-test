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

**Honest caveat:** the interactive parts of the town are not yet at a
comfortable frame rate. Menus, cutscenes, scripted scenes, the dojo and the
shops are fine — 25–30 FPS at 448×336 render resolution. **Walking around the
open town with several NPCs visible drops to 14–19 FPS.** Two things make the
open town slow, and only one of them is understood well enough to attack
directly:

- **A ~28 ms base load** that is present in every town frame regardless of
  how much is drawn. Measured from `[perf]` and `[timing]` traces: at 58
  draw calls the frame still takes 32.6 ms. That is the NPC simulation,
  the skeleton updates, the motion player and the character skinning — not
  draw-call overhead.
- **~0.075 ms per draw call** on top of that. At 700 draw calls in a dense
  part of town this adds ~50 ms, which is why the busiest scenes hit
  12–15 FPS while quiet spots stay near 20.

The current code changes have **reduced draw calls** (map batching brings
~124 `glBufferData` calls down to ~15) and **skip work for distant NPCs**
(beyond 20 player-units for the draw path, beyond 28 for the simulation),
but neither heals the base load. The frame-timing patch
(`wots2-frame-timing.py`) was added to measure exactly where those 28 ms go;
the results will drive the next round of work. See [Honest status](#honest-status).

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
- **Map batching (`wots2-map-batching.py` v3)** — static map geometry is
  gathered once per texture+bias into per-tile runs, with per-tile ranges
  for culling. The `glBufferData` calls for the map drop from ~124 to ~15
  in the open town, and each run carries its own bounding box so the renderer
  can still cull it by frustum and fog distance.
- **8 point lights per pixel, not 16.** The map's fragment shader used to
  loop over sixteen lanterns per pixel; the port caps that at eight, which
  is well past the point where the further lights contribute to the visible
  area, and halves the fragment-shader cost on the ground and walls.
- **SDL2 KMSDRM pageflip fix** — the Mali driver advertises
  `DRM_CAP_ASYNC_PAGE_FLIP` but rejects the actual `drmModePageFlip` call
  with `-EINVAL`; every frame is dropped and the picture tears. The build
  patches SDL2 to fall back to a synchronous flip for the session.

**NPC culling — three independent levers, each with its own distance**

The character manager runs several passes per frame per NPC (simulation,
map collision, skeleton update, draw). On a busy town these add up. The port
adds three distance-based skips, **all measured from the player**, which is
why they are configured in a specific order — `MAX_DIST` measures from the
*camera*, and the camera sits 3–4 units behind the player, so anything
above `MAX_DIST − 4` in player units is already not drawn:

- `WOTS2_NPC_MAX_DIST` (default **30**, camera distance) — the hard draw
  cull. Anything further than this is not rendered at all. Setting it below
  ~26 means you will see pop-in.
- `WOTS2_CHARA_DRAW_SKIP_DIST` (default **20**, player distance) — NPCs
  beyond this are still drawn but with a simplified draw path: no
  `Lights_At` lookup, no `ground_eased`, no per-bone matrix multiplication
  (they hold their rest pose), and no shadow pass. Visible but frozen and
  statically lit. This must sit **below** `MAX_DIST − 4` or it never fires.
- `WOTS2_CHARA_SHADOW_SKIP_DIST` (default **12**, player distance) — no
  shadow pass for NPCs beyond this. Saves two draw calls per NPC.
- `WOTS2_NPC_SIM_DIST` (default **28**, player distance) — no simulation
  for NPCs beyond this. Their animations and motion player stop updating.
  Must sit above `MAX_DIST − 4` or you get visible frozen NPCs in view.

The `WOTS2.sh` prints the effective distance bands on launch so these can be
checked against each other without reading the source.

**Character pose pool (`wots2-chara-pose-pool.py` v3)** — the draw path used
`std::vector<float>` for the pose and head-pose buffers; on this path that is
up to two heap allocations per NPC per frame. v3 replaces them with static
buffers guarded by a 64-bone sanity check. Small win, but it removes
allocation jitter from the frame.

**Frame timing (`wots2-frame-timing.py` v1)** — an `#ifdef`-style timing
shim around every `CharaMgr_*` step (update, StepA–D, StepMap, Draw) that
writes a `[timing]` line to stdout every 30 frames with the per-step
milliseconds. Off-switch: `WOTS2_TIMING=0`. The overhead is ~1 µs per
frame; it is on by default because the numbers are what the next round of
optimisation has to be based on. This is the patch that produced the
"~28 ms base load" figure above.

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
collision world, the character pipeline and the launcher.

### Where the RK3326 is slow, and what the port does about it

| Bottleneck | What the port does | Where |
|---|---|---|
| **CPU, hot loops** | `-fprefetch-loop-arrays`, `-funroll-loops`, NEON vertex-lerp, NEON frustum culling, NEON collision matrix multiply, NEON direction normaliser, NEON pairwise `Relative()`. | `cmake/aarch64-arkos.cmake`, `patches/wots2-neon.py`, `patches/wots2-collision-neon.py`, `patches/wots2-collision-relative-neon.py` |
| **GPU, bandwidth** | `glInvalidateFramebuffer` on depth and post-FBO, `glTexStorage2D` for framebuffer textures, AFBC enabled, async-buffer count bounded. | `patches/wots2-gs-invalidate.py`, `patches/wots2-gs-tex-storage.py`, `WOTS2.sh` |
| **Draw calls (3D)** | Map geometry batched per texture+bias into per-tile runs, with a bounding box per run for frustum and fog culling. `glBufferData` calls in the open town drop from ~124 to ~15. | `patches/wots2-map-batching.py` |
| **Draw calls (2D)** | Successive 2D draws that share a texture and primitive type are merged into a single `glDrawArrays`, including font glyphs. | `patches/wots2-gs-batch-2d.py` |
| **NPC draw path** | Distant NPCs (>20 player-units) are drawn with a simplified path: static light, no per-bone matrix, no ground light, no shadow. Still visible. | `patches/wots2-chara-draw-lod.py` |
| **NPC shadow** | No shadow pass for NPCs beyond 12 player-units. Two draw calls saved per NPC. | `patches/wots2-chara-draw-lod.py` |
| **NPC simulation** | No character simulation for NPCs beyond 28 player-units. Animation and motion player stop for those. | `patches/wots2-npc-sim-distance.py` |
| **NPC hard draw cull** | Anything beyond 30 camera units is not drawn at all. | `patches/wots2-npc-max-dist.py` |
| **Chara caches** | Find-cache in the character manager, resources cache, body last-position array, map-collision cell cache, list-indexed chara pose pool. | `patches/wots2-chara-mgr-find-cache.py`, `wots2-chara-resources-cache.py`, `wots2-chara-body-last-array.py`, `wots2-map-collision-cell-cache.py`, `wots2-chara-pose-pool.py` |
| **Fragment-shader cost** | Map point lights capped at 8 per pixel instead of 16, then made runtime-tunable via `WOTS2_LIGHTS_MAX` (default 2). | `patches/wots2-gs-combat.py`, `patches/wots2-gs-lights-cap.py` |
| **Effect spawn count** | World-effect spawn loops scaled by `WOTS2_FX_SCALE` (default 0.25). | `patches/wots2-fx-scale.py` |
| **Scheduling jitter** | CPU and GPU governors pinned to `performance`, restored on exit; `tailscaled` stopped during play. | `WOTS2.sh` |
| **Input mismatch** | PS2 button layout enforced in `pad.cpp`, independent of SDL's internal database. | `patches/wots2-pad-swap.py` |
| **Memory pressure** | Glibc trim/mmap thresholds raised, ZRAM with `lz4`. | `WOTS2.sh` |
| **Audio CPU** | SDL2 buffer raised to 2048 samples so the callback fires four times less often. | `WOTS2.sh` |
| **Diagnosis** | `[perf]` line every 30 frames (draw calls, cull calls, ms, fps), `[cull]` line per frame when `WOTS2_TRACE_CULL=1`, `[timing]` line every 30 frames with per-step milliseconds. | `patches/wots2-gs-perf-trace-v3.py`, `patches/wots2-frame-timing.py` |

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
- **`wots2-merge-3d-draws.py` — structurally impossible to help.** Each
  `draw_mesh` has its own `Begin3D`/`End3D` pair, so the recording state's
  owner changes on every mesh; the merge condition
  `prev.owner == s_recOwner` is never true. Kept out of the workflow.
- **`wots2-gs-orphan-vbo.py` — 40× slower on Mali-G31.** Bufer orphaning
  is a desktop GL win that the Mali driver punishes. Measured at 0.4 FPS
  instead of 15. Kept out of the workflow.
- **`wots2-chara-shadow-interval.py` — flickering.** Skipping the shadow
  pass every N frames made the shadow visibly pulse. Not built.
- **`wots2-npc-lod-closer.py` — ineffective.** The parameter it adjusts
  (`CharaModels_Draw(Chara*, int)`) is the draw *pass*, not the LOD. The
  actual LOD selection lives in `CharaModels_Start(phase)`, which only
  handles phases 0–2 (the port ships LOD 1 only). Kept in the repo as a
  no-op but does not change the picture.

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
ArkOS4Clone SD card.

**From source:** the CI workflow (`.github/workflows/build-wots2.yml`) runs
on GitHub Actions; a full build takes about 20 minutes on a standard runner.
The only requirements on the runner side are `ubuntu-22.04` and the aarch64
multiarch packages installed by the workflow — nothing needs to be installed
locally.

## Configuration

`port.ini` (next to the binary) and the environment variables read by
`WOTS2.sh` are the two tuning surfaces. The most useful ones:

**Render**

| Option | Default | Effect |
|---|---|---|
| `render` | `448x336` | Internal resolution. **The single biggest FPS lever.** `320x240` is the next stop. |
| `fps` | `30` | Frame limiter. Higher values only make sense with the FPS-unlock mod. |
| `shadows` | `0` | Modern shadow pass. On Mali-G31 it is expensive. |
| `ao` | `0` | Screen-space ambient occlusion. |
| `bloom` | `0.10` | Bloom strength. `0` disables the pass. |
| `god_rays` | `0.00` | Sun shafts. Expensive. |

**Runtime (in `WOTS2.sh`)**

| Variable | Default | Effect |
|---|---|---|
| `WOTS2_NPC_MAX_DIST` | `30` | NPC draw cull (camera distance). |
| `WOTS2_CHARA_DRAW_SKIP_DIST` | `20` | NPCs beyond this (player distance) drawn with a simplified path. **Must stay below `MAX_DIST − 4`.** |
| `WOTS2_CHARA_SHADOW_SKIP_DIST` | `12` | No shadow pass for NPCs beyond this (player distance). |
| `WOTS2_NPC_SIM_DIST` | `28` | No character simulation for NPCs beyond this (player distance). |
| `WOTS2_LIGHTS_MAX` | `2` | Point lights per pixel on the map, 0..8. |
| `WOTS2_TIMING` | `1` | Frame-timing trace. Turn off if you want every microsecond back. |
| `WOTS2_PERF_TRACE` | `1` | `[perf]` line every 30 frames. |
| `WOTS2_TRACE_CULL` | `0` | `[cull]` line per frame. Very noisy; turn on only for investigation. |
| `WOTS2_FX_SCALE` | `0.25` | World-effect spawn count scale. |

**Rollback examples**

```sh
WOTS2_NPC_MAX_DIST=0  ./WOTS2.sh          # no NPC draw cull at all (reference)
WOTS2_NPC_SIM_DIST=0  ./WOTS2.sh          # no NPC sim skip
WOTS2_CHARA_DRAW_SKIP_DIST=0  ./WOTS2.sh  # full draw path for all NPCs
WOTS2_CHARA_SHADOW_SKIP_DIST=0 ./WOTS2.sh # shadows for all NPCs
WOTS2_TIMING=0        ./WOTS2.sh          # no timing trace
WOTS2_TRACE_CULL=1    ./WOTS2.sh          # per-frame cull trace (noisy)
