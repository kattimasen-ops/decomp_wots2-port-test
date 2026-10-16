#!/bin/bash
# analyze-repo.sh — sammelt alles, was für weitere Optimierungen
#                     nützlich ist, in einem Verzeichnis.
#
# Was rauskommt:
#   00-README.txt               Was in diesem Ordner liegt
#   01-manifest.txt             Alle getrackten Dateien mit Größe/LOC/Mode
#   02-stats.txt                Dateien und LOC pro Endung; Top 30 Dateien
#   03-symbols-all.txt          ctags-Symbole aller Art
#   03b-symbols-functions.txt   Funktionen und Prototypen
#   03c-symbols-types.txt       structs, classes, enums, unions, typedefs
#   04-includes.txt             Include-Graph pro Quelldatei
#   05-hotness.txt              Identifier nach Aufrufhäufigkeit (Top 200)
#   06-bereiche.txt             Dateiliste pro Bereich (engine/game/hal/native)
#   07-sources.tar.gz           Alle Quellen als Tarball
#   08-cmake.txt                Alle CMakeLists.txt komplett
#   09-scripts.txt              Alle scripts/*.sh komplett
#   10-headers-list.txt         Nur die Header-Dateien mit Größe und Zeilen
#
# Verwendung:
#   bash scripts/analyze-repo.sh [Zieldir]
# Zieldir ist Standard "repo-analysis".

set -euo pipefail

OUT="${1:-repo-analysis}"
mkdir -p "$OUT"

log() { printf '[analyze] %s\n' "$*"; }

log "Zieldir: $OUT"

# ── 01 Manifest ─────────────────────────────────────────────────────────
{
    echo "=== Repo-Manifest ==="
    echo "Erstellt: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "Git:      $(git rev-parse --short HEAD 2>/dev/null || echo '?')"
    echo "Branch:   $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
    echo
    printf '%-10s %10s %6s  %s\n' "SIZE" "LOC" "MODE" "PATH"
    git ls-files | while IFS= read -r f; do
        [ -f "$f" ] || continue
        size=$(stat -c%s "$f" 2>/dev/null || echo 0)
        loc=$(wc -l < "$f" 2>/dev/null || echo 0)
        mode=$(stat -c%a "$f" 2>/dev/null || echo '?')
        printf '%-10s %10s %6s  %s\n' "$size" "$loc" "$mode" "$f"
    done
} > "$OUT/01-manifest.txt"
log "01-manifest.txt"

# ── 02 Statistik ───────────────────────────────────────────────────────
{
    echo "=== Repo-Statistik ==="
    echo
    echo "Dateien pro Endung:"
    git ls-files | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -40
    echo
    echo "LOC pro Endung:"
    git ls-files | while IFS= read -r f; do
        [ -f "$f" ] || continue
        ext="${f##*.}"
        loc=$(wc -l < "$f" 2>/dev/null || echo 0)
        echo "$loc $ext"
    done | awk '{s[$2]+=$1} END {for (e in s) print s[e], e}' | sort -rn | head -30
    echo
    echo "Größte Dateien (Top 30):"
    git ls-files | while IFS= read -r f; do
        [ -f "$f" ] || continue
        size=$(stat -c%s "$f" 2>/dev/null || echo 0)
        echo "$size $f"
    done | sort -rn | head -30
} > "$OUT/02-stats.txt"
log "02-stats.txt"

# ── 03 Symbole via ctags ───────────────────────────────────────────────
if command -v ctags >/dev/null 2>&1; then
    git ls-files \
        | grep -E '\.(c|cc|cpp|cxx|h|hpp|hxx)$' \
        > "$OUT/.src-files.txt" || true
    if [ -s "$OUT/.src-files.txt" ]; then
        ctags -R \
              --output-format=u-ctags \
              --fields=+nKSt \
              --extras=+q \
              -L "$OUT/.src-files.txt" \
              -o "$OUT/ctags-raw.txt" 2>/dev/null || true
        rm -f "$OUT/.src-files.txt"

        cp "$OUT/ctags-raw.txt" "$OUT/03-symbols-all.txt"
        awk -F'\t' '$2 == "f" || $2 == "p" { print }' \
            "$OUT/ctags-raw.txt" > "$OUT/03b-symbols-functions.txt" || true
        awk -F'\t' '$2 == "s" || $2 == "c" || $2 == "t" || $2 == "u" || $2 == "g" || $2 == "e" { print }' \
            "$OUT/ctags-raw.txt" > "$OUT/03c-symbols-types.txt" || true
    else
        echo "(keine Quellen gefunden)" > "$OUT/03-symbols-all.txt"
    fi
    log "03*.txt (ctags)"
else
    log "WARNUNG: ctags nicht installiert — Symbole werden übersprungen."
fi

# ── 04 Include-Graph ───────────────────────────────────────────────────
{
    echo "=== Include-Graph (Quelle → Include) ==="
    echo
    git ls-files | grep -E '\.(c|cc|cpp|cxx|h|hpp|hxx)$' | while IFS= read -r f; do
        incs=$(grep -E '^[[:space:]]*#[[:space:]]*include' "$f" 2>/dev/null \
               | sed -E 's/.*[<"]([^>"]+)[>"].*/\1/' \
               | sort -u \
               | tr '\n' ' ')
        [ -n "$incs" ] && echo "$f: $incs"
    done
} > "$OUT/04-includes.txt"
log "04-includes.txt"

# ── 05 Hotness (ein Durchgang, sortiert) ───────────────────────────────
{
    echo "=== Identifier-Aufrufe (Top 200, alle Quellen) ==="
    echo
    git ls-files | grep -E '\.(c|cc|cpp|cxx|h|hpp|hxx)$' \
        | xargs -r grep -hoE '[A-Za-z_][A-Za-z0-9_]*[[:space:]]*\(' 2>/dev/null \
        | sed -E 's/[[:space:]]*\($//' \
        | sort \
        | uniq -c \
        | sort -rn \
        | head -200
} > "$OUT/05-hotness.txt"
log "05-hotness.txt"

