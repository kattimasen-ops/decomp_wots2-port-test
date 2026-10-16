#!/bin/bash
# WOTS2.sh — Way of the Samurai 2 für M9 Pro / RK3326 / ArkOS4Clone
#
# RK3326-Port: St0len-One
# Target:      Rockchip RK3326 / Cortex-A35 / Mali-G31 MP2
#
# Erststart: sucht wots2.chd, wots2.iso oder ein anderes Disc-Image und
#            legt die Spieldateien nach wots2/extracted/.
#
# CHD-Support: chdman (ARM64) liegt neben der wots2-Binary und wird zum
#              Extrahieren von .chd-Dateien genutzt. Die entstandene ISO
#              wird im selben Lauf entpackt; die ISO bleibt nicht liegen.
#
# Killswitch:
#   gptokeyb wird mit SDL_GAMECONTROLLERCONFIG_FILE gestartet. Der
#   Standard-Hotkey (Select+Start) beendet wots2 sauber. Wenn wots2
#   auf SIGTERM nicht reagiert, eskaliert der Launcher nach 3 Sekunden
#   auf SIGKILL. Der Launcher sucht gptokeyb in PATH sowie in den auf
#   ArkOS4Clone ueblichen Pfaden.
#
# AUDIO-HINWEIS (Stand jetzt):
#   Unser SDL2-Bundle wurde ohne ALSA gebaut (FindALSA hat bei
#   Cross-Compiles libasound nicht gefunden). Der Port laeuft daher
#   stumm, bis scripts/ci-build-sdl2.sh um -DALSA_LIBRARY=...
#   -DALSA_INCLUDE_DIR=... erweitert und neu gebaut wurde.
#   Der Launcher erzwingt SDL_AUDIODRIVER nicht, damit SDL sich
#   selbst einen verfuegbaren Treiber sucht statt abzustuerzen.
#
# Steuerung:
#   WOTS2_LIBDIAG=0/1       LD_DEBUG-Probe (Default: 1)
#   WOTS2_FX_SCALE=N        Effekt-Anzahl (Default: 0.6)
#   WOTS2_NO_CULL=0/1       Frustum-Culling aus (Default: 0)
#   WOTS2_NO_BATCH=0/1      2D-Batching aus (Default: 0)
#   WOTS2_SHADER_CACHE=0/1  Shader-Cache (Default: 1)
#   WOTS2_SHADER_LRU=N      Frames bis Shader-Unload (Default: 120)
#   WOTS2_SPLASH=N          Splash-Dauer in Sekunden (Default: 2.5)
#   WOTS2_KILL_TIMEOUT=N    Sekunden bis SIGKILL (Default: 3)

XDG_DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}

export WOTS2_LIBDIAG="${WOTS2_LIBDIAG:-1}"
WOTS2_KILL_TIMEOUT="${WOTS2_KILL_TIMEOUT:-3}"

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

if [ -n "${sdl_controllerconfig:-}" ]; then
    export SDL_GAMECONTROLLERCONFIG="$sdl_controllerconfig"
    log "SDL_GAMECONTROLLERCONFIG aus PortMaster gesetzt."
elif [ -f "$GAMEDIR/sdl_mapping.py" ]; then
    SDL_MAP="$(cd "$GAMEDIR" && python3 sdl_mapping.py 2>/dev/null)"
    [ -n "$SDL_MAP" ] && export SDL_GAMECONTROLLERCONFIG="$SDL_MAP" && \
        log "SDL_GAMECONTROLLERCONFIG aus sdl_mapping.py gesetzt."
fi

# gptokeyb braucht eine DATEI, nicht nur die Env-Variable
if [ -n "${SDL_GAMECONTROLLERCONFIG:-}" ]; then
    export SDL_GAMECONTROLLERCONFIG_FILE="/tmp/wots2-gamecontrollerdb.txt"
    printf '%s\n' "$SDL_GAMECONTROLLERCONFIG" > "$SDL_GAMECONTROLLERCONFIG_FILE" 2>/dev/null || true
    log "SDL_GAMECONTROLLERCONFIG_FILE gesetzt: $SDL_GAMECONTROLLERCONFIG_FILE"
