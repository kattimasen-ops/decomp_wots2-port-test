#!/bin/bash
# WOTS2.sh — Way of the Samurai 2 für M9 Pro / RK3326 / ArkOS4Clone
#
# RK3326-Port: St0len-One
# Target:      Rockchip RK3326 / Cortex-A35 / Mali-G31 MP2
#
# Killswitch:
#   gptokeyb wird mit "-k wots2" gestartet. Der Standard-Hotkey
#   (Select+Start) beendet wots2 sauber.
#
# ── Flags, die mit 0/1 geschaltet werden ─────────────────────────────────
#   WOTS2_NO_CULL=0/1               Frustum-Culling AUS (Default: 0 = an)
#   WOTS2_NO_BATCH=0/1              2D-Batching AUS (Default: 0 = an)
#   WOTS2_NO_BUMP=0/1               Bump-Mapping AUS (Default: 1 = aus)
#   WOTS2_NO_SHADOW=0/1             Shadow-Pass AUS (Default: 0 = an)
#   WOTS2_NO_MAP_BATCHING=0/1       Map-Batching AUS (Default: 0 = an)
#   WOTS2_TRACE_CULL=0/1            Cull-Statistik ins stdout (Default: 0 = aus)
#   WOTS2_PERF_TRACE=0/1            Frame-Zeiten loggen (Default: 1)
#   WOTS2_PAD_DIAG=0/1              Stick-Diagnose ins stderr (Default: 0)
#   WOTS2_SHADER_CACHE=0/1          Shader-Cache (Default: 1)
#   WOTS2_TIMING=0/1                Frame-Timing ins stdout (Default: 1 für Analyse)
#   WOTS2_ATIMING=0/1               App-Loop-Timing [atiming] (Default: 1 für Analyse)
#   WOTS2_NO_BLOOM=0/1              Bloom-Pass AUS (Default: 1 = aus)
#   WOTS2_NO_POST=0/1               Komplette Post-Kette AUS (Default: unset)
#   WOTS2_NO_VSYNC=0/1              V-Sync AUS (Default: 1; wird seit wots2-gs-novsync.py honoriert)
#   WOTS2_PERSISTENT_BUFFERS        NIEMALS setzen. Auf Mali-G31 kaputt.
#
# ── Presets ──────────────────────────────────────────────────────────────
#   WOTS2_PRESET=max | balanced (Standard) | quality
#   Jeder Einzelwert darf weiter von aussen ueberschrieben werden, zum Beispiel:
#     WOTS2_PRESET=quality WOTS2_NPC_MAX_DIST=20 ./WOTS2.sh
#
# ── Zahlenwerte (vom Preset gesetzt, einzeln ueberschreibbar) ────────────
#   WOTS2_NPC_LOD_DIST=N            Fern-Modell ab N (Kamera-Distanz); wirkt seit
#                                   wots2-npc-lod-closer v2, mit Hysterese
#   WOTS2_NPC_MAX_DIST=N            Draw-Cull (Kamera-Distanz)
#   WOTS2_NPC_FADE_LEN=N            Laenge der Ausblendung vor MAX_DIST (Standard 4)
#   WOTS2_NPC_FADE_END=N            Ende der Ausblendung (Standard MAX_DIST - 0.5)
#   WOTS2_NPC_SIM_DIST=N            Sim-Skip (Spieler-Distanz); muss ueber der
#                                   Zeichenreichweite (MAX_DIST - 3.5) liegen
#   WOTS2_CHARA_DRAW_SKIP_DIST=N    Rest-Pose-Zone ab N (Spieler-D., 0 = aus)
#   WOTS2_CHARA_SHADOW_SKIP_DIST=N  Schatten nur bis N (Spieler-D.)
#   WOTS2_SWORD_DRAW_DIST=N         Schwert-Draw-Skip (Kamera-D., 999 = aus)
#   WOTS2_LIGHTS_MAX=N              Punktlichter pro Frame
#   WOTS2_SHADER_LRU=N              Frames bis Shader-Unload
#   WOTS2_SHADOW_RES=N              Kantenlaenge der Figuren-Schatten-Textur
#   WOTS2_FX_SCALE=N                Effekt-Anzahl
#   WOTS2_SHADOW_INTERVAL=N         Shadow-Redraw alle N Frames (Default: 1)
#   WOTS2_SPLASH=N                  Splash-Dauer in Sekunden (Default: 2.5)
#   WOTS2_KILL_TIMEOUT=N            Sekunden bis SIGKILL (Default: 3)
#
# ── Launcher-Schalter ────────────────────────────────────────────────────
#   WOTS2_ANALYSE=0/1               Timing-Logs ([timing], [gtiming], [perf] ...)
#                                   an/aus (Default: 1). Zum Spielen auf 0 setzen.
#   WOTS2_LIBDIAG=0/1               LD_DEBUG-Probe, startet das Spiel 5 s vorab (Default: 0)
#   WOTS2_DMC_PERF=0/1              Speichertakt (DDR) auf 'performance' (Default: 1)
#   WOTS2_CPU_UNCAP=0/1             scaling_max_freq auf cpuinfo_max_freq heben (Default: 0)
#   WOTS2_HWMON=0/1                 Takte/Last/Temperatur mitloggen (Default: 1)
#   WOTS2_HWMON_INTERVAL=N          Abtastung in Sekunden (Default: 10)
#   WOTS2_NICE=N                    Prioritaet des Spiels per renice (Default: -5, 0 = aus)
#   MALLOC_MMAP_THRESHOLD_ / MALLOC_TRIM_THRESHOLD_ / MALLOC_TOP_PAD_
#                                   glibc-Speicher-Tuning, einzeln ueberschreibbar
#
# ── Wichtiger Hinweis zu getenv() ────────────────────────────────────────
# Der Port prüft seine Flags mit getenv(...) != nullptr. Deshalb werden
# alle Bool-Flags mit wots2_export_flag() gesetzt: nur exportieren wenn
# 1, sonst unset.

XDG_DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}

export WOTS2_LIBDIAG="${WOTS2_LIBDIAG:-0}"   # 1 = Spiel startet 5 s vorab zur Bibliotheks-Diagnose
WOTS2_KILL_TIMEOUT="${WOTS2_KILL_TIMEOUT:-3}"

# ── Flag-Helfer ──────────────────────────────────────────────────────────
wots2_export_flag() {
    local var="$1" default="$2"
    local value="${!var:-$default}"
    if [ "$value" = "1" ]; then
        export "$var=1"
    else
        unset "$var"
    fi
}

# ── PFADE ────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
[ -z "$SCRIPT_DIR" ] && { echo "FEHLER: SCRIPT_DIR nicht ermittelbar." >&2; exit 1; }
GAMEDIR="$SCRIPT_DIR/wots2"
[ ! -d "$GAMEDIR" ] && { echo "FEHLER: $GAMEDIR fehlt." >&2; exit 1; }
cd "$GAMEDIR" || exit 1

EXTRACTED="$GAMEDIR/extracted"
DATA_ROOT="$GAMEDIR"
CHDMAN="$GAMEDIR/chdman"

# ── LOGGING ──────────────────────────────────────────────────────────
LOG="$GAMEDIR/log.txt"
if [ -f "$LOG" ] && [ "$(stat -c%s "$LOG" 2>/dev/null || echo 0)" -gt 2097152 ]; then
    mv -f "$LOG" "$LOG.1" 2>/dev/null || true
fi
if ! touch "$LOG" 2>/dev/null; then
    LOG="/tmp/wots2-log.txt"
    touch "$LOG" 2>/dev/null || LOG="/dev/null"
fi
exec >> "$LOG" 2>&1

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
log_section() {
    log ""
    log "========================================================="
    log "== $*"
    log "========================================================="
}

log_pipe() {
    while IFS= read -r line; do log "    $line"; done
}

log_binary_info() {
    local bin="$1"
    [ ! -e "$bin" ] && { log "  ($bin existiert nicht)"; return; }
    if command -v file >/dev/null 2>&1; then
        log "  file $bin:"
        file "$bin" 2>&1 | log_pipe
    fi
    if command -v readelf >/dev/null 2>&1; then
        log "  readelf -d $bin | NEEDED:"
        readelf -d "$bin" 2>/dev/null | grep NEEDED | log_pipe || log "    (keine NEEDED)"
    fi
    if command -v ldd >/dev/null 2>&1; then
        log "  ldd $bin:"
        ldd "$bin" 2>&1 | log_pipe || true
    fi
}

