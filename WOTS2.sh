#!/bin/bash
# WOTS2.sh — Way of the Samurai 2 für M9 Pro / RK3326 / ArkOS4Clone
# Basiert auf dem Halo-RK3326-Launcher.

XDG_DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}

# ── PFADE ───────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
[ -z "$SCRIPT_DIR" ] && { echo "FEHLER: SCRIPT_DIR." >&2; exit 1; }
GAMEDIR="$SCRIPT_DIR/wots2"
[ ! -d "$GAMEDIR" ] && { echo "FEHLER: $GAMEDIR fehlt." >&2; exit 1; }
cd "$GAMEDIR" || exit 1

# ── LOGGING ─────────────────────────────────────────────────────────
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

log_section "WOTS2 START"
log "SCRIPT_DIR=$SCRIPT_DIR"
log "GAMEDIR=$GAMEDIR"
log "Kernel=$(uname -r), Arch=$(uname -m)"

# ── LOCK ────────────────────────────────────────────────────────────
exec 9> /tmp/wots2-lock 2>/dev/null || true
if [ -e /proc/self/fd/9 ]; then
    if ! { flock -n 9 || python3 -c 'import fcntl; fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)' 2>/dev/null; } 2>/dev/null; then
        log "WOTS2 laeuft bereits."
        exit 1
    fi
fi

# ── PORTMASTER-CONTROLS ─────────────────────────────────────────────
PM_CONTROLFOLDER=""
for candidate in \
    "/opt/system/Tools/PortMaster" \
    "/opt/tools/PortMaster" \
    "$XDG_DATA_HOME/PortMaster" \
    "/roms/ports/PortMaster"; do
    if [ -d "$candidate" ]; then
        PM_CONTROLFOLDER="$candidate"
        break
    fi
done

if [ -n "$PM_CONTROLFOLDER" ] && [ -f "$PM_CONTROLFOLDER/control.txt" ]; then
    source "$PM_CONTROLFOLDER/control.txt" 2>/dev/null || true
    if [ -n "${CFW_NAME:-}" ] && [ -f "$PM_CONTROLFOLDER/mod_${CFW_NAME}.txt" ]; then
        source "$PM_CONTROLFOLDER/mod_${CFW_NAME}.txt" 2>/dev/null || true
    fi
    if command -v get_controls >/dev/null 2>&1; then
        get_controls 2>/dev/null || true
    fi
    log "PortMaster control.txt geladen aus $PM_CONTROLFOLDER"
fi

# SDL-GameController-Mapping
if [ -n "${sdl_controllerconfig:-}" ]; then
    export SDL_GAMECONTROLLERCONFIG="$sdl_controllerconfig"
    log "SDL_GAMECONTROLLERCONFIG aus PortMaster gesetzt."
elif [ -f "$GAMEDIR/sdl_mapping.py" ]; then
    SDL_MAP="$(cd "$GAMEDIR" && python3 sdl_mapping.py 2>/dev/null)"
    if [ -n "$SDL_MAP" ]; then
        export SDL_GAMECONTROLLERCONFIG="$SDL_MAP"
        log "SDL_GAMECONTROLLERCONFIG aus sdl_mapping.py gesetzt."
    fi
fi

# ── SYSTEMOPTIMIERUNG ───────────────────────────────────────────────
log_section "SYSTEMOPTIMIERUNG"

cpu_governor_path=""
for candidate in \
    /sys/devices/system/cpu/cpufreq/policy0/scaling_governor \
    /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; do
    if [ -w "$candidate" ]; then
        cpu_governor_path="$candidate"
        break
    fi
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
    if [ -d "$candidate" ]; then
        gpu_devfreq_path="$candidate"
        break
    fi
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

if swapon --show 2>/dev/null | grep -q zram; then
    log "ZRAM bereits aktiv."
