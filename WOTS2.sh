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
# ── Zahlenwerte ──────────────────────────────────────────────────────────
#   WOTS2_SHADOW_INTERVAL=N         Shadow-Redraw alle N Frames (Default: 1)
#   WOTS2_NPC_LOD_DIST=N            LOD-2-Schwelle (Default: 4, wirkt nicht)
#   WOTS2_NPC_MAX_DIST=N            Draw-Cull (Kamera-Distanz, Default: 16)
#   WOTS2_NPC_SIM_DIST=N            Sim-Skip (Spieler-Distanz, Default: 15)
#   WOTS2_CHARA_DRAW_SKIP_DIST=N    Draw-Pfad-Skip (Spieler-D., Default: 10)
#   WOTS2_CHARA_SHADOW_SKIP_DIST=N  Shadow-Skip (Spieler-D., Default: 5)
#   WOTS2_SWORD_DRAW_DIST=N         Schwert-Draw-Skip (Kamera-D., Default: 8)
#   WOTS2_LIGHTS_MAX=N              Punktlichter pro Frame (Default: 1)
#   WOTS2_SHADER_LRU=N              Frames bis Shader-Unload (Default: 120)
#   WOTS2_FX_SCALE=N                Effekt-Anzahl (Default: 0.05)
#   WOTS2_SPLASH=N                  Splash-Dauer in Sekunden (Default: 2.5)
#   WOTS2_KILL_TIMEOUT=N            Sekunden bis SIGKILL (Default: 3)
#   WOTS2_LIBDIAG=0/1               LD_DEBUG-Probe (Default: 1)
#
# ── Wichtiger Hinweis zu getenv() ────────────────────────────────────────
# Der Port prüft seine Flags mit getenv(...) != nullptr. Deshalb werden
# alle Bool-Flags mit wots2_export_flag() gesetzt: nur exportieren wenn
# 1, sonst unset.

XDG_DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}

export WOTS2_LIBDIAG="${WOTS2_LIBDIAG:-1}"
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
log "SCRIPT_DIR=$SCRIPT_DIR, GAMEDIR=$GAMEDIR"
log "Kernel=$(uname -r), Arch=$(uname -m)"

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
for candidate in "/opt/system/Tools/PortMaster" "/opt/tools/PortMaster" "$XDG_DATA_HOME/PortMaster" "/roms/ports/PortMaster"; do
    [ -d "$candidate" ] && PM_CONTROLFOLDER="$candidate" && break
done

if [ -n "$PM_CONTROLFOLDER" ] && [ -f "$PM_CONTROLFOLDER/control.txt" ]; then
    source "$PM_CONTROLFOLDER/control.txt" 2>/dev/null || true
    if [ -n "${CFW_NAME:-}" ] && [ -f "$PM_CONTROLFOLDER/mod_${CFW_NAME}.txt" ]; then
        source "$PM_CONTROLFOLDER/mod_${CFW_NAME}.txt" 2>/dev/null || true
    fi
fi

if [ -n "${sdl_controllerconfig:-}" ]; then
    export SDL_GAMECONTROLLERCONFIG="$sdl_controllerconfig"
fi
if [ -n "${SDL_GAMECONTROLLERCONFIG:-}" ]; then
    export SDL_GAMECONTROLLERCONFIG_FILE="/tmp/wots2-gamecontrollerdb.txt"
    printf '%s\n' "$SDL_GAMECONTROLLERCONFIG" > "$SDL_GAMECONTROLLERCONFIG_FILE" 2>/dev/null || true
fi

log_section "SYSTEMOPTIMIERUNG"

cpu_governor_path=""
for candidate in /sys/devices/system/cpu/cpufreq/policy0/scaling_governor /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; do
    [ -w "$candidate" ] && cpu_governor_path="$candidate" && break
done
if [ -n "$cpu_governor_path" ]; then echo performance > "$cpu_governor_path" 2>/dev/null || true; fi
for cpu in /sys/devices/system/cpu/cpu[0-9]*; do
    [ -w "$cpu/cpufreq/scaling_governor" ] && echo performance > "$cpu/cpufreq/scaling_governor" 2>/dev/null || true
done

gpu_devfreq_path=""
for candidate in /sys/class/devfreq/ff400000.gpu /sys/class/devfreq/gpu; do
    [ -d "$candidate" ] && gpu_devfreq_path="$candidate" && break
