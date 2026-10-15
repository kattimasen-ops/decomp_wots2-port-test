cmake_minimum_required(VERSION 3.20)
project(wots2_native CXX C)

# ══════════════════════════════════════════════════════════════════════
#  Way of the Samurai 2 — M9 Pro (RK3326) Port
#  Build-Konfiguration
#
#  Decompilation:  acklavidian (github.com/acklavidian/decomp_wots2)
#  RK3326-Port:    St0len-One
#  Target:         Rockchip RK3326 / Cortex-A35 / Mali-G31 MP2
# ══════════════════════════════════════════════════════════════════════

# CMake 4.x Kompatibilität
if(CMAKE_VERSION VERSION_GREATER_EQUAL "3.30")
    set(CMAKE_POLICY_VERSION_MINIMUM 3.5)
endif()

# ── Globale Einstellungen ────────────────────────────────────────────
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# WOTS2 liest PS2-Gastmemory durch Casts jeder Art. Ohne dieses Flag
# optimiert GCC Aliasing-Annahmen, die den Code brechen.
add_compile_options(-fno-strict-aliasing)

if(WIN32)
    add_compile_definitions(GetThreadId=Ps2_GetThreadId)
endif()

# ── LTO ──────────────────────────────────────────────────────────────
# AUS wegen GCC-Bug 92872. Der Decomp definiert structs wie ScreenLayout
# zweimal (Header + anonymer Namespace in .cpp). Das ist ein ODR-Verstoß,
# den GCC 9 mit LTO nicht verkraftet — der Linker stürzt ab mit
# "lto1: internal compiler error: in warn_types_mismatch".
# GCC 10+ hat den Fix; das Build-Image hat GCC 9.4.
set(CMAKE_INTERPROCEDURAL_OPTIMIZATION FALSE)

# ── OpenGL ES 3.2 für Mali-G31 (RK3326) ──────────────────────────────
option(WOTS2_GLES "Build for OpenGL ES 3.2 (Mali-G31)" OFF)

# ── SDL2 ─────────────────────────────────────────────────────────────
find_package(SDL2 CONFIG QUIET)
if(NOT SDL2_FOUND)
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(SDL2 REQUIRED sdl2)
    add_library(SDL2::SDL2 INTERFACE IMPORTED)
    target_include_directories(SDL2::SDL2 INTERFACE ${SDL2_INCLUDE_DIRS})
    target_link_libraries(SDL2::SDL2 INTERFACE ${SDL2_LIBRARIES})
endif()

if(NOT TARGET SDL2::SDL2main)
    add_library(SDL2::SDL2main INTERFACE IMPORTED)
    if(TARGET SDL2::SDL2)
        target_link_libraries(SDL2::SDL2main INTERFACE SDL2::SDL2)
    endif()
endif()

# ── OpenGL / OpenGL ES ───────────────────────────────────────────────
if(WOTS2_GLES)
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(EGL   REQUIRED egl)
    pkg_check_modules(GLES2 REQUIRED glesv2)

    add_library(OpenGL::GL INTERFACE IMPORTED)
    target_include_directories(OpenGL::GL INTERFACE
        ${EGL_INCLUDE_DIRS} ${GLES2_INCLUDE_DIRS})
    target_link_libraries(OpenGL::GL INTERFACE
        ${EGL_LIBRARIES} ${GLES2_LIBRARIES})

    add_compile_definitions(WOTS2_GLES=1)
    message(STATUS "WOTS2: building for OpenGL ES 3.2 (Mali-G31)")
else()
    find_package(OpenGL REQUIRED)
    message(STATUS "WOTS2: building for Desktop OpenGL")
endif()

# ── HAL ──────────────────────────────────────────────────────────────
add_library(hal STATIC
    src/hal/gs.cpp
    src/hal/spu2.cpp
    src/hal/pad.cpp
    src/hal/iop.cpp
)
target_include_directories(hal PUBLIC include)
target_link_libraries(hal PUBLIC SDL2::SDL2 OpenGL::GL)