else
    modprobe zram 2>/dev/null || true
    if [ -e /dev/zram0 ]; then
        echo 512M > /sys/block/zram0/disksize 2>/dev/null || true
        mkswap /dev/zram0 >/dev/null 2>&1 || true
        swapon /dev/zram0 2>/dev/null || true
        log "ZRAM aktiviert."
    fi
fi

WOTS2_SERVICE_STATE="/tmp/wots2-services.$$"
WOTS2_SERVICES_RESTORED=0

stop_service_if_active() {
    service="$1"
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

# ── SAVE-VERZEICHNISSE ──────────────────────────────────────────────
mkdir -p "$GAMEDIR/wots2_card" \
         "$GAMEDIR/save" \
         "$GAMEDIR/screenshots" 2>/dev/null || true

# ── DRI-RECHTE ──────────────────────────────────────────────────────
for node in /dev/dri/card0 /dev/dri/renderD128 /dev/fb0; do
    if [ -e "$node" ] && { [ ! -r "$node" ] || [ ! -w "$node" ]; }; then
        sudo -n chmod 666 "$node" 2>/dev/null || true
    fi
done

# ── MALI-SYMLINKS ───────────────────────────────────────────────────
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
    if [ -f "$candidate" ]; then
        SYSTEM_MALI="$candidate"
        break
    fi
done

if [ -n "$SYSTEM_MALI" ] && [ -f "$SYSTEM_MALI" ]; then
    rm -rf /tmp/wots2-mali
    mkdir -p /tmp/wots2-mali
    for name in libmali.so.0 libmali.so.1 libmali.so libgbm.so.1 libgbm.so.1.0.0 libgbm.so libEGL.so.1 libEGL.so libGLESv2.so.2 libGLESv2.so libGLESv1_CM.so.1 libGLESv1_CM.so; do
        ln -sf "$SYSTEM_MALI" "/tmp/wots2-mali/$name"
    done
    export LD_LIBRARY_PATH="/tmp/wots2-mali:$GAMEDIR/libs.aarch64:$GAMEDIR:/roms/ports/libs:/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}"
    log "Mali-Symlinks aus $SYSTEM_MALI erstellt."
else
    log "WARNUNG: Kein Mali-Blob gefunden — nutze System-Libraries."
    export LD_LIBRARY_PATH="$GAMEDIR/libs.aarch64:$GAMEDIR:/roms/ports/libs:/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}"
fi

# ── ALSA aufräumen ──────────────────────────────────────────────────
ASOUNDRC="$HOME/.asoundrc"
if [ -f "$ASOUNDRC" ]; then
    WOTS2_ASOUNDRC_EXPECTED="$(printf 'pcm.!default { type hw; card 0; device 0 }\nctl.!default { type hw; card 0 }\n')"
    if [ "$(cat "$ASOUNDRC" 2>/dev/null)" = "$WOTS2_ASOUNDRC_EXPECTED" ]; then
        mv -f "$ASOUNDRC" "$ASOUNDRC.wots2-backup" 2>/dev/null || rm -f "$ASOUNDRC" 2>/dev/null || true
        log "Alte .asoundrc gesichert."
    fi
fi

# ── SDL-UMGEBUNG ────────────────────────────────────────────────────
export SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-kmsdrm}"
unset SDL_AUDIODRIVER
unset AUDIODEV

# ── WOTS2-PFADE ─────────────────────────────────────────────────────
export WOTS2_DATA_ROOT="$GAMEDIR"
export WOTS2_SAVE_ROOT="$GAMEDIR/save"

# ── RUNTIME-TUNING ──────────────────────────────────────────────────
export WOTS2_NO_VSYNC=1
export WOTS2_BUTTON_REMAP=1

# Glibc-Allocator (1 GB RAM)
export MALLOC_TRIM_THRESHOLD_=131072
export MALLOC_MMAP_THRESHOLD_=131072

# Mali-G31 DDK
export MALI_MAX_ASYNC_BUFFER_COUNT=2
export MALI_BUFFER_PREALLOC=1

