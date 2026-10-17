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
#   WOTS2_TIMING=0/1                Frame-Timing ins stdout (Default: 0)
#   WOTS2_NO_BLOOM=0/1              Bloom-Pass AUS (Default: 1 = aus)
#   WOTS2_NO_POST=0/1               Komplette Post-Kette AUS (Default: unset)
#   WOTS2_PERSISTENT_BUFFERS        NIEMALS setzen. Auf Mali-G31 kaputt.
#
# ── Zahlenwerte ──────────────────────────────────────────────────────────
#   WOTS2_SHADOW_INTERVAL=N         Shadow-Redraw alle N Frames (Default: 1)
#   WOTS2_NPC_LOD_DIST=N            LOD-2-Schwelle (Default: 4, wirkt nicht)
#   WOTS2_NPC_MAX_DIST=N            Draw-Cull (Kamera-Distanz, Default: 22)
#   WOTS2_NPC_SIM_DIST=N            Sim-Skip (Spieler-Distanz, Default: 20)
#   WOTS2_CHARA_DRAW_SKIP_DIST=N    Draw-Pfad-Skip (Spieler-D., Default: 15)
#   WOTS2_CHARA_SHADOW_SKIP_DIST=N  Shadow-Skip (Spieler-D., Default: 8)
#   WOTS2_LIGHTS_MAX=N              Punktlichter pro Frame (Default: 1)
#   WOTS2_SHADER_LRU=N              Frames bis Shader-Unload (Default: 120)
#   WOTS2_FX_SCALE=N                Effekt-Anzahl (Default: 0.10)
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
    echo "