log_flag() {
    local var="$1" meaning_on="$2"
    if [ -n "${!var:-}" ]; then
        log "  $var=${!var}  ->  $meaning_on"
    else
        log "  $var=(unset)  ->  aus"
    fi
}

find_gptokeyb() {
    GPTOKEYB_PATH=""
    if command -v gptokeyb >/dev/null 2>&1; then
        GPTOKEYB_PATH="$(command -v gptokeyb)"
        return 0
    fi
    for cand in \
        "/opt/system/Tools/PortMaster/gptokeyb" \
        "/opt/system/Tools/gptokeyb" \
        "/opt/tools/PortMaster/gptokeyb" \
        "/roms/ports/PortMaster/gptokeyb" \
        "$PM_CONTROLFOLDER/gptokeyb" \
        "/usr/local/bin/gptokeyb" \
        "/usr/bin/gptokeyb" \
        "/usr/local/sbin/gptokeyb" \
        "/usr/sbin/gptokeyb"; do
        if [ -n "$cand" ] && [ -x "$cand" ]; then
            GPTOKEYB_PATH="$cand"
            return 0
        fi
    done
    return 1
}

log_section "WOTS2 START"
log "SCRIPT_DIR=$SCRIPT_DIR"
log "GAMEDIR=$GAMEDIR"
log "Kernel=$(uname -r), Arch=$(uname -m)"
log "Datum=$(date)"
log "WOTS2_LIBDIAG=$WOTS2_LIBDIAG"
log "WOTS2_KILL_TIMEOUT=$WOTS2_KILL_TIMEOUT"

# ── LOCK ─────────────────────────────────────────────────────────────
exec 9> /tmp/wots2-lock 2>/dev/null || true
if [ -e /proc/self/fd/9 ]; then
    if ! { flock -n 9 || python3 -c 'import fcntl; fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)' 2>/dev/null; } 2>/dev/null; then
        log "WOTS2 laeuft bereits."
        exit 1
    fi
fi

# ── PORTMASTER-CONTROLS ──────────────────────────────────────────────
PM_CONTROLFOLDER=""
for candidate in \
    "/opt/system/Tools/PortMaster" \
    "/opt/tools/PortMaster" \
    "$XDG_DATA_HOME/PortMaster" \
    "/roms/ports/PortMaster"; do
    [ -d "$candidate" ] && PM_CONTROLFOLDER="$candidate" && break
done

if [ -n "$PM_CONTROLFOLDER" ] && [ -f "$PM_CONTROLFOLDER/control.txt" ]; then
    source "$PM_CONTROLFOLDER/control.txt" 2>/dev/null || true
    if [ -n "${CFW_NAME:-}" ] && [ -f "$PM_CONTROLFOLDER/mod_${CFW_NAME}.txt" ]; then
        source "$PM_CONTROLFOLDER/mod_${CFW_NAME}.txt" 2>/dev/null || true
    fi
    command -v get_controls >/dev/null 2>&1 && get_controls 2>/dev/null || true
    log "PortMaster control.txt geladen aus $PM_CONTROLFOLDER"
fi

# ── SDL-GAMECONTROLLER + DIAGNOSE-DUMP ───────────────────────────────
SDL_DIAG="$GAMEDIR/sdl_diag.txt"
: > "$SDL_DIAG"
{
    echo "=== WOTS2 SDL-Diagnose $(date) ==="
    echo "--- /proc/bus/input/devices ---"
    if [ -f /proc/bus/input/devices ]; then
        grep -E '^(I|N|P|S|U|H):' /proc/bus/input/devices || true
    fi
    echo "--- es_input.cfg Kandidaten ---"
    for f in /userdata/system/configs/emulationstation/es_input.cfg \
             /usr/share/emulationstation/es_input.cfg; do
        if [ -f "$f" ]; then
            echo "### $f"
            cat "$f"
            echo "### /$f"
        fi
    done
} >> "$SDL_DIAG" 2>&1

if [ -n "${sdl_controllerconfig:-}" ]; then
    export SDL_GAMECONTROLLERCONFIG="$sdl_controllerconfig"
    log "SDL_GAMECONTROLLERCONFIG aus PortMaster gesetzt."
elif [ -f "$GAMEDIR/sdl_mapping.py" ]; then
    SDL_MAP="$(cd "$GAMEDIR" && python3 sdl_mapping.py 2>>"$SDL_DIAG")"
    if [ -n "$SDL_MAP" ]; then
        export SDL_GAMECONTROLLERCONFIG="$SDL_MAP"
        log "SDL_GAMECONTROLLERCONFIG aus sdl_mapping.py gesetzt."
    else
        log "sdl_mapping.py hat nichts ausgegeben — SDL benutzt die interne Datenbank."
    fi
fi

if [ -n "${SDL_GAMECONTROLLERCONFIG:-}" ]; then
    export SDL_GAMECONTROLLERCONFIG_FILE="/tmp/wots2-gamecontrollerdb.txt"
    printf '%s\n' "$SDL_GAMECONTROLLERCONFIG" > "$SDL_GAMECONTROLLERCONFIG_FILE" 2>/dev/null || true
    log "SDL_GAMECONTROLLERCONFIG_FILE gesetzt: $SDL_GAMECONTROLLERCONFIG_FILE"
fi

# ── SYSTEMOPTIMIERUNG ────────────────────────────────────────────────
log_section "SYSTEMOPTIMIERUNG"

cpu_governor_path=""
for candidate in \
    /sys/devices/system/cpu/cpufreq/policy0/scaling_governor \
    /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; do
    [ -w "$candidate" ] && cpu_governor_path="$candidate" && break
done
cpu_saved=""
if [ -n "$cpu_governor_path" ]; then
    cpu_saved=$(cat "$cpu_governor_path" 2>/dev/null)
    log "CPU-Governor: $cpu_saved -> performance"
    echo performance > "$cpu_governor_path" 2>/dev/null || true
fi
for cpu in /sys/devices/system/cpu/cpu[0-9]*; do
    [ -w "$cpu/cpufreq/scaling_governor" ] && \
        echo performance > "$cpu/cpufreq/scaling_governor" 2>/dev/null || true
done

gpu_devfreq_path=""
for candidate in /sys/class/devfreq/ff400000.gpu /sys/class/devfreq/gpu; do
    [ -d "$candidate" ] && gpu_devfreq_path="$candidate" && break
done
gpu_gov_saved=""; gpu_min_saved=""
if [ -n "$gpu_devfreq_path" ]; then
    [ -r "$gpu_devfreq_path/governor" ] && gpu_gov_saved=$(cat "$gpu_devfreq_path/governor" 2>/dev/null)
    log "GPU-Governor: $gpu_gov_saved -> performance"
    [ -w "$gpu_devfreq_path/governor" ] && \
        echo performance > "$gpu_devfreq_path/governor" 2>/dev/null || true
    if [ -r "$gpu_devfreq_path/available_frequencies" ] && [ -w "$gpu_devfreq_path/min_freq" ]; then
        gpu_min_saved=$(cat "$gpu_devfreq_path/min_freq" 2>/dev/null)
        max_freq=$(tr ' ' '\n' < "$gpu_devfreq_path/available_frequencies" | sort -n | tail -n 1)
        [ -n "$max_freq" ] && echo "$max_freq" > "$gpu_devfreq_path/min_freq" 2>/dev/null || true
    fi
fi

