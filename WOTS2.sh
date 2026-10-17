#!/bin/bash
# WOTS2.sh — Way of the Samurai 2 für M9 Pro / RK3326 / ArkOS4Clone
#
# RK3326-Port: St0len-One
# Target:      Rockchip RK3326 / Cortex-A35 / Mali-G31 MP2
#
# Killswitch:
#   gptokeyb wird mit "-k wots2" gestartet. Der Standard-Hotkey
#   (Select+Start) beendet wots2 sauber.

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

# ── SDL-GAMECONTROLLER ───────────────────────────────────────────────
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

saved=/tmp/wots2-clocks
printf '%s|%s|%s\n' "$cpu_saved" "$gpu_gov_saved" "$gpu_min_saved" > "$saved" 2>/dev/null || true

restore() {
    log_section "RESTORE"
    if [ -f "$saved" ]; then
        IFS='|' read -r cpu_gov gpu_gov gpu_min < "$saved"
        [ -n "$cpu_gov" ] && [ -n "$cpu_governor_path" ] && [ -w "$cpu_governor_path" ] && \
            echo "$cpu_gov" > "$cpu_governor_path" 2>/dev/null || true
        if [ -n "$gpu_devfreq_path" ]; then
            [ -n "$gpu_gov" ] && [ -w "$gpu_devfreq_path/governor" ] && \
                echo "$gpu_gov" > "$gpu_devfreq_path/governor" 2>/dev/null || true
            [ -n "$gpu_min" ] && [ -w "$gpu_devfreq_path/min_freq" ] && \
                echo "$gpu_min" > "$gpu_devfreq_path/min_freq" 2>/dev/null || true
        fi
        rm -f "$saved"
    fi
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

# ── RUNTIME-TUNING (MAX PERF) ────────────────────────────────────────
export WOTS2_NO_VSYNC=1
export WOTS2_BUTTON_REMAP=1

export MALLOC_TRIM_THRESHOLD_=131072
export MALLOC_MMAP_THRESHOLD_=131072

export MALI_AFBC=1
export MALI_MAX_ASYNC_BUFFER_COUNT=4
export MALI_BUFFER_PREALLOC=1

export SDL_AUDIO_SAMPLES="${SDL_AUDIO_SAMPLES:-2048}"

# ── WOTS2-Flags: NUR exportieren wenn 1, sonst unset ─────────────────────
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

# ══════════════════════════════════════════════════════════════════════
# DIE KILLER-FLAGS (Rendering-Optimierung)
# ══════════════════════════════════════════════════════════════════════
# Himmel, Wasser und Hitzeflimmern generieren massig Draw-Calls und 
# Polygone. Auf dem RK3326 deaktiviert für stabile Frameraten.
export WOTS2_NO_SKY=1
export WOTS2_NO_WATER=1
export WOTS2_NO_SHIMMER=1

# ── WOTS2-Zahlenwerte: MAX-PERFORMANCE-PRESET ───────────────────────────
# Distanz-Baender (Kamera ~3.5u hinter Spieler):
#   gezeichnet (MAX_DIST=16):        0 .. 12u Spieler-Distanz
#   voll animiert (DRAW_SKIP=10):    0 ..  9u
#   simuliert (SIM_DIST=15):         0 .. 14u
#   Schwert gezeichnet (SWORD_DRAW=8): 0 .. 8u Kamera-Distanz
export WOTS2_SHADOW_INTERVAL="${WOTS2_SHADOW_INTERVAL:-1}"
export WOTS2_SHADER_LRU="${WOTS2_SHADER_LRU:-120}"
export WOTS2_FX_SCALE="${WOTS2_FX_SCALE:-0.05}" # Halbiert die Partikel-Menge!
export WOTS2_SPLASH="${WOTS2_SPLASH:-2.5}"
export WOTS2_NPC_LOD_DIST="${WOTS2_NPC_LOD_DIST:-4}"
export WOTS2_NPC_MAX_DIST="${WOTS2_NPC_MAX_DIST:-16}"
export WOTS2_NPC_SIM_DIST="${WOTS2_NPC_SIM_DIST:-15}"
export WOTS2_CHARA_DRAW_SKIP_DIST="${WOTS2_CHARA_DRAW_SKIP_DIST:-10}"
export WOTS2_CHARA_SHADOW_SKIP_DIST="${WOTS2_CHARA_SHADOW_SKIP_DIST:-5}"
export WOTS2_SWORD_DRAW_DIST="${WOTS2_SWORD_DRAW_DIST:-8}"
export WOTS2_LIGHTS_MAX="${WOTS2_LIGHTS_MAX:-1}"

# ── BINARY-CHECK ─────────────────────────────────────────────────────
if [ ! -x ./wots2 ]; then
    log "FEHLER: ./wots2 fehlt oder nicht ausfuehrbar."
    echo "FEHLER: ./wots2 fehlt." >&2
    exit 1
fi

# ══════════════════════════════════════════════════════════════════════
# SPIELDATEN ENTPACKEN (Übersprungen, da bereits entpackt)
# ══════════════════════════════════════════════════════════════════════
log_section "SPIELDATEN ENTPACKEN"

if [ -f "$EXTRACTED/SLUS_208.93" ] || [ -f "$EXTRACTED/slus_208.93" ]; then
    log "extracted/ enthaelt bereits SLUS_208.93 — ueberspringe Entpacken."
else
    log "FEHLER: SLUS_208.93 fehlt in extracted/."
    exit 1
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

cleanup_all() {
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

log_section "ENDE"
sync
exit "$WOTS2_STATUS"
