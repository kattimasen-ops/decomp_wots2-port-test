// ══════════════════════════════════════════════════════════════════════
//  Way of the Samurai 2 — M9 Pro (RK3326) Port
//  main.cpp — Programm-Einstieg
//
//  Decompilation:  acklavidian (github.com/acklavidian/decomp_wots2)
//  RK3326-Port:    St0len-One
//  Target:         Rockchip RK3326 / Cortex-A35 / Mali-G31 MP2
// ══════════════════════════════════════════════════════════════════════
#include "game/map_db.h"
#include <vector>
#include <cstdio>
#include "engine/app.h"
#include "hal/gs.h"
#include "hal/iop.h"
#include "hal/pad.h"
#include "hal/spu2.h"
#include "native/archive.h"
#include "native/guest.h"
#include "native/hle.h"
#include "native/launcher.h"
#include "native/model.h"
#include "native/mods.h"
#include "native/port_options.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

static void shutdown() {
    hal::pad::shutdown();
    hal::spu2::shutdown();
    hal::gs::shutdown();
}

static void print_credits() {
    std::fprintf(stderr, "\n");
    std::fprintf(stderr, "=====================================================\n");
    std::fprintf(stderr, "  Way of the Samurai 2 - Native Port\n");
    std::fprintf(stderr, "  Target: Rockchip RK3326 / Cortex-A35 / Mali-G31\n");
    std::fprintf(stderr, "-----------------------------------------------------\n");
    std::fprintf(stderr, "  Decompilation:  acklavidian\n");
    std::fprintf(stderr, "                  github.com/acklavidian/decomp_wots2\n");
    std::fprintf(stderr, "  RK3326-Port:    St0len-One\n");
    std::fprintf(stderr, "-----------------------------------------------------\n");
    std::fprintf(stderr, "  Build: %s %s\n", __DATE__, __TIME__);
    std::fprintf(stderr, "=====================================================\n\n");
    std::fflush(stderr);
}