done
if [ -n "$gpu_devfreq_path" ]; then
    [ -w "$gpu_devfreq_path/governor" ] && echo performance > "$gpu_devfreq_path/governor" 2>/dev/null || true
    if [ -r "$gpu_devfreq_path/available_frequencies" ] && [ -w "$gpu_devfreq_path/min_freq" ]; then
        max_freq=$(tr ' ' '\n' < "$gpu_devfreq_path/available_frequencies" | sort -n | tail -n 1)
        [ -n "$max_freq" ] && echo "$max_freq" > "$gpu_devfreq_path/min_freq" 2>/dev/null || true
    fi
fi

restore() {
    log_section "RESTORE"
    log "Restore abgeschlossen."
}
trap restore EXIT

SYSTEM_MALI=""
for candidate in /usr/lib/aarch64-linux-gnu/libmali-bifrost-g31-rxp0-gbm.so /usr/local/lib/aarch64-linux-gnu/libmali-bifrost-g31-rxp0-gbm.so /usr/lib/aarch64-linux-gnu/libmali.so; do
    [ -f "$candidate" ] && SYSTEM_MALI="$candidate" && break
done
if [ -n "$SYSTEM_MALI" ]; then
    rm -rf /tmp/wots2-mali; mkdir -p /tmp/wots2-mali
    for name in libmali.so.0 libmali.so.1 libmali.so libEGL.so.1 libEGL.so libGLESv2.so.2 libGLESv2.so libGLESv1_CM.so.1 libGLESv1_CM.so; do
        ln -sf "$SYSTEM_MALI" "/tmp/wots2-mali/$name"
    done
    export LD_LIBRARY_PATH="/tmp/wots2-mali:$GAMEDIR/libs.aarch64:$GAMEDIR:/roms/ports/libs:/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}"
else
    export LD_LIBRARY_PATH="$GAMEDIR/libs.aarch64:$GAMEDIR:/roms/ports/libs:/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}"
fi

export SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-kmsdrm}"
unset SDL_AUDIODRIVER
unset AUDIODEV
export WOTS2_DATA_ROOT="$DATA_ROOT"
export WOTS2_SAVE_ROOT="$GAMEDIR/save"

# ── RUNTIME-TUNING (MAX PERF) ────────────────────────────────────────
export WOTS2_NO_VSYNC=1
export WOTS2_BUTTON_REMAP=1
export MALLOC_TRIM_THRESHOLD_=131072
export MALLOC_MMAP_THRESHOLD_=131072
export MALI_AFBC=1
export MALI_MAX_ASYNC_BUFFER_COUNT=4
export MALI_BUFFER_PREALLOC=1
export SDL_AUDIO_SAMPLES="${SDL_AUDIO_SAMPLES:-2048}"

wots2_export_flag WOTS2_NO_CULL   0
wots2_export_flag WOTS2_NO_BATCH  0
wots2_export_flag WOTS2_NO_BUMP   1
wots2_export_flag WOTS2_NO_SHADOW 0
wots2_export_flag WOTS2_NO_MAP_BATCHING 0
wots2_export_flag WOTS2_TRACE_CULL  0
wots2_export_flag WOTS2_PERF_TRACE  1
wots2_export_flag WOTS2_PAD_DIAG    0
wots2_export_flag WOTS2_SHADER_CACHE 1
wots2_export_flag WOTS2_TIMING      1
wots2_export_flag WOTS2_ATIMING     1
wots2_export_flag WOTS2_NO_BLOOM    1
unset WOTS2_PERSISTENT_BUFFERS

# ── DIE KILLER-FLAGS ─────────────────────────────────────────────────
export WOTS2_NO_SKY=1
export WOTS2_NO_WATER=1
export WOTS2_NO_SHIMMER=1