# ── Decompiled code that runs natively ───────────────────────────────
add_library(game STATIC
    src/engine/app.cpp
    src/engine/notice.cpp
    src/engine/scenes.cpp
    src/engine/scene_base.cpp
    src/engine/font.cpp
    src/engine/text_label.cpp
    src/engine/window.cpp
    src/engine/text_table.cpp
    src/engine/containers.cpp
    src/engine/mt_random.cpp
    src/engine/pad_repeat.cpp
    src/engine/param_file.cpp
    src/engine/screen_layout.cpp
    src/engine/sprite_draw.cpp
    src/engine/config.cpp
    src/engine/bgm.cpp
    src/engine/gs_shapes.cpp
    src/engine/model.cpp
    src/engine/motion.cpp
    src/game/game_scene.cpp
    src/game/title_menu.cpp
    src/game/title_bg.cpp
    src/game/menu_widgets.cpp
    src/game/settings_screen.cpp
    src/game/chara_setup.cpp
    src/game/name_input.cpp
    src/game/player_data.cpp
    src/game/item_select.cpp
    src/game/sword_db.cpp
    src/game/map_db.cpp
    src/game/map_collision.cpp
    src/game/gameplay_scene.cpp
    src/game/world.cpp
    src/game/hud.cpp
    src/game/spawner.cpp
    src/game/chara_mgr.cpp
    src/game/chara.cpp
    src/game/chara_body.cpp
    src/game/chara_control.cpp
    src/game/chara_motions.cpp
    src/game/ai_moves.cpp
    src/game/ai_fight.cpp
    src/game/camera.cpp
    src/game/pairs.cpp
    src/game/world_objects.cpp
    src/game/world_effects.cpp
    src/game/status_menu.cpp
    src/game/status_page.cpp
    src/game/items_page.cpp
    src/game/swords_page.cpp
    src/game/forge.cpp
    src/game/skill_sheets.cpp
    src/game/sword_info.cpp
    src/game/sword_safe.cpp
    src/game/results_scene.cpp
    src/game/records_screen.cpp
    src/game/eye_catch.cpp
    src/game/accessories.cpp
    src/game/dropped_swords.cpp
    src/game/shop_menu.cpp
    src/game/text_roll.cpp
    src/game/chara_face.cpp
    src/game/chara_look.cpp
    src/game/mcard.cpp
    src/game/point_lights.cpp
    src/game/sword_table.cpp
    src/game/movie_scenes.cpp
    src/game/chara_events.cpp
    src/game/script_vm.cpp
    src/game/event_player.cpp
    src/game/collision_world.cpp
    src/game/pad_commands.cpp
    src/game/sword_holder.cpp
    src/game/map_routes.cpp
    src/game/task.cpp
    src/game/task_mgr.cpp
    src/game/task_actions.cpp
    src/game/speech.cpp
    src/game/talk_mgr.cpp
    src/game/day_mgr.cpp
    src/game/pause_menu.cpp
    src/game/area_map.cpp
    src/game/chara_resources.cpp
)
target_include_directories(game PUBLIC include)
target_link_libraries(game PRIVATE hal)

# ── Decompiled code not wired in yet ─────────────────────────────────
add_library(wip OBJECT
    src/engine/sdk_vsync.cpp
    src/engine/sdk_tlb.cpp
)
target_include_directories(wip PUBLIC include)

# ── Native runtime ───────────────────────────────────────────────────
add_library(native STATIC
    src/native/guest.cpp
    src/native/archive.cpp
    src/native/launcher.cpp
    src/native/port_options.cpp
    src/native/sprites.cpp
    src/native/texture_pack.cpp
    src/native/model.cpp
    src/native/hle.cpp
    src/native/hle_gameplay.cpp
    src/native/hle_chara.cpp
    src/native/hle_tasks.cpp
    src/native/hle_script.cpp
    src/native/movie.cpp
    src/native/mcard_native.cpp
    src/native/mods.cpp
    src/native/editor.cpp
    src/native/enhancements.cpp
)
target_include_directories(native PUBLIC include)
target_link_libraries(native PRIVATE hal)