int main(int argc, char* argv[]) {
    print_credits();

    // Directory holding the files from the game disc (SLUS_208.93, VOLUME.DAT, …):
    // given, found, or unpacked from a disc image first (the launcher).
    std::string root = launcher::locate(argc, argv);

    // Map PS2 RAM and load the game's data into it before anything else
    // allocates in the low address range.
    if (!guest::init((root + "/SLUS_208.93").c_str()) ||
        !archive::open((root + "/VOLUME.DAT").c_str())) {
        fprintf(stderr, "usage: wots2 [directory with the disc's files | disc image | archive]\n");
        return 1;
    }
    hle::bind_all();
    hle::set_disc_root(root.c_str());

    hal::iop::init(root.c_str());

    // ── Port-Optionen (port.ini) ────────────────────────────────────
    // Liest port.ini und setzt hal::gs::Video + hal::gs::Lighting, BEVOR
    // der Renderer startet. Sucht in dieser Reihenfolge:
    //   1. ./port.ini            (neben dem Launcher-Skript)
    //   2. <root>/port.ini       (im Spieldaten-Verzeichnis)
    // Fehlt die Datei, bleibt alles auf Upstream-Default.
    {
        port_options::Options opts;
        bool loaded = false;
        const std::string candidates[] = {
            std::string("port.ini"),
            root + "/port.ini"
        };
        for (const auto& candidate : candidates) {
            if (FILE* f = fopen(candidate.c_str(), "rb")) {
                fclose(f);
                opts = port_options::load(candidate.c_str());
                loaded = true;
                break;
            }
        }
        if (!loaded) {
            fprintf(stderr, "[main] port.ini nicht gefunden - Defaults aktiv\n");
        }
        port_options::apply(opts);
    }

    hal::gs::init(640, 448, "Way of the Samurai 2 [St0len-One RK3326 port]");

    // Debug aid: WOTS2_VIDEO="aspect=1.7778,height=1080,fps=60" sets what the
    // video mods would (see hal::gs::Video), without any mod. Überschreibt
    // port.ini-Werte.
    if (const char* v = getenv("WOTS2_VIDEO")) {
        hal::gs::Video video = hal::gs::video();
        if (const char* at = strstr(v, "aspect=")) video.aspect = (float)atof(at + 7);
        if (const char* at = strstr(v, "height=")) video.height = atoi(at + 7);
        if (const char* at = strstr(v, "fps="))    video.fps = atoi(at + 4);
        hal::gs::set_video(video);
    }
    // Mods (the mods directory): after the game's functions are bound and
    // the window is up, before anything of the game runs.
    mods::load_all();
    hal::spu2::init();
    hal::pad::init();
    atexit(shutdown);

    // Debug aid: WOTS2_MODEL_VIEW=<character name or index> shows character
    // models on a turntable instead of starting the game.
    if (const char* which = getenv("WOTS2_MODEL_VIEW"))
        return model::run_viewer(which);
    if (const char* which = getenv("WOTS2_MAP_VIEW"))
        return model::run_map_viewer(which);

    // Debug aid: WOTS2_RUN_SCRIPT=<name> runs an event script in the VM alone.
    if (const char* script = getenv("WOTS2_RUN_SCRIPT")) {
        extern int hle_run_script(const char* name);
        return hle_run_script(script);
    }

    // Debug aid: WOTS2_DUMP_MAPS=1 prints the decompiled map database.
    if (getenv("WOTS2_DUMP_MAPS")) {
        MapDb* db = MapDb_Get();
        MapDb_Load(db, 0);
        std::vector<const MapInfo*> maps;
        for (GuestListNode* n = GuestList_Begin(&db->maps); n != GuestList_End(&db->maps); n = GuestList_Next(n))
            maps.push_back(guest::ptr<MapInfo>(n->value));
        printf("%zu maps, %u + %u areas, %d point sets (+%d)\n", maps.size(), db->links[0].size,
               db->links[1].size, db->count, db->count2);
        int mismatched = 0;
        for (size_t i = 0; i < maps.size(); i++)
            if (maps[i]->id != (int)i)
                mismatched++;
        printf("%d maps whose id differs from their position in the list\n", mismatched);
        for (size_t i = 0; i < maps.size(); i++)
            if (maps[i]->water) {
                float height;
                memcpy(&height, &maps[i]->waterParam, 4);
                printf("  map %2zu %-40s water %s at %.2f\n", i, guest::ptr<const char>(maps[i]->model),
                       guest::ptr<const char>(maps[i]->water), height);
            }
        for (int variant = 0; variant < 2; variant++) {
            int area = 0;
            for (GuestListNode* n = GuestList_Begin(&db->links[variant]); n != GuestList_End(&db->links[variant]);
                 n = GuestList_Next(n), area++) {
                AreaLink* link = guest::ptr<AreaLink>(n->value);
                const char* model = link->map >= 0 && link->map < (int)maps.size()
                                  ? guest::ptr<const char>(maps[link->map]->model) : "-";
                printf("  [%d] area %2d: map %2d %-40s (%s) exits:", variant, area, link->map, model,
                       link->map >= 0 && link->map < (int)maps.size() ? guest::ptr<const char>(maps[link->map]->collision) : "-");
                for (GuestMapNode* e = GuestIntMap_Begin(&link->exits); e != GuestIntMap_End(&link->exits);
                     e = GuestIntMap_Next(e)) {
                    AreaExit* exit = guest::ptr<AreaExit>(e->value);
                    printf(" %d\u2192%d(%s)", e->key, exit->target, exit->name ? guest::ptr<const char>(exit->name) : "");
                }
                printf("\n");
            }
        }
        return 0;
    }

    // The game's own main(): App_Init, then App_Run, which loops until the
    // window is closed (the pad poll handles that and exits).
    return GameMain();
}