else
    log "WARNUNG: keine SDL_GAMECONTROLLERCONFIG — gptokeyb Kill-Hotkey evtl. inaktiv."
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
else
    log "CPU-Governor: kein Pfad gefunden"
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
else
    log "GPU-Governor: kein Devfreq-Pfad gefunden"
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
# libgbm wird NICHT auf die Mali-Blob gelegt. Die Mali-Blob ruft selbst
# gbm_bo_get_modifier aus der echten System-libgbm; ein Symlink auf die
# Blob wuerde dieses Symbol nicht aufloesen und beim ersten GBM-Aufruf
# "undefined symbol: gbm_bo_get_modifier" werfen.
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
# AUDIODRIVER NICHT erzwingen: unser SDL2-Bundle hat kein ALSA drin
# (FindALSA findet die Lib bei Cross-Compiles nicht); SDL waehlt dann
# selbst den naechsten verfuegbaren Treiber oder laeuft stumm statt
# abzustuerzen.
unset SDL_AUDIODRIVER
unset AUDIODEV

# ── WOTS2-PFADE ──────────────────────────────────────────────────────
export WOTS2_DATA_ROOT="$DATA_ROOT"
export WOTS2_SAVE_ROOT="$GAMEDIR/save"

# ── RUNTIME-TUNING ───────────────────────────────────────────────────
export WOTS2_NO_VSYNC=1
export WOTS2_BUTTON_REMAP=1

export MALLOC_TRIM_THRESHOLD_=131072
export MALLOC_MMAP_THRESHOLD_=131072

export MALI_AFBC=1
export MALI_MAX_ASYNC_BUFFER_COUNT=2
export MALI_BUFFER_PREALLOC=1

export WOTS2_SHADER_CACHE="${WOTS2_SHADER_CACHE:-1}"
export WOTS2_SHADER_LRU="${WOTS2_SHADER_LRU:-120}"

export WOTS2_NO_BATCH="${WOTS2_NO_BATCH:-0}"

export SDL_AUDIO_SAMPLES="${SDL_AUDIO_SAMPLES:-2048}"

export WOTS2_FX_SCALE="${WOTS2_FX_SCALE:-0.6}"

export WOTS2_SPLASH="${WOTS2_SPLASH:-2.5}"

# Frustum-Culling laeuft mit korrigierter NEON-Version (wots2-neon.py v3).
# Notausgang bei Bedarf: WOTS2_NO_CULL=1 in der Umgebung setzen.
export WOTS2_NO_CULL="${WOTS2_NO_CULL:-0}"

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
log "  WOTS2_SHADER_CACHE=$WOTS2_SHADER_CACHE"
log "  WOTS2_SHADER_LRU=$WOTS2_SHADER_LRU"
log "  WOTS2_NO_BATCH=$WOTS2_NO_BATCH"
log "  WOTS2_NO_CULL=$WOTS2_NO_CULL"
log "  WOTS2_FX_SCALE=$WOTS2_FX_SCALE"
log "  WOTS2_SPLASH=$WOTS2_SPLASH"
log "  SDL_AUDIO_SAMPLES=$SDL_AUDIO_SAMPLES"

log ""
log "Bundle-Bibliotheken (libs.aarch64):"
if [ -d "$GAMEDIR/libs.aarch64" ]; then
    ls -la "$GAMEDIR/libs.aarch64" 2>&1 | log_pipe
    if [ -e "$GAMEDIR/libs.aarch64/libSDL2-2.0.so.0" ]; then
        log "  OK: libSDL2-2.0.so.0 im Bundle — System-SDL2 wird umgangen."
    else
        log "  WARNUNG: libSDL2-2.0.so.0 fehlt in libs.aarch64!"
        log "  Es wird die System-SDL2 geladen; der KMSDRM-Pageflip-Patch greift dann NICHT."
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
    log "  Der Launcher beendet wots2 trotzdem sauber bei SIGTERM/SIGINT."
