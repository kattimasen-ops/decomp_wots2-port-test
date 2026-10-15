cmake_minimum_required(VERSION 3.20)
project(wots2_native CXX C)

# ══════════════════════════════════════════════════════════════════════
# CMake 4.x Kompatibilität
# ══════════════════════════════════════════════════════════════════════
# CMake 4.x hat alle Policies < 3.5 entfernt. Viele von FetchContent
# geladene Projekte (xxHash deklariert VERSION 2.8.12) werden sonst mit
# einem Hard-Error abgelehnt. Diese Variable sagt CMake, dass es die
# alten Policies trotzdem akzeptieren darf.
if(CMAKE_VERSION VERSION_GREATER_EQUAL "3.30")
    set(CMAKE_POLICY_VERSION_MINIMUM 3.5)
endif()

# ══════════════════════════════════════════════════════════════════════
# Globale Compiler-Einstellungen
# ══════════════════════════════════════════════════════════════════════
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# WOTS2 liest PS2-Gastmemory durch Casts jeder Art. Ohne dieses Flag
# optimiert GCC Aliasing-Annahmen, die den Code brechen.
add_compile_options(-fno-strict-aliasing)

if(WIN32)
    # Ein PS2-Kernel-Aufruf teilt den Namen mit einem Windows-Aufruf.
    add_compile_definitions(GetThreadId=Ps2_GetThreadId)
endif()

# ══════════════════════════════════════════════════════════════════════
# LTO (Link-Time Optimization)
# ══════════════════════════════════════════════════════════════════════
# Über CMake statt im Toolchain-File, damit einzelne Targets (imgui)
# es abschalten können. CMake's IPO nutzt -flto für GCC (unterstützt
# seit GCC 4.5), nicht -flto=auto (erst GCC 10).
set(CMAKE_INTERPROCEDURAL_OPTIMIZATION FALSE)

# ══════════════════════════════════════════════════════════════════════
# OpenGL ES 3.2 für Mali-G31 (RK3326)
# ══════════════════════════════════════════════════════════════════════
# Default OFF (Desktop-GL 3.3 für x86_64-Entwicklung).
# -DWOTS2_GLES=ON aktiviert den Mali-Pfad: EGL + GLESv2 statt libGL.
option(WOTS2_GLES "Build for OpenGL ES 3.2 (Mali-G31)" OFF)

# ══════════════════════════════════════════════════════════════════════
# SDL2
# ══════════════════════════════════════════════════════════════════════
# Bevorzugt SDL2Config.cmake (aus dem selbst gebauten SDL2 in
# $SDL2_INSTALL/lib/cmake/SDL2). Fällt auf pkg-config zurück, wenn die
# Config-Datei fehlt (z. B. bei Ubuntu-Paket-Installation ohne CMake-Modul).
find_package(SDL2 CONFIG QUIET)
if(NOT SDL2_FOUND)
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(SDL2 REQUIRED sdl2)
    add_library(SDL2::SDL2 INTERFACE IMPORTED)
    target_include_directories(SDL2::SDL2 INTERFACE ${SDL2_INCLUDE_DIRS})
    target_link_libraries(SDL2::SDL2 INTERFACE ${SDL2_LIBRARIES})
endif()

# SDL2::SDL2main ist nicht in jedem SDL2-Build vorhanden. Ohne Target
# würde target_link_libraries einen Hard-Error werfen.
if(NOT TARGET SDL2::SDL2main)
    add_library(SDL2::SDL2main INTERFACE IMPORTED)
    if(TARGET SDL2::SDL2)
        target_link_libraries(SDL2::SDL2main INTERFACE SDL2::SDL2)
    endif()
endif()

# ══════════════════════════════════════════════════════════════════════
# OpenGL / OpenGL ES
# ══════════════════════════════════════════════════════════════════════
# WICHTIG: find_package(OpenGL) beim Cross-Compile findet die
# x86_64-libGL des Hosts, wenn kein Sysroot-Filter greift. Für GLES
# umgehen wir es komplett und nutzen pkg-config mit den Cross-.pc-Dateien.
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

# ══════════════════════════════════════════════════════════════════════
# HAL (PS2 hardware abstraction)
# ══════════════════════════════════════════════════════════════════════
add_library(hal STATIC
    src/hal/gs.cpp
    src/hal/spu2.cpp
    src/hal/pad.cpp
    src/hal/iop.cpp
)
target_include_directories(hal PUBLIC include)
target_link_libraries(hal PUBLIC SDL2::SDL2 OpenGL::GL)

# ══════════════════════════════════════════════════════════════════════
# Decompiled code that runs natively
# ══════════════════════════════════════════════════════════════════════
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

# ══════════════════════════════════════════════════════════════════════
# Decompiled code not wired in yet (compiliert, aber nicht gelinkt)
# ══════════════════════════════════════════════════════════════════════
add_library(wip OBJECT
    src/engine/sdk_vsync.cpp
    src/engine/sdk_tlb.cpp
)
target_include_directories(wip PUBLIC include)

