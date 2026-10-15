#!/usr/bin/env python3
"""Liest die ArkOS4Clone-Controller-Konfiguration und gibt einen
SDL_GAMECONTROLLERCONFIG-String aus.

Aufruf: python3 sdl_mapping.py
Ausgabe: "<guid>,<name>,a:b0,b:b1,..."
"""
import os
import re
import glob
import sys


ES_CONFIG_PATHS = [
    "/etc/emulationstation/es_input.cfg",
    os.path.expanduser("~/.emulationstation/es_input.cfg"),
    "/home/ark/.emulationstation/es_input.cfg",
    "/roms/tools/PortMaster/gamecontrollerdb.txt",
    "/usr/share/gamecontrollerdb.txt",
]


def read_es_config():
    for path in ES_CONFIG_PATHS:
        if os.path.isfile(path):
            try:
                with open(path, "r", errors="ignore") as f:
                    return f.read()
            except OSError:
                continue
    return ""


def parse_input_config(xml):
    """Sehr einfacher Parser – ES schreibt <inputConfig ... />."""
    m = re.search(r'<inputConfig[^>]*/>', xml)
    if not m:
        return None
    attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(0)))
    return attrs


def build_gc_string(attrs):
    # SDL-Reihenfolge (Xbox-Layout)
    mapping = [
        ("a", "a"), ("b", "b"), ("x", "x"), ("y", "y"),
        ("leftshoulder", "leftshoulder"), ("rightshoulder", "rightshoulder"),
        ("lefttrigger", "lefttrigger"), ("righttrigger", "righttrigger"),
        ("back", "back"), ("start", "start"),
        ("leftstick", "leftstick"), ("rightstick", "rightstick"),
        ("dpup", "dpup"), ("dpdown", "dpdown"),
        ("dpleft", "dpleft"), ("dpright", "dpright"),
    ]
    parts = []
    for sdl_name, es_name in mapping:
        if es_name in attrs:
            parts.append("%s:%s" % (sdl_name, attrs[es_name]))
    if not parts:
        return ""
    guid = attrs.get("deviceGUID", "03000000000000000000000000000000")
    name = attrs.get("deviceName", "ArkOS Controller")
    return "%s,%s,%s" % (guid, name, ",".join(parts))


def main():
    xml = read_es_config()
    attrs = parse_input_config(xml) if xml else None
    if not attrs:
        # Fallback: Standard-ArkOS-M9-Pro-Layout
        attrs = {
            "deviceGUID": "030000005e0400008e02000010010000",
            "deviceName": "Xbox 360 Controller",
            "a": "b0", "b": "b1", "x": "b2", "y": "b3",
            "leftshoulder": "b4", "rightshoulder": "b5",
            "back": "b6", "start": "b7",
            "leftstick": "b8", "rightstick": "b9",
            "dpup": "h0.1", "dpdown": "h0.4",
            "dpleft": "h0.8", "dpright": "h0.2",
        }
    out = build_gc_string(attrs)
    if out:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