fi

# ── LD_DEBUG=libs Probe ──────────────────────────────────────────────
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
        bsdtar)
            bsdtar -xf "$img" -C "$tmp" 2>>"$LOG" || return 1
            ;;
        7z|7za)
            7z x -y -o"$tmp" "$img" >>"$LOG" 2>&1 || return 1
            ;;
        unzip)
            unzip -o "$img" -d "$tmp" >>"$LOG" 2>&1 || return 1
            ;;
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
    if ! kill -0 "$WOTS2_PID" 2>/dev/null; then
        return 0
    fi
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
    "$GPTOKEYB_PATH" "./wots2" >/dev/null 2>&1 &
    GPTOKEYB_PID=$!
    log "gptokeyb gestartet (PID $GPTOKEYB_PID) — Kill-Hotkey Select+Start."
else
    log "gptokeyb nicht gefunden — Kill-Hotkey faellt aus."
    log "Der Launcher beendet wots2 trotzdem sauber bei SIGTERM/SIGINT."
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
        4)  SIGNAME="SIGILL — Illegal Instruction (auf Cortex-A35 oft eine LSE-Atomic oder falsche CPU-Flags)" ;;
        6)  SIGNAME="SIGABRT — Abort (meist eine fehlgeschlagene Zusicherung)" ;;
        7)  SIGNAME="SIGBUS — Bus Error (meist ein Speicherzugriff auf eine ungueltige Adresse)" ;;
        8)  SIGNAME="SIGFPE — Floating-Point Exception" ;;
        9)  SIGNAME="SIGKILL — hart abgeschossen (Launcher-Eskalation oder OOM-Killer)" ;;
        11) SIGNAME="SIGSEGV — Segmentation Fault (Null-Dereferenz oder Stack-Ueberlauf)" ;;
        15) SIGNAME="SIGTERM — regulaer beendet" ;;
        *)  SIGNAME="Signal $SIGNAL" ;;
    esac
    log "wots2 wurde durch $SIGNAME getoetet."
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
    log "Erkannte Fehlermuster in wots2-stderr.txt:"
    if grep -q "shader error" "$WOTS2_STDERR"; then
        log "  - Shader-Kompilierung fehlgeschlagen: siehe [GS] shader error"
    fi
    if grep -q "link error" "$WOTS2_STDERR"; then
        log "  - Shader-Link fehlgeschlagen: siehe [GS] link error"
    fi
    if grep -q "no OpenGL 3.3" "$WOTS2_STDERR"; then
        log "  - Kein OpenGL-3.x-Kontext — Mali-Blob oder EGL-Config stimmt nicht"
    fi
    if grep -q "not found" "$WOTS2_STDERR"; then
        log "  - Eine Bibliothek wurde nicht gefunden"
    fi
    if grep -q "SDL_CreateWindow" "$WOTS2_STDERR"; then
        log "  - SDL_CreateWindow ist gescheitert — evtl. KMSDRM-Problem"
    fi
    if grep -q "GLIBCXX" "$WOTS2_STDERR"; then
        log "  - GLIBCXX-Version zu alt — sollte durch -static-libstdc++ nicht passieren"
    fi
    if grep -q "Segmentation fault" "$WOTS2_STDERR"; then
        log "  - Segmentation Fault"
    fi
    grep -c "" "$WOTS2_STDERR" 2>/dev/null | {
        read -r n; log "  (stderr hat $n Zeilen insgesamt)"
    }
else
    log "wots2-stderr.txt ist leer."
fi

log_section "ENDE"
sync
exit "$WOTS2_STATUS"
