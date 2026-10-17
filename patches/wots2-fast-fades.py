#!/usr/bin/env python3
import sys
from pathlib import Path

PATH   = Path("src/native/hle.cpp")

def main():
    if not PATH.exists(): sys.exit(1)
    src = PATH.read_text()
    if "/* WOTS2_FAST_FADES */" in src: return
    
    # 80 strips for the fade -> 8 strips
    if "const int strips = 80;" in src:
        src = src.replace("const int strips = 80;", "const int strips = 8; /* WOTS2_FAST_FADES */", 1)
    
    # 56 strips for the wash -> 8 strips
    if "const int strips = 56;" in src:
        src = src.replace("const int strips = 56;", "const int strips = 8;", 1)
        
    PATH.write_text(src)