# ══════════════════════════════════════════════════════════════════════
# Native runtime
# ══════════════════════════════════════════════════════════════════════
add_library(native STATIC
    src/native/guest.cpp
    src/native/archive.cpp
    src/native/launcher.cpp
    src/native/port_options.cpp        # NEU: port.ini-Loader
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

# ══════════════════════════════════════════════════════════════════════
# Dear ImGui (Level-Editor)
# ══════════════════════════════════════════════════════════════════════
include(FetchContent)
FetchContent_Declare(imgui
    URL https://github.com/ocornut/imgui/archive/refs/tags/v1.91.9.tar.gz
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
FetchContent_MakeAvailable(imgui)

# WICHTIG: Es gibt KEINE imgui_impl_opengles3.cpp. Der Backend-File
# heißt immer imgui_impl_opengl3.cpp; das Define IMGUI_IMPL_OPENGL_ES3
# schaltet intern auf die GLES-Pfade (GLES3/gl3.h, EGL-Funktionsladung).
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
    # Der Backend braucht die GLES-Header im Include-Pfad und die
    # Verknüpfung gegen EGL/GLESv2.
    target_compile_definitions(imgui PRIVATE IMGUI_IMPL_OPENGL_ES3)
    target_include_directories(imgui PRIVATE
        ${EGL_INCLUDE_DIRS} ${GLES2_INCLUDE_DIRS})
    target_link_libraries(imgui PUBLIC ${EGL_LIBRARIES} ${GLES2_LIBRARIES})
endif()

# LTO kann ImGuis static-initialized Daten (GContext, Memory-Pools)
# wegoptimieren. Bekanntes Problem, das auf Mali-Ports zu Abstürzen
# beim ersten Frame führt. Wir schalten LTO für imgui explizit ab.
set_target_properties(imgui PROPERTIES INTERPROCEDURAL_OPTIMIZATION FALSE)

target_link_libraries(native PRIVATE imgui)

# ══════════════════════════════════════════════════════════════════════
# xxHash (XXH3, für PCSX2-Texturpacks)
# ══════════════════════════════════════════════════════════════════════
# xxHash v0.8.2 hat ein CMakeLists.txt mit cmake_minimum_required
# (VERSION 2.8.12) — das wird von CMake 4.x abgelehnt. Wir nutzen
# FetchContent_Populate (nur Quellen entpacken, KEIN add_subdirectory)
# und binden den Include-Pfad direkt ein (header-only via XXH_INLINE_ALL).
FetchContent_Declare(xxhash
    URL https://github.com/Cyan4973/xxHash/archive/refs/tags/v0.8.2.tar.gz
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
FetchContent_GetProperties(xxhash)
if(NOT xxhash_POPULATED)
    FetchContent_Populate(xxhash)
endif()
target_include_directories(native PRIVATE ${xxhash_SOURCE_DIR})

# ══════════════════════════════════════════════════════════════════════
# libarchive (Disc-Images entpacken)
# ══════════════════════════════════════════════════════════════════════
# Der Launcher entpackt .iso / .zip / .7z. find_package sucht im
# Sysroot nach libarchive. Wir erlauben explizite Pfadangabe.
find_package(LibArchive QUIET)
if(LibArchive_FOUND)
    target_compile_definitions(native PRIVATE WOTS2_LIBARCHIVE)
    target_include_directories(native PRIVATE ${LibArchive_INCLUDE_DIRS})
    target_link_libraries(native PUBLIC ${LibArchive_LIBRARIES})
    message(STATUS "WOTS2: libarchive gefunden — Disc-Images werden unterstützt")
else()
    message(STATUS "WOTS2: libarchive fehlt — Disc-Images werden NICHT unterstützt")
endif()

# ══════════════════════════════════════════════════════════════════════
# Main executable
# ══════════════════════════════════════════════════════════════════════
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
    # Linux (inkl. Cross-Compile für aarch64):
    # -Wl,--start-group ... --end-group löst Zyklen zwischen game/native auf.
    # SDL2::SDL2main kommt aus dem CONFIG-Paket oder dem Fallback-Target.
    target_link_libraries(wots2 PRIVATE
        -Wl,--start-group game native -Wl,--end-group
        hal imgui
        SDL2::SDL2main
        ${CMAKE_DL_LIBS})
endif()

# ══════════════════════════════════════════════════════════════════════
# Mods (mods/<name>/<name>.cpp → mods/<name>/<name>.so)
# ══════════════════════════════════════════════════════════════════════
# file(GLOB) mit relativen Pfaden: existiert mods/ nicht, bleibt die
# Liste leer — kein Fehler. (file(GLOB ... CONFIGURE_DEPENDS) wäre
# bei CI-Builds problematisch, weil CMake bei jedem Build neu prüft.)
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

# ══════════════════════════════════════════════════════════════════════
# Build-Type Default
# ══════════════════════════════════════════════════════════════════════
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE RelWithDebInfo)
endif()