# ── DISTANZEN & WERTE (MAX PERF) ─────────────────────────────────────
export WOTS2_SHADOW_INTERVAL="${WOTS2_SHADOW_INTERVAL:-1}"
export WOTS2_SHADER_LRU="${WOTS2_SHADER_LRU:-120}"
export WOTS2_FX_SCALE="${WOTS2_FX_SCALE:-0.05}"
export WOTS2_SPLASH="${WOTS2_SPLASH:-2.5}"
export WOTS2_NPC_LOD_DIST="${WOTS2_NPC_LOD_DIST:-4}"
export WOTS2_NPC_MAX_DIST="${WOTS2_NPC_MAX_DIST:-16}"
export WOTS2_NPC_SIM_DIST="${WOTS2_NPC_SIM_DIST:-15}"
export WOTS2_CHARA_DRAW_SKIP_DIST="${WOTS2_CHARA_DRAW_SKIP_DIST:-10}"
export WOTS2_CHARA_SHADOW_SKIP_DIST="${WOTS2_CHARA_SHADOW_SKIP_DIST:-5}"
export WOTS2_SWORD_DRAW_DIST="${WOTS2_SWORD_DRAW_DIST:-8}"
export WOTS2_LIGHTS_MAX="${WOTS2_LIGHTS_MAX:-1}"

if [ ! -x ./wots2 ]; then
    echo "FEHLER: ./wots2 fehlt." >&2
    exit 1
fi

log_section "SPIELSTART"

WOTS2_STDOUT="$GAMEDIR/wots2-stdout.txt"
WOTS2_STDERR="$GAMEDIR/wots2-stderr.txt"
: > "$WOTS2_STDOUT"
: > "$WOTS2_STDERR"

WOTS2_PID=""
GPTOKEYB_PID=""

kill_wots2_escalate() {
    [ -z "$WOTS2_PID" ] && return 0
    kill -TERM "$WOTS2_PID" 2>/dev/null || true
    local elapsed=0
    while [ "$elapsed" -lt "$WOTS2_KILL_TIMEOUT" ]; do
        kill -0 "$WOTS2_PID" 2>/dev/null || return 0
        sleep 1
        elapsed=$((elapsed + 1))
    done
    kill -KILL "$WOTS2_PID" 2>/dev/null || true
}

cleanup_all() {
    [ -n "$GPTOKEYB_PID" ] && kill -TERM "$GPTOKEYB_PID" 2>/dev/null || true
    kill_wots2_escalate
    restore
}

trap cleanup_all EXIT
trap "kill_wots2_escalate" TERM INT HUP

if find_gptokeyb; then
    "$GPTOKEYB_PATH" "./wots2" -k "wots2" >/dev/null 2>&1 &
    GPTOKEYB_PID=$!
fi

./wots2 extracted > "$WOTS2_STDOUT" 2> "$WOTS2_STDERR" &
WOTS2_PID=$!

WOTS2_STATUS=0
while true; do
    wait "$WOTS2_PID"
    WOTS2_STATUS=$?
    kill -0 "$WOTS2_PID" 2>/dev/null || break
done

[ -n "$GPTOKEYB_PID" ] && kill -TERM "$GPTOKEYB_PID" 2>/dev/null || true
log "wots2 beendet mit Status $WOTS2_STATUS"

if [ -n "${WOTS2_PERF_TRACE:-}" ] && [ -s "$WOTS2_STDOUT" ]; then
    PERF_LINES=$(grep -c '^\[perf\]' "$WOTS2_STDOUT" 2>/dev/null || true)
    ATIMING_LINES=$(grep -c '^\[atiming\]' "$WOTS2_STDOUT" 2>/dev/null || true)
    GTIMING_LINES=$(grep -c '^\[gtiming\]' "$WOTS2_STDOUT" 2>/dev/null || true)
    log "Diag-Zeilen: perf=$PERF_LINES atiming=$ATIMING_LINES gtiming=$GTIMING_LINES"
    [ "$PERF_LINES" -gt 0 ] && log "Letzte 20 [perf]-Zeilen:" && grep '^\[perf\]' "$WOTS2_STDOUT" | tail -20 | log_pipe
    [ "$ATIMING_LINES" -gt 0 ] && log "Letzte 10 [atiming]-Zeilen:" && grep '^\[atiming\]' "$WOTS2_STDOUT" | tail -10 | log_pipe
    [ "$GTIMING_LINES" -gt 0 ] && log "Letzte 10 [gtiming]-Zeilen:" && grep '^\[gtiming\]' "$WOTS2_STDOUT" | tail -10 | log_pipe
fi

log_section "ENDE"
sync
exit "$WOTS2_STATUS"
