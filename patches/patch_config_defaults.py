#!/usr/bin/env python3
"""
Setzt die Default-Werte in port_config.c auf RK3326-Optimum.

Diese Version ist auf die WOTS2-Optionen angepasst. Die Kernwerte
entsprechen dem "Recommended"-Preset aus der README.
"""
import os
import re
import sys


CHANGES = [
    # ── Video ────────────────────────────────────────────────────────
    ("video.height",     "448",  "336"),
    ("video.aspect",     "1.7778", "1.3333"),
    ("video.fps",        "60",   "30"),
    ("video.vsync",      "false", "true"),
    ("video.fullscreen", "false", "true"),
    # ── Lighting ────────────────────────────────────────────────────
    ("lighting.shadows",         "true",  "false"),
    ("lighting.ao",              "true",  "false"),
    ("lighting.god_rays",        "0.4",   "0.0"),
    ("lighting.dust",            "0.5",   "0.0"),
    ("lighting.bloom",           "0.3",   "0.15"),
    ("lighting.bloom_threshold", "0.7",   "0.85"),
    ("lighting.grade",           "true",  "false"),
    ("lighting.lanterns",        "true",  "true"),
    ("lighting.lantern_shadows", "true",  "false"),
    # ── Fog ─────────────────────────────────────────────────────────
    ("fog.far_scale",            "1.0",   "0.85"),
]


def apply_patch(src_root):
    print("== Patch: port_config.c Defaults ==")
    path = os.path.join(src_root, "port", "linux", "src", "port_config.c")
    if not os.path.exists(path):
        print("WARNUNG: %s nicht gefunden." % path)
        return
    with open(path) as f:
        text = f.read()

    changed = already = missing = 0
    for name, old, new in CHANGES:
        pat = re.compile(
            r'(\{\s*"' + re.escape(name) + r'"\s*,\s*_config_\w+\s*,\s*")'
            + re.escape(old) + r'(")')
        if pat.search(text):
            text = pat.sub(r'\g<1>' + new + r'\g<2>', text, count=1)
            print("  %s: %s -> %s" % (name, old, new))
            changed += 1
            continue
        if re.search(r'\{\s*"' + re.escape(name) + r'"\s*,\s*_config_\w+\s*,\s*"'
                     + re.escape(new) + r'"', text):
            print("  %s: schon %s." % (name, new))
            already += 1
            continue
        if re.search(r'\{\s*"' + re.escape(name) + r'"\s*,\s*_config_\w+\s*,', text):
            text = re.sub(
                r'(\{\s*"' + re.escape(name) + r'"\s*,\s*_config_\w+\s*,\s*")[^"]*(")',
                r'\g<1>' + new + r'\g<2>', text, count=1)
            print("  %s: unbekannter Default -> %s" % (name, new))
            changed += 1
        else:
            print("  HINWEIS: %s nicht vorhanden." % name)
            missing += 1

    with open(path, "w") as f:
        f.write(text)
    print("  %d geaendert, %d schon korrekt, %d fehlend." % (changed, already, missing))


if __name__ == "__main__":
    apply_patch(sys.argv[1] if len(sys.argv) > 1 else ".")
