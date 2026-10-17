#!/usr/bin/env python3
import sys
from pathlib import Path

PATH   = Path("src/native/hle_chara.cpp")
MARKER = "/* WOTS2_REDUCE_SHADOW */"

OLD = """    hal::gs::begin_target(256);"""
NEW = """    hal::gs::begin_target(128); /* WOTS2_REDUCE_SHADOW */"""

def main():
    if not PATH.exists(): sys.exit(1)
    src = PATH.read_text()
    if MARKER in src: return
    if src.count(OLD) != 1: sys.exit(1)
    PATH.write_text(src.replace(OLD, NEW, 1))