# ── BINARY-CHECK ────────────────────────────────────────────────────
if [ ! -x ./wots2 ]; then
    log "FEHLER: ./wots2 fehlt oder nicht ausfuehrbar."
    echo "FEHLER: ./wots2 fehlt." >&2
    exit 1
fi

# ── ERSTSTART: DISC-IMAGE ENTPACKEN ─────────────────────────────────
EXTRACTED="$GAMEDIR/extracted"
if [ ! -d "$EXTRACTED" ] || [ -z "$(ls -A "$EXTRACTED" 2>/dev/null)" ]; then
    log "Erststart: $EXTRACTED ist leer — suche Disc-Image."
    IMG=""
    for cand in "$GAMEDIR"/*.iso "$GAMEDIR"/*.ISO \
                "$GAMEDIR"/*.zip "$GAMEDIR"/*.7z "$GAMEDIR"/*.rar "$GAMEDIR"/*.tar.*; do
        [ -f "$cand" ] && { IMG="$cand"; break; }
    done
    if [ -z "$IMG" ]; then
        log "FEHLER: Kein Disc-Image gefunden. Bitte SLUS-208.93 ablegen."
        echo "FEHLER: Kein Disc-Image gefunden (SLUS-208.93)." >&2
        exit 1
    fi
    log "Entpacke $IMG ..."
    mkdir -p "$EXTRACTED"
    case "$IMG" in
        *.iso|*.ISO)
            python3 - "$IMG" "$EXTRACTED" <<'PYEOF'
import sys, os
# Minimaler ISO-9660-Extraktor – ersetzt 7z/bsdtar falls nicht vorhanden
src, dst = sys.argv[1], sys.argv[2]
print("ISO:", src, "->", dst)
# Fallback: bsdtar falls vorhanden
os.system('bsdtar -xf "%s" -C "%s" 2>/dev/null || 7z x -y -o"%s" "%s" >/dev/null' % (src, dst, dst, src))
PYEOF
            ;;
        *.zip)    unzip -o "$IMG" -d "$EXTRACTED" >/dev/null 2>&1 || true ;;
        *.7z)     7z x -y -o"$EXTRACTED" "$IMG" >/dev/null 2>&1 || true ;;
        *.rar)    unrar x -o+ "$IMG" "$EXTRACTED/" >/dev/null 2>&1 || true ;;
        *.tar.*)  tar -xf "$IMG" -C "$EXTRACTED" >/dev/null 2>&1 || true ;;
    esac
fi

# ── START ───────────────────────────────────────────────────────────
log_section "SPIELSTART"
log "Starte: ./wots2"

WOTS2_STDOUT="$GAMEDIR/wots2-stdout.txt"
WOTS2_STDERR="$GAMEDIR/wots2-stderr.txt"
: > "$WOTS2_STDOUT"
: > "$WOTS2_STDERR"

GPTOKEYB_PID=""
if [ -n "$PM_CONTROLFOLDER" ] && command -v gptokeyb >/dev/null 2>&1; then
    gptokeyb "./wots2" >/dev/null 2>&1 &
    GPTOKEYB_PID=$!
fi
cleanup_all() {
    [ -n "$GPTOKEYB_PID" ] && kill -0 "$GPTOKEYB_PID" 2>/dev/null && \
        kill -TERM "$GPTOKEYB_PID" 2>/dev/null || true
    restore
}
trap cleanup_all EXIT

./wots2 > "$WOTS2_STDOUT" 2> "$WOTS2_STDERR" &
WOTS2_PID=$!
forward_signal() {
    [ -n "$WOTS2_PID" ] && kill -0 "$WOTS2_PID" 2>/dev/null && \
        kill -TERM "$WOTS2_PID" 2>/dev/null || true
}
trap forward_signal TERM INT HUP

wait "$WOTS2_PID"
WOTS2_STATUS=$?

log "wots2 beendet mit Status $WOTS2_STATUS"
log_section "ENDE"
sync
exit "$WOTS2_STATUS"