# ── Dear ImGui ───────────────────────────────────────────────────────
include(FetchContent)
FetchContent_Declare(imgui
    URL https://github.com/ocornut/imgui/archive/refs/tags/v1.91.9.tar.gz
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
FetchContent_MakeAvailable(imgui)

add_library(imgui STATIC
    ${imgui_SOURCE_DIR}/imgui.cpp
    ${imgui_SOURCE_DIR}/imgui_draw.cpp
    ${imgui_SOURCE_DIR}/imgui_tables.cpp
    ${imgui_SOURCE_DIR}/imgui_widgets.cpp
    ${imgui_SOURCE_DIR}/backends/imgui_impl_sdl2.cpp
    ${imgui_SOURCE_DIR}/backends/imgui_impl_opengl3.cpp
)
target_include_directories(imgui PUBLIC
    ${imgui_SOURCE_DIR}
    ${imgui_SOURCE_DIR}/backends)
target_link_libraries(imgui PUBLIC SDL2::SDL2)

if(WOTS2_GLES)
    target_compile_definitions(imgui PRIVATE IMGUI_IMPL_OPENGL_ES3)
    target_include_directories(imgui PRIVATE
        ${EGL_INCLUDE_DIRS} ${GLES2_INCLUDE_DIRS})
    target_link_libraries(imgui PUBLIC ${EGL_LIBRARIES} ${GLES2_LIBRARIES})
endif()

target_link_libraries(native PRIVATE imgui)

# ── xxHash (header-only) ─────────────────────────────────────────────
FetchContent_Declare(xxhash
    URL https://github.com/Cyan4973/xxHash/archive/refs/tags/v0.8.2.tar.gz
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
FetchContent_GetProperties(xxhash)
if(NOT xxhash_POPULATED)
    FetchContent_Populate(xxhash)
endif()
target_include_directories(native PRIVATE ${xxhash_SOURCE_DIR})

# ── libarchive ───────────────────────────────────────────────────────
find_package(LibArchive QUIET)
if(LibArchive_FOUND)
    target_compile_definitions(native PRIVATE WOTS2_LIBARCHIVE)
    target_include_directories(native PRIVATE ${LibArchive_INCLUDE_DIRS})
    target_link_libraries(native PUBLIC ${LibArchive_LIBRARIES})
    message(STATUS "WOTS2: libarchive gefunden — Disc-Images werden unterstützt")
else()
    message(STATUS "WOTS2: libarchive fehlt — Disc-Images werden NICHT unterstützt")
endif()

# ── Main executable ──────────────────────────────────────────────────
add_executable(wots2 src/main.cpp)

if(WIN32)
    target_link_libraries(wots2 PRIVATE
        -Wl,--start-group game native -Wl,--end-group
        hal imgui
        opengl32 comdlg32
        -mwindows -static-libgcc -static-libstdc++
        -Wl,-Bstatic -lwinpthread -Wl,-Bdynamic)
elseif(APPLE)
    target_link_libraries(wots2 PRIVATE
        game native game native hal imgui
        -Wl,-pagezero_size,0x10000)
else()
    target_link_libraries(wots2 PRIVATE
        -Wl,--start-group game native -Wl,--end-group
        hal imgui
        SDL2::SDL2main
        ${CMAKE_DL_LIBS})
endif()

# ── Mods ─────────────────────────────────────────────────────────────
file(GLOB mod_dirs RELATIVE ${CMAKE_SOURCE_DIR}/mods ${CMAKE_SOURCE_DIR}/mods/*)
foreach(mod ${mod_dirs})
    if(EXISTS ${CMAKE_SOURCE_DIR}/mods/${mod}/${mod}.cpp)
        add_library(mod_${mod} MODULE mods/${mod}/${mod}.cpp)
        target_include_directories(mod_${mod} PRIVATE include/mod)
        set_target_properties(mod_${mod} PROPERTIES
            PREFIX ""
            OUTPUT_NAME ${mod}
            LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/mods/${mod})
    endif()
endforeach()

# ── Build-Type Default ───────────────────────────────────────────────
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE RelWithDebInfo)
endif()