# ── Speichertakt (DMC): auf dem RK3326 teilen sich CPU und Mali den DDR-Speicher.
# Ein trager Speichertakt-Governor bremst beide. Nur wenn der Pfad existiert und
# 'performance' angeboten wird; die Wiederherstellung steht in restore().
dmc_devfreq_path=""; dmc_gov_saved=""
if [ "${WOTS2_DMC_PERF:-1}" = "1" ]; then
    for candidate in /sys/class/devfreq/dmc /sys/class/devfreq/*dmc*; do
        [ -d "$candidate" ] && [ -e "$candidate/governor" ] && dmc_devfreq_path="$candidate" && break
    done
fi
if [ -n "$dmc_devfreq_path" ]; then
    if [ -w "$dmc_devfreq_path/governor" ] && grep -qw performance "$dmc_devfreq_path/available_governors" 2>/dev/null; then
        dmc_gov_saved=$(cat "$dmc_devfreq_path/governor" 2>/dev/null)
        echo performance > "$dmc_devfreq_path/governor" 2>/dev/null || true
        log "DMC-Governor (Speichertakt): $dmc_gov_saved -> $(cat "$dmc_devfreq_path/governor" 2>/dev/null)"
    else
        log "DMC gefunden ($dmc_devfreq_path), aber 'performance' nicht setzbar (verfuegbar: $(cat "$dmc_devfreq_path/available_governors" 2>/dev/null))"
    fi
else
    log "DMC-devfreq nicht gefunden oder abgeschaltet (WOTS2_DMC_PERF=0)."
fi

# ── CPU-Takt: nur loggen, optional die Obergrenze aufheben ───────────────
cpu_max_saved=""
cpu0_cf="/sys/devices/system/cpu/cpu0/cpufreq"
if [ -r "$cpu0_cf/cpuinfo_max_freq" ]; then
    log "CPU0 kHz: cpuinfo_max=$(cat "$cpu0_cf/cpuinfo_max_freq" 2>/dev/null) scaling_max=$(cat "$cpu0_cf/scaling_max_freq" 2>/dev/null) cur=$(cat "$cpu0_cf/scaling_cur_freq" 2>/dev/null)"
    if [ "$(cat "$cpu0_cf/scaling_max_freq" 2>/dev/null)" != "$(cat "$cpu0_cf/cpuinfo_max_freq" 2>/dev/null)" ]; then
        if [ "${WOTS2_CPU_UNCAP:-0}" = "1" ] && [ -w "$cpu0_cf/scaling_max_freq" ]; then
            cpu_max_saved=$(cat "$cpu0_cf/scaling_max_freq" 2>/dev/null)
            for cpu in /sys/devices/system/cpu/cpu[0-9]*; do
                [ -w "$cpu/cpufreq/scaling_max_freq" ] && \
                    cat "$cpu/cpufreq/cpuinfo_max_freq" > "$cpu/cpufreq/scaling_max_freq" 2>/dev/null || true
            done
            log "CPU-Obergrenze angehoben: $cpu_max_saved -> $(cat "$cpu0_cf/scaling_max_freq" 2>/dev/null) kHz (WOTS2_CPU_UNCAP=1)"
        else
            log "  Hinweis: scaling_max liegt unter cpuinfo_max, die CPU taktet nicht voll hoch. Mit WOTS2_CPU_UNCAP=1 aufhebbar."
        fi
    fi
fi

if ! swapon --show 2>/dev/null | grep -q zram; then
    modprobe zram 2>/dev/null || true
    if [ -e /dev/zram0 ]; then
        if grep -q lz4 /sys/block/zram0/comp_algorithm 2>/dev/null; then
            echo lz4 > /sys/block/zram0/comp_algorithm 2>/dev/null || true
            log "ZRAM-Kompressor: lz4"
        else
            log "ZRAM-Kompressor: Standard (lzo)"
        fi
        echo 512M > /sys/block/zram0/disksize 2>/dev/null || true
        mkswap /dev/zram0 >/dev/null 2>&1 || true
        swapon /dev/zram0 2>/dev/null || true
        log "ZRAM aktiviert."
    fi
else
    log "ZRAM bereits aktiv."
fi

WOTS2_SERVICE_STATE="/tmp/wots2-services.$$"
WOTS2_SERVICES_RESTORED=0
stop_service_if_active() {
    local service="$1"
    if command -v systemctl >/dev/null 2>&1 && \
       systemctl is-active --quiet "$service" 2>/dev/null; then
        echo "$service" >> "$WOTS2_SERVICE_STATE" 2>/dev/null || true
        log "stopping $service"
        command -v sudo >/dev/null 2>&1 && sudo -n systemctl stop "$service" 2>/dev/null || true
    fi
}
restore_services() {
    [ "$WOTS2_SERVICES_RESTORED" = "0" ] || return 0
    WOTS2_SERVICES_RESTORED=1
    if [ -f "$WOTS2_SERVICE_STATE" ]; then
        while IFS= read -r service; do
            [ -n "$service" ] || continue
            log "restoring $service"
            command -v sudo >/dev/null 2>&1 && sudo -n systemctl start "$service" 2>/dev/null || true
        done < "$WOTS2_SERVICE_STATE"
        rm -f "$WOTS2_SERVICE_STATE" 2>/dev/null || true
    fi
}
: > "$WOTS2_SERVICE_STATE" 2>/dev/null || true
stop_service_if_active tailscaled.service

saved=/tmp/wots2-clocks
printf '%s|%s|%s|%s|%s\n' "$cpu_saved" "$gpu_gov_saved" "$gpu_min_saved" "$dmc_gov_saved" "$cpu_max_saved" > "$saved" 2>/dev/null || true

restore() {
    log_section "RESTORE"
    if [ -f "$saved" ]; then
        IFS='|' read -r cpu_gov gpu_gov gpu_min dmc_gov cpu_max_old < "$saved"
        [ -n "$cpu_gov" ] && [ -n "$cpu_governor_path" ] && [ -w "$cpu_governor_path" ] && \
            echo "$cpu_gov" > "$cpu_governor_path" 2>/dev/null || true
        if [ -n "$gpu_devfreq_path" ]; then
            [ -n "$gpu_gov" ] && [ -w "$gpu_devfreq_path/governor" ] && \
                echo "$gpu_gov" > "$gpu_devfreq_path/governor" 2>/dev/null || true
            [ -n "$gpu_min" ] && [ -w "$gpu_devfreq_path/min_freq" ] && \
                echo "$gpu_min" > "$gpu_devfreq_path/min_freq" 2>/dev/null || true
        fi
        [ -n "$dmc_gov" ] && [ -n "$dmc_devfreq_path" ] && [ -w "$dmc_devfreq_path/governor" ] && \
            echo "$dmc_gov" > "$dmc_devfreq_path/governor" 2>/dev/null || true
        if [ -n "$cpu_max_old" ]; then
            for cpu in /sys/devices/system/cpu/cpu[0-9]*; do
                [ -w "$cpu/cpufreq/scaling_max_freq" ] && \
                    echo "$cpu_max_old" > "$cpu/cpufreq/scaling_max_freq" 2>/dev/null || true
            done
        fi
        rm -f "$saved"
    fi
    restore_services
    rm -f /var/run/battery-saver/wots2.pause 2>/dev/null || true
    log "Restore abgeschlossen."
}
trap restore EXIT

mkdir -p /var/run/battery-saver 2>/dev/null && \
    touch /var/run/battery-saver/wots2.pause 2>/dev/null || true

mkdir -p "$GAMEDIR/wots2_card" "$GAMEDIR/save" "$GAMEDIR/screenshots" \
         "$GAMEDIR/shader_cache" 2>/dev/null || true

# ── DRI-RECHTE ───────────────────────────────────────────────────────
log_section "DRI-RECHTE"
for node in /dev/dri/card0 /dev/dri/renderD128 /dev/fb0; do
    if [ -e "$node" ]; then
        if [ ! -r "$node" ] || [ ! -w "$node" ]; then
            log "$node war nicht les/schreibbar — setze chmod 666"
            sudo -n chmod 666 "$node" 2>/dev/null || true
        fi
        log "$node: $(stat -c '%A %U:%G' "$node" 2>/dev/null)"
    else
        log "$node: nicht vorhanden"
    fi
done

# ── MALI-SYMLINKS ────────────────────────────────────────────────────
log_section "MALI-SYMLINKS"
SYSTEM_MALI=""
for candidate in \
    /usr/lib/aarch64-linux-gnu/libmali-bifrost-g31-rxp0-gbm.so \
    /usr/local/lib/aarch64-linux-gnu/libmali-bifrost-g31-rxp0-gbm.so \
    /usr/lib/aarch64-linux-gnu/libmali-bifrost-g31-rxp0-wayland-gbm.so \
    /usr/lib/aarch64-linux-gnu/mali/libmali.so \
    /usr/lib/mali/libmali.so \
    /usr/lib/aarch64-linux-gnu/libmali.so.1 \
    /usr/lib/aarch64-linux-gnu/libmali.so \
    /usr/lib/libmali.so \
    /usr/local/lib/libmali.so \
    /usr/lib/aarch64-linux-gnu/libEGL.so.1 \
    /usr/lib/aarch64-linux-gnu/libEGL.so; do
    [ -f "$candidate" ] && SYSTEM_MALI="$candidate" && break
done

if [ -n "$SYSTEM_MALI" ]; then
    rm -rf /tmp/wots2-mali
    mkdir -p /tmp/wots2-mali
    for name in libmali.so.0 libmali.so.1 libmali.so libEGL.so.1 libEGL.so libGLESv2.so.2 libGLESv2.so libGLESv1_CM.so.1 libGLESv1_CM.so; do
        ln -sf "$SYSTEM_MALI" "/tmp/wots2-mali/$name"
    done
    export LD_LIBRARY_PATH="/tmp/wots2-mali:$GAMEDIR/libs.aarch64:$GAMEDIR:/roms/ports/libs:/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}"
    log "Mali-Blob: $SYSTEM_MALI"
    log "Symlinks in /tmp/wots2-mali/ erstellt (ohne libgbm)."
else
    log "WARNUNG: Kein Mali-Blob gefunden — nutze System-Libraries."
    export LD_LIBRARY_PATH="$GAMEDIR/libs.aarch64:$GAMEDIR:/roms/ports/libs:/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}"
fi

# ── ALSA-Volume auf Anschlag (RK817) ─────────────────────────────────
if command -v amixer >/dev/null 2>&1; then
    for ctrl in Playback Master PCM Speaker Headphone DAC; do
        amixer -c 0 sset "$ctrl" 100% unmute >/dev/null 2>&1 || true
    done
    amixer -c 0 cset numid=1 1 >/dev/null 2>&1 || true
fi

ASOUNDRC="$HOME/.asoundrc"
if [ -f "$ASOUNDRC" ]; then
    WOTS2_ASOUNDRC_EXPECTED="$(printf 'pcm.!default { type hw; card 0; device 0 }\nctl.!default { type hw; card 0 }\n')"
    if [ "$(cat "$ASOUNDRC" 2>/dev/null)" = "$WOTS2_ASOUNDRC_EXPECTED" ]; then
        mv -f "$ASOUNDRC" "$ASOUNDRC.wots2-backup" 2>/dev/null || rm -f "$ASOUNDRC" 2>/dev/null || true
        log "Alte .asoundrc gesichert."
    fi
fi

# ── SDL-UMGEBUNG ─────────────────────────────────────────────────────
export SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-kmsdrm}"
unset SDL_AUDIODRIVER
unset AUDIODEV

# ── WOTS2-PFADE ──────────────────────────────────────────────────────
export WOTS2_DATA_ROOT="$DATA_ROOT"
export WOTS2_SAVE_ROOT="$GAMEDIR/save"

# ── RUNTIME-TUNING ───────────────────────────────────────────────────
# V-Sync aus: seit wots2-gs-novsync.py wertet gs.cpp diese Variable endlich
# aus (vorher wurde nur WOTS2_FAST gelesen). ~15 ms Ersparnis pro Frame.
export WOTS2_NO_VSYNC=1
export WOTS2_BUTTON_REMAP=1

# glibc-Speicher: Wer MALLOC_MMAP_THRESHOLD_ setzt, schaltet die automatische
# Anpassung ab. Mit 128 KB gehen alle groesseren Puffer (Frame-Vertices, Batches)
# jedes Mal per mmap/munmap durch den Kernel und werden neu genullt. Hoehere
# Schwellen halten sie im Heap. Alles ueberschreibbar, zum A/B-Test mit den
# [timing]-Zeilen: z. B. MALLOC_MMAP_THRESHOLD_=131072 MALLOC_TRIM_THRESHOLD_=131072 ./WOTS2.sh
export MALLOC_MMAP_THRESHOLD_="${MALLOC_MMAP_THRESHOLD_:-4194304}"
export MALLOC_TRIM_THRESHOLD_="${MALLOC_TRIM_THRESHOLD_:-33554432}"
export MALLOC_TOP_PAD_="${MALLOC_TOP_PAD_:-4194304}"

# Diese drei sind keine dokumentierten Variablen des Mali-Treibers (libmali) und
# hatten in deinen Logs keinen nachweisbaren Effekt. Auskommentiert, nicht geloescht:
#export MALI_AFBC=1
#export MALI_MAX_ASYNC_BUFFER_COUNT=4
#export MALI_BUFFER_PREALLOC=1

export SDL_AUDIO_SAMPLES="${SDL_AUDIO_SAMPLES:-2048}"

# NEU: SDL2 im stabilen Double-Buffer-Modus halten (verhindert KMSDRM-Abstürze)
export SDL_KMSDRM_DOUBLE_BUFFER=1

# ── WOTS2-Flags: NUR exportieren wenn 1, sonst unset ─────────────────────
wots2_export_flag WOTS2_NO_CULL   0
wots2_export_flag WOTS2_NO_BATCH  0
wots2_export_flag WOTS2_NO_BUMP   1
wots2_export_flag WOTS2_NO_SHADOW 0
wots2_export_flag WOTS2_NO_MAP_BATCHING 0
wots2_export_flag WOTS2_TRACE_CULL  0
wots2_export_flag WOTS2_PERF_TRACE  "${WOTS2_ANALYSE:-1}"
wots2_export_flag WOTS2_PAD_DIAG    0
wots2_export_flag WOTS2_SHADER_CACHE 1
wots2_export_flag WOTS2_TIMING      "${WOTS2_ANALYSE:-1}"
wots2_export_flag WOTS2_ATIMING     "${WOTS2_ANALYSE:-1}"
wots2_export_flag WOTS2_NO_BLOOM    1
unset WOTS2_PERSISTENT_BUFFERS

# ══════════════════════════════════════════════════════════════════════
# DIE KILLER-FLAGS (Rendering-Optimierung)
# ══════════════════════════════════════════════════════════════════════
# Himmel, Wasser und Hitzeflimmern generieren massig Draw-Calls und 
# Polygone. Auf dem RK3326 deaktiviert für stabile Frameraten.
export WOTS2_NO_SKY=1
export WOTS2_NO_WATER=1
export WOTS2_NO_SHIMMER=1

# ══════════════════════════════════════════════════════════════════════
# WOTS2_NO_POST — Komplette Post-Kette aus (9-12 ms)
# ══════════════════════════════════════════════════════════════════════
# Der [gtiming]-Wert play.post war ~3,3 ms (Bloom+Grade) plus Blit in
# swap plus Depth-Buffer-Write in play.loop. Zusammen 9-12 ms laut
# letztem [gtiming]-Run.
#
# WARNUNG: Das Bild verliert dann Farbkorrektur, Bloom und alle Schatten
# (auch die vom Charakter). Sichtbar, aber spielbar. Wenn dir das zu
# aggressiv ist, lass es auskommentiert.
#
# # export WOTS2_NO_POST=1

# ── WOTS2-PRESET ─────────────────────────────────────────────────────────
# Entfernungen in Spieleinheiten. Die Kamera steht etwa 3,5 hinter dem Spieler, die
# Zeichenreichweite in Spieler-Distanz ist also etwa MAX_DIST - 3,5.
#   max       aggressiv: kuerzere Sicht, Schwerter ab 10 aus, kleine Schatten
#   balanced  Standard: Fern-Modell ab 8, Ausblendung ab 11,5, Schwerter blenden mit
#   quality   weit und hell: Original-LOD-Naehe 12, Sicht 24, 2 Lichter, mehr Effekte
# SIM_DIST liegt bewusst knapp unter MAX_DIST: Alles, was gezeichnet wird, wird auch
# simuliert, und NPCs starten ihre Bewegung ausserhalb des Bildes.
# DRAW_SKIP=0 schaltet die Rest-Pose-Zone aus (dort stehen NPCs sonst unbewegt da).
# SHADER_LRU 600 ist der Standard der README; 120 entlaedt Shader nach 4 s ohne Nutzung.
WOTS2_PRESET="${WOTS2_PRESET:-balanced}"
case "$WOTS2_PRESET" in
    max)      P_LOD=6;  P_MAX=14; P_SIM=13; P_DRAWSKIP=0; P_SHADOWSKIP=3;  P_SWORD=10;  P_LIGHTS=1; P_FX=0.05; P_LRU=120; P_SHRES=64  ;;
    quality)  P_LOD=12; P_MAX=24; P_SIM=23; P_DRAWSKIP=0; P_SHADOWSKIP=12; P_SWORD=999; P_LIGHTS=2; P_FX=0.25; P_LRU=600; P_SHRES=256 ;;
    *)        WOTS2_PRESET=balanced
              P_LOD=8;  P_MAX=16; P_SIM=15; P_DRAWSKIP=0; P_SHADOWSKIP=5;  P_SWORD=999; P_LIGHTS=1; P_FX=0.05; P_LRU=600; P_SHRES=128 ;;
esac
export WOTS2_SHADOW_INTERVAL="${WOTS2_SHADOW_INTERVAL:-1}"
export WOTS2_SHADER_LRU="${WOTS2_SHADER_LRU:-$P_LRU}"
export WOTS2_FX_SCALE="${WOTS2_FX_SCALE:-$P_FX}"
export WOTS2_SPLASH="${WOTS2_SPLASH:-2.5}"
export WOTS2_NPC_LOD_DIST="${WOTS2_NPC_LOD_DIST:-$P_LOD}"
export WOTS2_NPC_MAX_DIST="${WOTS2_NPC_MAX_DIST:-$P_MAX}"
export WOTS2_NPC_FADE_LEN="${WOTS2_NPC_FADE_LEN:-4}"
export WOTS2_NPC_SIM_DIST="${WOTS2_NPC_SIM_DIST:-$P_SIM}"
export WOTS2_CHARA_DRAW_SKIP_DIST="${WOTS2_CHARA_DRAW_SKIP_DIST:-$P_DRAWSKIP}"
export WOTS2_CHARA_SHADOW_SKIP_DIST="${WOTS2_CHARA_SHADOW_SKIP_DIST:-$P_SHADOWSKIP}"
export WOTS2_SWORD_DRAW_DIST="${WOTS2_SWORD_DRAW_DIST:-$P_SWORD}"
export WOTS2_LIGHTS_MAX="${WOTS2_LIGHTS_MAX:-$P_LIGHTS}"
export WOTS2_SHADOW_RES="${WOTS2_SHADOW_RES:-$P_SHRES}"

# ── BINARY-CHECK ─────────────────────────────────────────────────────
if [ ! -x ./wots2 ]; then
    log "FEHLER: ./wots2 fehlt oder nicht ausfuehrbar."
    echo "FEHLER: ./wots2 fehlt." >&2
    exit 1
fi

# ══════════════════════════════════════════════════════════════════════
# DIAGNOSE
# ══════════════════════════════════════════════════════════════════════
log_section "DIAGNOSE"

log "Umgebung:"
log "  LD_LIBRARY_PATH=$LD_LIBRARY_PATH"
log "  SDL_VIDEODRIVER=$SDL_VIDEODRIVER"
log "  SDL_GAMECONTROLLERCONFIG_FILE=${SDL_GAMECONTROLLERCONFIG_FILE:-(nicht gesetzt)}"
log "  WOTS2_DATA_ROOT=$WOTS2_DATA_ROOT"
log "  WOTS2_SAVE_ROOT=$WOTS2_SAVE_ROOT"
log ""
log "Flags (effektiv):"
log_flag WOTS2_NO_CULL    "Culling aus"
log_flag WOTS2_NO_BATCH   "2D-Batching aus"
log_flag WOTS2_NO_BUMP    "Bump-Mapping aus"
log_flag WOTS2_NO_SHADOW  "Shadow-Pass aus"
log_flag WOTS2_NO_MAP_BATCHING "Map-Batching aus"
log_flag WOTS2_TRACE_CULL  "Cull-Statistik an"
log_flag WOTS2_PERF_TRACE  "Perf-Trace an"
log_flag WOTS2_PAD_DIAG    "Stick-Diagnose an"
log_flag WOTS2_SHADER_CACHE "Shader-Cache an"
log_flag WOTS2_TIMING      "Frame-Timing an ([timing] + [gtiming] + [mtiming])"
log_flag WOTS2_ATIMING     "App-Loop-Timing an ([atiming])"
log_flag WOTS2_NO_BLOOM    "Bloom aus"
log_flag WOTS2_NO_POST     "Komplette Post-Kette aus (sichtbar!)"
log_flag WOTS2_NO_VSYNC    "V-Sync aus (Swap blockiert nicht mehr auf V-Blank)"
if [ -n "${WOTS2_PERSISTENT_BUFFERS:-}" ]; then
    log "  WOTS2_PERSISTENT_BUFFERS=${WOTS2_PERSISTENT_BUFFERS}  ->  WARNUNG, sollte unset sein"
else
    log "  WOTS2_PERSISTENT_BUFFERS=(unset)  ->  aus (korrekt)"
fi
log ""
log "Preset: $WOTS2_PRESET"
log "Zahlenwerte:"
log "  WOTS2_SHADOW_INTERVAL=$WOTS2_SHADOW_INTERVAL"
log "  WOTS2_SHADER_LRU=$WOTS2_SHADER_LRU"
log "  WOTS2_FX_SCALE=$WOTS2_FX_SCALE"
log "  WOTS2_SPLASH=$WOTS2_SPLASH"
log "  WOTS2_NPC_LOD_DIST=$WOTS2_NPC_LOD_DIST (Kamera-Distanz, Fern-Modell ab hier)"
log "  WOTS2_NPC_MAX_DIST=$WOTS2_NPC_MAX_DIST (Kamera-Distanz)"
log "  WOTS2_NPC_FADE_LEN=$WOTS2_NPC_FADE_LEN${WOTS2_NPC_FADE_END:+  WOTS2_NPC_FADE_END=$WOTS2_NPC_FADE_END}"
log "  WOTS2_NPC_SIM_DIST=$WOTS2_NPC_SIM_DIST (Spieler-Distanz, 0 = aus)"
log "  WOTS2_CHARA_DRAW_SKIP_DIST=$WOTS2_CHARA_DRAW_SKIP_DIST (Spieler-Distanz, 0 = aus)"
log "  WOTS2_CHARA_SHADOW_SKIP_DIST=$WOTS2_CHARA_SHADOW_SKIP_DIST (Spieler-Distanz)"
log "  WOTS2_SWORD_DRAW_DIST=$WOTS2_SWORD_DRAW_DIST (Kamera-Distanz, 999 = aus)"
log "  WOTS2_LIGHTS_MAX=$WOTS2_LIGHTS_MAX"
log "  WOTS2_SHADOW_RES=$WOTS2_SHADOW_RES"
log "  MALLOC_MMAP_THRESHOLD_=$MALLOC_MMAP_THRESHOLD_  MALLOC_TRIM_THRESHOLD_=$MALLOC_TRIM_THRESHOLD_  MALLOC_TOP_PAD_=$MALLOC_TOP_PAD_"
log "  SDL_AUDIO_SAMPLES=$SDL_AUDIO_SAMPLES"
log ""
# Rechnen mit awk, damit auch Kommawerte (z. B. 16.5) funktionieren.
w2_calc() { awk -v a="$1" -v b="$2" -v op="$3" 'BEGIN { if (op == "-") printf "%.1f", a - b; else printf "%.1f", a + b }' 2>/dev/null; }
w2_lt()   { awk -v a="$1" -v b="$2" 'BEGIN { exit !(a < b) }' 2>/dev/null; }
W2_RANGE=$(w2_calc "$WOTS2_NPC_MAX_DIST" 3.5 -)
W2_FADE_END="${WOTS2_NPC_FADE_END:-$(w2_calc "$WOTS2_NPC_MAX_DIST" 0.5 -)}"
W2_FADE_START=$(w2_calc "$W2_FADE_END" "$WOTS2_NPC_FADE_LEN" -)
log "Effektive Distanz-Baender (Naeherung, Kamera ~3.5u hinter Spieler):"
log "  gezeichnet (MAX_DIST):          0 .. ~${W2_RANGE}u Spieler-Distanz"
log "  Fern-Modell (LOD_DIST):         ab ${WOTS2_NPC_LOD_DIST}u Kamera-Distanz (Hysterese +-0.75)"
log "  Ausblendung (Dither):           ${W2_FADE_START} .. ${W2_FADE_END}u Kamera-Distanz"
if [ "${WOTS2_CHARA_DRAW_SKIP_DIST%%.*}" -gt 0 ] 2>/dev/null; then
    log "  nur Rest-Pose, kein Licht:      ab ${WOTS2_CHARA_DRAW_SKIP_DIST}u Spieler-Distanz  (kann wie Pop-in wirken)"
else
    log "  Rest-Pose-Zone:                 aus"
fi
log "  mit Schatten:                   0 .. ${WOTS2_CHARA_SHADOW_SKIP_DIST}u"
log "  simuliert (SIM_DIST):           0 .. ${WOTS2_NPC_SIM_DIST}u"
if w2_lt "$WOTS2_SWORD_DRAW_DIST" 900; then
    log "  Schwert gezeichnet:             0 .. ${WOTS2_SWORD_DRAW_DIST}u Kamera-Distanz"
else
    log "  Schwert gezeichnet:             immer (blendet mit der Figur aus)"
fi
if [ "${WOTS2_NPC_SIM_DIST%%.*}" -gt 0 ] 2>/dev/null && w2_lt "$WOTS2_NPC_SIM_DIST" "$(w2_calc "$W2_RANGE" 1 +)"; then
    log "  WARNUNG: SIM_DIST ($WOTS2_NPC_SIM_DIST) liegt zu nah an der Zeichenreichweite (~$W2_RANGE):"
    log "           NPCs wuerden gezeichnet, aber eingefroren sein. SIM_DIST sollte >= ~$(w2_calc "$W2_RANGE" 1.5 +) sein."
fi
if w2_lt "$WOTS2_NPC_MAX_DIST" "$WOTS2_NPC_LOD_DIST"; then
    log "  WARNUNG: LOD_DIST ($WOTS2_NPC_LOD_DIST) liegt ueber MAX_DIST ($WOTS2_NPC_MAX_DIST): das Fern-Modell wird nie genutzt."
fi

log ""
log "Bundle-Bibliotheken (libs.aarch64):"
if [ -d "$GAMEDIR/libs.aarch64" ]; then
    ls -la "$GAMEDIR/libs.aarch64" 2>&1 | log_pipe
    if [ -e "$GAMEDIR/libs.aarch64/libSDL2-2.0.so.0" ]; then
        log "  OK: libSDL2-2.0.so.0 im Bundle — System-SDL2 wird umgangen."
    else
        log "  WARNUNG: libSDL2-2.0.so.0 fehlt in libs.aarch64!"
    fi
else
    log "  (libs.aarch64 fehlt komplett)"
fi

log ""
log "Binary ./wots2:"
log_binary_info "./wots2"

if [ -x "$CHDMAN" ]; then
    log ""
    log "Binary ./chdman:"
    log_binary_info "./chdman"
fi

log ""
log "gptokeyb:"
if find_gptokeyb; then
    log "  gefunden: $GPTOKEYB_PATH"
else
    log "  NICHT gefunden — Kill-Hotkey (Select+Start) faellt aus."
fi

log ""
log "SDL-Diagnose-Dump: $SDL_DIAG ($(wc -l < "$SDL_DIAG" 2>/dev/null || echo 0) Zeilen)"

LIBDIAG_LOG="$GAMEDIR/wots2-libdiag.txt"
if [ "${WOTS2_LIBDIAG:-0}" = "1" ]; then
    log ""
    log "WOTS2_LIBDIAG=1: LD_DEBUG=libs Probe (max 5 Sekunden) ..."
    : > "$LIBDIAG_LOG"
    PROBE_OK=0
    if command -v timeout >/dev/null 2>&1; then
        ( LD_DEBUG=libs timeout 5 ./wots2 extracted ) > /dev/null 2>> "$LIBDIAG_LOG" || PROBE_OK=1
    else
        ( LD_DEBUG=libs ./wots2 extracted ) > /dev/null 2>> "$LIBDIAG_LOG" &
        DIAG_PID=$!
        ( sleep 5 && kill -TERM "$DIAG_PID" 2>/dev/null ) &
        KILLER_PID=$!
        wait "$DIAG_PID" 2>/dev/null || PROBE_OK=1
        kill -TERM "$KILLER_PID" 2>/dev/null || true
        wait "$KILLER_PID" 2>/dev/null || true
    fi
    if [ -s "$LIBDIAG_LOG" ]; then
        head -200 "$LIBDIAG_LOG" > "$LIBDIAG_LOG.head"
        mv -f "$LIBDIAG_LOG.head" "$LIBDIAG_LOG"
        LINES=$(wc -l < "$LIBDIAG_LOG")
        log "  $LIBDIAG_LOG geschrieben ($LINES Zeilen)"
        log "  Erste 20 Zeilen:"
        head -20 "$LIBDIAG_LOG" | log_pipe
    else
        log "  WARNUNG: LD_DEBUG hat nichts geschrieben."
    fi
    if [ "$PROBE_OK" = "1" ]; then
        log "  Hinweis: Der Probe-Lauf endete nicht regulaer —"
        log "  das Spiel ist entweder abgestuerzt oder braucht mehr als 5 Sekunden."
    fi
else
    log ""
    log "WOTS2_LIBDIAG=$WOTS2_LIBDIAG (Probe uebersprungen)."
fi

# ══════════════════════════════════════════════════════════════════════
# HELFER: Entpacker wählen
# ══════════════════════════════════════════════════════════════════════
pick_extractor() {
    if command -v bsdtar >/dev/null 2>&1; then echo "bsdtar"
    elif command -v 7z     >/dev/null 2>&1; then echo "7z"
    elif command -v 7za    >/dev/null 2>&1; then echo "7za"
    elif command -v unzip  >/dev/null 2>&1; then echo "unzip"
    else echo ""; fi
}

unpack_image() {
    local img="$1"
    local extractor
    extractor="$(pick_extractor)"
    if [ -z "$extractor" ]; then
        log "FEHLER: Kein Entpacker gefunden."
        return 1
    fi
    log "Entpacker: $extractor"
    local tmp="$GAMEDIR/.extract-tmp"
    rm -rf "$tmp"
    mkdir -p "$tmp"
    log "Entpacke $img nach $tmp ..."
    case "$extractor" in
        bsdtar) bsdtar -xf "$img" -C "$tmp" 2>>"$LOG" || return 1 ;;
        7z|7za) 7z x -y -o"$tmp" "$img" >>"$LOG" 2>&1 || return 1 ;;
        unzip)  unzip -o "$img" -d "$tmp" >>"$LOG" 2>&1 || return 1 ;;
    esac
    mkdir -p "$EXTRACTED"
    local subdir
    subdir="$(find "$tmp" -maxdepth 2 -type d \( -name 'PS2' -o -name 'SLUS*' \) 2>/dev/null | head -n 1)"
    if [ -n "$subdir" ] && [ -d "$subdir" ]; then
        log "Verschiebe Inhalt aus $subdir"
        cp -a "$subdir"/. "$EXTRACTED"/ 2>>"$LOG" || true
    else
        cp -a "$tmp"/. "$EXTRACTED"/ 2>>"$LOG" || true
    fi
    rm -rf "$tmp"
    return 0
}

# ══════════════════════════════════════════════════════════════════════
# ENTPACKEN — CHD zuerst, dann ISO, dann Archive
# ══════════════════════════════════════════════════════════════════════
log_section "SPIELDATEN ENTPACKEN"

if [ -f "$EXTRACTED/SLUS_208.93" ] || [ -f "$EXTRACTED/slus_208.93" ]; then
    log "extracted/ enthaelt bereits SLUS_208.93 — ueberspringe Entpacken."
else
    NEEDS_UNPACK=1

    CHD_FILE=""
    for cand in "$GAMEDIR"/*.chd "$GAMEDIR"/*.CHD \
                "$SCRIPT_DIR"/*.chd "$SCRIPT_DIR"/*.CHD; do
        [ -f "$cand" ] && { CHD_FILE="$cand"; break; }
    done

    if [ -n "$CHD_FILE" ]; then
        log "CHD gefunden: $CHD_FILE"
        if [ ! -x "$CHDMAN" ]; then
            log "FEHLER: chdman nicht gefunden unter $CHDMAN."
            echo "FEHLER: chdman fehlt." >&2
            exit 1
        fi
        TMP_CHD="$GAMEDIR/.chd-extract"
        rm -rf "$TMP_CHD"
        mkdir -p "$TMP_CHD"
        BASE="$(basename "$CHD_FILE")"
        BASE="${BASE%.chd}"; BASE="${BASE%.CHD}"
        log "Extrahiere CHD nach ISO ..."
        CHD_ISO=""
        if "$CHDMAN" extractdvd -i "$CHD_FILE" -o "$TMP_CHD/$BASE.iso" >>"$LOG" 2>&1 \
           && [ -f "$TMP_CHD/$BASE.iso" ]; then
            CHD_ISO="$TMP_CHD/$BASE.iso"
            log "extractdvd erfolgreich."
        elif "$CHDMAN" extractcd -i "$CHD_FILE" -o "$TMP_CHD/$BASE.cue" \
                                 -ob "$TMP_CHD/$BASE.bin" >>"$LOG" 2>&1 \
             && [ -f "$TMP_CHD/$BASE.bin" ]; then
            CHD_ISO="$TMP_CHD/$BASE.bin"
            log "extractcd erfolgreich (CUE/BIN)."
        else
            log "FEHLER: chdman konnte die CHD nicht extrahieren."
            echo "FEHLER: CHD-Extraktion fehlgeschlagen. Log: $LOG" >&2
            rm -rf "$TMP_CHD"
            exit 1
        fi
        log "Entpacke die entstandene ISO/BIN ..."
        if ! unpack_image "$CHD_ISO"; then
            log "FEHLER: ISO-Entpacken fehlgeschlagen."
            echo "FEHLER: ISO-Entpacken fehlgeschlagen. Log: $LOG" >&2
            rm -rf "$TMP_CHD"
            exit 1
        fi
        rm -rf "$TMP_CHD"
        log "CHD-Verarbeitung abgeschlossen."
        NEEDS_UNPACK=0
    fi

    if [ "$NEEDS_UNPACK" = "1" ]; then
        IMG=""
        for cand in "$GAMEDIR"/*.iso "$GAMEDIR"/*.ISO \
                    "$GAMEDIR"/*.zip "$GAMEDIR"/*.7z "$GAMEDIR"/*.rar \
                    "$GAMEDIR"/*.tar.* "$SCRIPT_DIR"/*.iso "$SCRIPT_DIR"/*.zip; do
            [ -f "$cand" ] && { IMG="$cand"; break; }
        done
        if [ -z "$IMG" ]; then
            log "FEHLER: Kein Disc-Image und keine CHD gefunden."
            echo "FEHLER: Bitte 'wots2.chd' oder 'wots2.iso' in $GAMEDIR ablegen." >&2
            exit 1
        fi
        log "Disc-Image: $IMG"
        if ! unpack_image "$IMG"; then
            log "FEHLER: Entpacken fehlgeschlagen."
            echo "FEHLER: Entpacken fehlgeschlagen. Log: $LOG" >&2
            exit 1
        fi
    fi

    log "Inhalt von extracted/:"
    ls -la "$EXTRACTED" | head -20 | log_pipe

    if [ ! -f "$EXTRACTED/SLUS_208.93" ] && [ ! -f "$EXTRACTED/slus_208.93" ]; then
        log "FEHLER: SLUS_208.93 fehlt in extracted/."
        echo "FEHLER: SLUS_208.93 fehlt. Log: $LOG" >&2
        find "$EXTRACTED" -maxdepth 2 -type f 2>/dev/null | head -30 | log_pipe
        exit 1
    fi
    log "SLUS_208.93 vorhanden — Entpacken OK."
fi

# ══════════════════════════════════════════════════════════════════════
# SPIELSTART
# ══════════════════════════════════════════════════════════════════════
log_section "SPIELSTART"
log "Starte: ./wots2 extracted"

WOTS2_STDOUT="$GAMEDIR/wots2-stdout.txt"
WOTS2_STDERR="$GAMEDIR/wots2-stderr.txt"
: > "$WOTS2_STDOUT"
: > "$WOTS2_STDERR"

WOTS2_PID=""
GPTOKEYB_PID=""

kill_wots2_escalate() {
    [ -z "$WOTS2_PID" ] && return 0
    if ! kill -0 "$WOTS2_PID" 2>/dev/null; then return 0; fi
    log "sende SIGTERM an wots2 (PID $WOTS2_PID)"
    kill -TERM "$WOTS2_PID" 2>/dev/null || true
    local elapsed=0
    while [ "$elapsed" -lt "$WOTS2_KILL_TIMEOUT" ]; do
        kill -0 "$WOTS2_PID" 2>/dev/null || { log "wots2 sauber beendet."; return 0; }
        sleep 1
        elapsed=$((elapsed + 1))
    done
    log "wots2 reagiert nicht nach ${WOTS2_KILL_TIMEOUT}s — sende SIGKILL"
    kill -KILL "$WOTS2_PID" 2>/dev/null || true
    sleep 1
    return 0
}

HWMON_PID=""
cleanup_all() {
    [ -n "$HWMON_PID" ] && kill "$HWMON_PID" 2>/dev/null || true
    if [ -n "$GPTOKEYB_PID" ] && kill -0 "$GPTOKEYB_PID" 2>/dev/null; then
        kill -TERM "$GPTOKEYB_PID" 2>/dev/null || true
        sleep 0.3
        kill -KILL "$GPTOKEYB_PID" 2>/dev/null || true
    fi
    kill_wots2_escalate
    restore
}

on_signal() {
    log "Signal empfangen — beende."
    kill_wots2_escalate
}

if find_gptokeyb; then
    "$GPTOKEYB_PATH" "./wots2" -k "wots2" >/dev/null 2>&1 &
    GPTOKEYB_PID=$!
    log "gptokeyb gestartet (PID $GPTOKEYB_PID) — Kill-Hotkey Select+Start."
else
    log "gptokeyb nicht gefunden — Kill-Hotkey faellt aus."
fi

trap cleanup_all EXIT
trap on_signal TERM INT HUP

./wots2 extracted > "$WOTS2_STDOUT" 2> "$WOTS2_STDERR" &
WOTS2_PID=$!
log "PID=$WOTS2_PID"

# Hoehere Prioritaet gegenueber Hintergrunddiensten (nur wenn erlaubt, nie fatal).
W2_NICE="${WOTS2_NICE:--5}"
if [ "$W2_NICE" != "0" ]; then
    if [ "$(id -u)" = "0" ]; then
        renice -n "$W2_NICE" -p "$WOTS2_PID" >/dev/null 2>&1 && log "Prioritaet: nice $W2_NICE" || log "renice fehlgeschlagen (ignoriert)"
    elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
        sudo -n renice -n "$W2_NICE" -p "$WOTS2_PID" >/dev/null 2>&1 && log "Prioritaet: nice $W2_NICE (sudo)" || log "renice fehlgeschlagen (ignoriert)"
    else
        log "renice nicht moeglich (kein root/sudo) - uebersprungen."
    fi
fi

# Hardware-Monitor: Takte, GPU-Last, Temperatur alle N Sekunden. Zeigt, ob das Spiel
# CPU- oder GPU-gebunden ist und ob die Hardware drosselt. Fast kostenlos (5 sysfs-Reads).
HWMON_LOG="$GAMEDIR/wots2-hwmon.txt"
if [ "${WOTS2_HWMON:-1}" = "1" ]; then
    : > "$HWMON_LOG"
    (
        t0=$(date +%s)
        rd() { cat "$1" 2>/dev/null || echo "-"; }
        while kill -0 "$WOTS2_PID" 2>/dev/null; do
            now=$(( $(date +%s) - t0 ))
            cpu_khz=$(rd /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq)
            temp=$(rd /sys/class/thermal/thermal_zone0/temp)
            [ "$temp" != "-" ] && temp=$(( temp / 1000 ))
            gpu_hz="-"; gpu_load="-"; dmc_hz="-"
            [ -n "$gpu_devfreq_path" ] && { gpu_hz=$(rd "$gpu_devfreq_path/cur_freq"); gpu_load=$(rd "$gpu_devfreq_path/load"); }
            [ -n "$dmc_devfreq_path" ] && dmc_hz=$(rd "$dmc_devfreq_path/cur_freq")
            printf '%s cpu_khz=%s gpu_hz=%s gpu_load=%s dmc_hz=%s temp_c=%s\n' "$now" "$cpu_khz" "$gpu_hz" "$gpu_load" "$dmc_hz" "$temp"
            sleep "${WOTS2_HWMON_INTERVAL:-10}"
        done
    ) >> "$HWMON_LOG" 2>/dev/null &
    HWMON_PID=$!
    log "Hardware-Monitor: $HWMON_LOG (alle ${WOTS2_HWMON_INTERVAL:-10} s)"
fi

WOTS2_STATUS=0
while true; do
    wait "$WOTS2_PID"
    WOTS2_STATUS=$?
    kill -0 "$WOTS2_PID" 2>/dev/null || break
    log "wait wurde unterbrochen, wots2 laeuft noch — warte erneut."
done

if [ -n "$GPTOKEYB_PID" ] && kill -0 "$GPTOKEYB_PID" 2>/dev/null; then
    kill -TERM "$GPTOKEYB_PID" 2>/dev/null || true
    wait "$GPTOKEYB_PID" 2>/dev/null || true
fi

log "wots2 beendet mit Status $WOTS2_STATUS"

if [ "$WOTS2_STATUS" -gt 128 ]; then
    SIGNAL=$((WOTS2_STATUS - 128))
    case "$SIGNAL" in
        4)  SIGNAME="SIGILL — Illegal Instruction" ;;
        6)  SIGNAME="SIGABRT — Abort" ;;
        7)  SIGNAME="SIGBUS — Bus Error" ;;
        8)  SIGNAME="SIGFPE — Floating-Point Exception" ;;
        9)  SIGNAME="SIGKILL — hart abgeschossen" ;;
        11) SIGNAME="SIGSEGV — Segmentation Fault" ;;
        15) SIGNAME="SIGTERM — regulaer beendet" ;;
        *)  SIGNAME="Signal $SIGNAL" ;;
    esac
    log "wots2 wurde durch $SIGNAME getoetet."
fi

# ── Perf-Trace-Zeilen ins Hauptlog holen ─────────────────────────────
if [ -n "${WOTS2_PERF_TRACE:-}" ] && [ -s "$WOTS2_STDOUT" ]; then
    # Hinweis: grep -c schreibt immer den Zaehler (auch 0) und exitet bei
    # 0 Treffern mit Code 1. Deshalb '|| true', NICHT '|| echo 0' — sonst
    # landet "0\n0" in der Variable und zerlegt die folgende log-Zeile.
    PERF_LINES=$(grep -c '^\[perf\]'    "$WOTS2_STDOUT" 2>/dev/null || true)
    CULL_LINES=$(grep -c '^\[cull\]'    "$WOTS2_STDOUT" 2>/dev/null || true)
    TIMING_LINES=$(grep -c '^\[timing\]'  "$WOTS2_STDOUT" 2>/dev/null || true)
    GTIMING_LINES=$(grep -c '^\[gtiming\]' "$WOTS2_STDOUT" 2>/dev/null || true)
    MTIMING_LINES=$(grep -c '^\[mtiming\]' "$WOTS2_STDOUT" 2>/dev/null || true)
    ATIMING_LINES=$(grep -c '^\[atiming\]' "$WOTS2_STDOUT" 2>/dev/null || true)
    log ""
    log "Diag-Zeilen in wots2-stdout.txt: perf=$PERF_LINES cull=$CULL_LINES timing=$TIMING_LINES gtiming=$GTIMING_LINES mtiming=$MTIMING_LINES atiming=$ATIMING_LINES"
    if [ "$PERF_LINES" -gt 0 ]; then
        log ""
        log "Letzte 20 [perf]-Zeilen:"
        grep '^\[perf\]' "$WOTS2_STDOUT" | tail -20 | log_pipe
    fi
    if [ "$ATIMING_LINES" -gt 0 ]; then
        log ""
        log "Letzte 10 [atiming]-Zeilen:"
        grep '^\[atiming\]' "$WOTS2_STDOUT" | tail -10 | log_pipe
    fi
    if [ "$GTIMING_LINES" -gt 0 ]; then
        log ""
        log "Letzte 10 [gtiming]-Zeilen:"
        grep '^\[gtiming\]' "$WOTS2_STDOUT" | tail -10 | log_pipe
    fi
    if [ "$MTIMING_LINES" -gt 0 ]; then
        log ""
        log "Letzte 10 [mtiming]-Zeilen:"
        grep '^\[mtiming\]' "$WOTS2_STDOUT" | tail -10 | log_pipe
    fi
    if [ "$TIMING_LINES" -gt 0 ]; then
        log ""
        log "Letzte 10 [timing]-Zeilen:"
        grep '^\[timing\]' "$WOTS2_STDOUT" | tail -10 | log_pipe
    fi
    if [ "$CULL_LINES" -gt 0 ]; then
        log ""
        log "Letzte 5 [cull]-Zeilen:"
        grep '^\[cull\]' "$WOTS2_STDOUT" | tail -5 | log_pipe
    fi
fi

if [ -s "$WOTS2_STDOUT" ]; then
    log ""
    log "Auszug aus wots2-stdout.txt (letzte 40 Zeilen):"
    tail -40 "$WOTS2_STDOUT" | log_pipe
else
    log "wots2-stdout.txt ist leer."
fi

if [ -s "$WOTS2_STDERR" ]; then
    log ""
    log "Auszug aus wots2-stderr.txt (letzte 40 Zeilen):"
    tail -40 "$WOTS2_STDERR" | log_pipe
    log ""
    log "Erkannte Fehlermuster:"
    grep -q "shader error" "$WOTS2_STDERR" && log "  - Shader-Kompilierung fehlgeschlagen"
    grep -q "link error" "$WOTS2_STDERR" && log "  - Shader-Link fehlgeschlagen"
    grep -q "no OpenGL 3.3" "$WOTS2_STDERR" && log "  - Kein OpenGL-3.x-Kontext"
    grep -q "not found" "$WOTS2_STDERR" && log "  - Eine Bibliothek wurde nicht gefunden"
    grep -q "Segmentation fault" "$WOTS2_STDERR" && log "  - Segmentation Fault"
    grep -c "" "$WOTS2_STDERR" 2>/dev/null | { read -r n; log "  (stderr hat $n Zeilen insgesamt)"; }
else
    log "wots2-stderr.txt ist leer."
fi

# ── Hardware-Zusammenfassung ─────────────────────────────────────────
if [ -n "$HWMON_PID" ]; then
    kill "$HWMON_PID" 2>/dev/null || true
    wait "$HWMON_PID" 2>/dev/null || true
    HWMON_PID=""
    if [ -s "$HWMON_LOG" ]; then
        log ""
        log "Hardware waehrend des Laufs (aus wots2-hwmon.txt):"
        awk '
            { for (i = 2; i <= NF; i++) { split($i, kv, "="); v[kv[1]] = kv[2];
                if (v[kv[1]] ~ /^[0-9]+(@.*)?$/) { n = v[kv[1]]; sub(/@.*/, "", n); n += 0;
                    if (!(kv[1] in mn) || n < mn[kv[1]]) mn[kv[1]] = n;
                    if (!(kv[1] in mx) || n > mx[kv[1]]) mx[kv[1]] = n; sum[kv[1]] += n; cnt[kv[1]]++ } } }
            END { for (k in mn) printf "  %-9s min=%s  max=%s  mittel=%.0f\n", k, mn[k], mx[k], sum[k] / cnt[k] }
        ' "$HWMON_LOG" 2>/dev/null | sort | log_pipe
        if awk '/cpu_khz=/ { split($2, a, "="); if (a[2] + 0 > 0 && a[2] + 0 < 1000000) low = 1 } END { exit !low }' "$HWMON_LOG" 2>/dev/null; then
            log "  Hinweis: Die CPU lief zeitweise unter 1 GHz - moegliche Drosselung (Temperatur oder Akku)."
        fi
    fi
fi
if [ -s "$WOTS2_STDOUT" ]; then
    GCOUNT_LINES=$(grep -c '^\[gcount\]' "$WOTS2_STDOUT" 2>/dev/null || true)
    if [ "${GCOUNT_LINES:-0}" -gt 0 ]; then
        log ""
        log "Letzte 5 [gcount]-Zeilen (Begin3D-Paare, Schnellpfad, echte 2D-Wechsel):"
        grep '^\[gcount\]' "$WOTS2_STDOUT" | tail -5 | log_pipe
    fi
fi

log_section "ENDE"
sync
exit "$WOTS2_STATUS"