# ── 06 Bereiche ────────────────────────────────────────────────────────
{
    echo "=== Dateiliste pro Bereich ==="
    echo
    for dir in src/engine src/game src/hal src/native src/native/hle \
               include/engine include/game include/hal include/native \
               scripts cmake .github/workflows; do
        echo "--- $dir ---"
        if [ -d "$dir" ]; then
            find "$dir" -type f 2>/dev/null | sort
        else
            echo "(nicht vorhanden)"
        fi
        echo
    done
} > "$OUT/06-bereiche.txt"
log "06-bereiche.txt"

# ── 07 Quellen als Tarball ─────────────────────────────────────────────
tar -czf "$OUT/07-sources.tar.gz" \
    $(git ls-files \
      | grep -E '\.(c|cc|cpp|cxx|h|hpp|hxx|cmake|txt|py|sh|yml|yaml|ini|md)$' \
      | grep -vE '^(build|dist|sysroot|sdl2-install|chdman-arm64)/') \
    2>/dev/null || true
log "07-sources.tar.gz"

# ── 08 CMakeLists komplett ─────────────────────────────────────────────
{
    echo "=== Alle CMakeLists.txt und *.cmake ==="
    echo
    git ls-files | grep -E '(CMakeLists\.txt$|\.cmake$)' | while IFS= read -r f; do
        echo "----- $f -----"
        cat "$f"
        echo
    done
} > "$OUT/08-cmake.txt"
log "08-cmake.txt"

# ── 09 Scripts komplett ────────────────────────────────────────────────
{
    echo "=== Alle .sh- und .py-Skripte in scripts/ ==="
    echo
    if [ -d scripts ]; then
        find scripts -maxdepth 1 -type f \( -name '*.sh' -o -name '*.py' \) | sort | while IFS= read -r f; do
            echo "----- $f -----"
            cat "$f"
            echo
        done
    fi
    echo "=== Launcher und Tools im Root ==="
    echo
    for f in WOTS2.sh sdl_mapping.py patch_config_defaults.py patch_config_changes.py; do
        [ -f "$f" ] || continue
        echo "----- $f -----"
        cat "$f"
        echo
    done
} > "$OUT/09-scripts.txt"
log "09-scripts.txt"

# ── 10 Header-Liste ────────────────────────────────────────────────────
{
    echo "=== Header-Dateien (include/**, src/**/*.h) ==="
    echo
    printf '%-10s %10s  %s\n' "SIZE" "LOC" "PATH"
    git ls-files | grep -E '\.(h|hpp|hxx)$' | while IFS= read -r f; do
        size=$(stat -c%s "$f" 2>/dev/null || echo 0)
        loc=$(wc -l < "$f" 2>/dev/null || echo 0)
        printf '%-10s %10s  %s\n' "$size" "$loc" "$f"
    done
} > "$OUT/10-headers-list.txt"
log "10-headers-list.txt"

# ── 00 README ──────────────────────────────────────────────────────────
cat > "$OUT/00-README.txt" <<'EOF'
Repo-Analyse für WOTS2-Optimierungen
=====================================

Dieser Ordner enthält alles, was für weitere Performance-Arbeit an
diesem Port nützlich ist. Er wurde automatisch aus dem Repo erzeugt;
keine Build-Verzeichnisse, keine Binärdateien, keine Git-Objekte.

Inhalt
------
00-README.txt               Diese Datei
01-manifest.txt             Alle getrackten Dateien mit Größe, LOC, Mode
02-stats.txt                Dateien und LOC pro Endung; Top 30 Dateien
03-symbols-all.txt          Alle ctags-Symbole (Rohformat)
03b-symbols-functions.txt   Funktionen und Prototypen
03c-symbols-types.txt       structs, classes, enums, unions, typedefs
04-includes.txt             Include-Graph pro Quelldatei
05-hotness.txt              Identifier nach Aufrufhäufigkeit (Top 200)
06-bereiche.txt             Dateiliste pro Bereich (engine, game, hal, ...)
07-sources.tar.gz           Alle Quellen als Tarball
08-cmake.txt                Alle CMakeLists.txt und *.cmake komplett
09-scripts.txt              Alle launcher-relevanten Skripte komplett
10-headers-list.txt         Header-Dateien mit Größe und LOC

Wie man es liest
----------------
- 01-manifest.txt gibt den Überblick: welche Datei wie groß und wie
  viele Zeilen. Daraus lässt sich ablesen, wo der meiste Code liegt.
- 03b/03c zeigen die tatsächlichen Symbole — daraus lassen sich
  Hotspots ableiten.
- 04-includes.txt zeigt, welche Header überall eingebunden sind —
  Kandidaten für Precompiled Headers oder für das Entfernen von
  transitiven Includes.
- 05-hotness.txt zählt, wie oft welcher Identifier gefolgt von einer
  öffnenden Klammer im gesamten Repo auftaucht. Das ist eine grobe
  aber gute Näherung für „wie heiß ist diese Funktion".
- 07-sources.tar.gz ist das vollständige Quellpaket. Wer den Ordner
  bekommt, kann direkt grep, ctags, clang-tidy, etc. darauf laufen
  lassen.

Format
------
Alle Textdateien sind UTF-8 mit LF-Zeilenenden. Kein BOM.
EOF

log "00-README.txt"
log "Fertig."

echo
echo "=== Inhalt von $OUT ==="
ls -la "$OUT"
echo
echo "=== Größe ==="
du -sh "$OUT"
