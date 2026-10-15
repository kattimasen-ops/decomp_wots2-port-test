#!/usr/bin/env python3
"""
patch_config_defaults.py — setzt die Default-Werte in
include/native/port_options.h auf das "Recommended"-Preset für den
RK3326 (M9 Pro).

Hintergrund:
  Der Port liest port.ini zur Laufzeit (port_options.cpp). Fehlt die
  Datei, greifen die Default-Member-Initializer aus dem Options-Struct
  in include/native/port_options.h. Diese Datei wird hier auf die Werte
  des "Recommended"-Presets umgestellt — damit der Port auch ohne
  port.ini vernünftig läuft (Vollbild, 336 Zeilen, Bloom, Laternen).

Idempotent: erkennt den Ziel-Wert und überspringt.
Zielt ausdrücklich NICHT auf port/linux/src/port_config.c — diese
Datei existiert in diesem Repo nicht (das war der Knulli-Port).

Python 3.6+ kompatibel.
"""
import os
import re
import sys


# Datei, in der die Defaults stehen.
TARGET = os.path.join("include", "native", "port_options.h")

# (Feldname, erwarteter Default, neuer Default)
# Erwartung ist Absicht: wenn der Wert schon ein anderer ist, überspringt
# das Skript und meldet — kein blindes Überschreiben.
CHANGES = [
    # ── Video ────────────────────────────────────────────────────────
    ("aspect",         "0.0f",   "1.3333f"),
    ("height",         "448",    "336"),
    ("fps",            "0",      "30"),
    ("fullscreen",     "false",  "true"),
    # ── Lighting ────────────────────────────────────────────────────
    ("bloom",          "0.0f",   "0.15f"),
    ("bloom_threshold","0.78f",  "0.85f"),
    ("lanterns",       "false",  "true"),
    # ── Fog ─────────────────────────────────────────────────────────
    ("fog_far_scale",  "1.0f",   "0.85f"),
]


# Zeilen wie:    int   height = 448;
#                float aspect = 0.0f;
#                bool  fullscreen = false;
LINE = re.compile(
    r'^(?P<indent>\s*)(?P<type>int|float|bool)\s+(?P<name>\w+)\s*=\s*'
    r'(?P<value>[^;]+?)\s*;\s*(?P<rest>//.*)?$'
)


def patch_header(src_root):
    path = os.path.join(src_root, TARGET)
    if not os.path.exists(path):
        print("WARNUNG: %s nicht gefunden — ueberspringe." % path)
        return 0, 0, 0

    with open(path) as f:
        lines = f.read().split("\n")

    changed = already = missing = 0

    wanted = {name: (old, new) for name, old, new in CHANGES}
    seen = set()

    for i, line in enumerate(lines):
        m = LINE.match(line)
        if not m:
            continue
        name = m.group("name")
        if name not in wanted:
            continue
        seen.add(name)
        old_expected, new = wanted[name]
        cur = m.group("value")
        if cur == new:
            print("  %-18s schon %s" % (name, new))
            already += 1
            continue
        if cur != old_expected:
            print("  %-18s unerwartet: %r (erwartet %r -> %r) — unangetastet"
                  % (name, cur, old_expected, new))
            missing += 1
            continue
        # Ersetze nur den Wert, erhalte Einrückung, Typ, Abstand und Kommentar.
        new_line = "%s%s %s = %s;%s" % (
            m.group("indent"), m.group("type"), name, new,
            (" " + m.group("rest")) if m.group("rest") else "")
        lines[i] = new_line
        print("  %-18s %s -> %s" % (name, cur, new))
        changed += 1

    for name in wanted:
        if name not in seen:
            print("  HINWEIS: Feld %r nicht gefunden." % name)
            missing += 1

    if changed:
        with open(path, "w") as f:
            f.write("\n".join(lines))

    print("port_options.h: %d geaendert, %d schon korrekt, %d nicht gefunden."
          % (changed, already, missing))
    return changed, already, missing


def apply_patch(src_root):
    print("== Patch: Default-Werte in port_options.h ==")
    patch_header(src_root)
    print("== Fertig.")


if __name__ == "__main__":
    apply_patch(sys.argv[1] if len(sys.argv) > 1 else ".")
