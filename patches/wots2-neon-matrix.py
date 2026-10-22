#!/usr/bin/env python3
"""
patches/wots2-neon-matrix.py   (v3 — 2026-10-22, Aufraeum-Patch)

Die alte v1/v2-Version hat einen kaputten NEON-Block in Matrix_Multiply
eingebaut, der a^T * b statt b * a rechnet. Damit war jede 3D-Transformation
im Port falsch (Skelett, Kamera, Objekte, Effekte) — das ganze Bild voller
zerstoerter Geometrie.

Diese v3-Version baut NICHTS mehr ein. Sie ERKENNT den kaputten Block am
Marker '/* WOTS2_NEON_MATRIX */' und entfernt ihn, sodass die korrekte
Skalar-Funktion (mat_mul mit richten Vorzeichen) uebrig bleibt.

Wenn die Quelldatei sauber ist (kein Marker), ist der Patch ein No-op.
Der Patch ist damit idempotent und sicher wiederholbar.

Zieldatei: src/native/hle.cpp
"""
import sys
from pathlib import Path

PATH   = Path("src/native/hle.cpp")
MARKER = "/* WOTS2_NEON_MATRIX */"

FIXED_LINE = "    mat_mul(static_cast<const float*>(b), static_cast<const float*>(a), static_cast<float*>(dst));"


def main():
    if not PATH.exists():
        print(f"  FEHLER: {PATH} fehlt")
        return 1
    src = PATH.read_text()

    idx = src.find(MARKER)
    if idx < 0:
        print("  kein kaputter NEON-Matrix-Block vorhanden — nichts zu tun")
        return 0

    # Das Ende des kaputten Blocks: das naechste '#endif' nach dem Marker.
    end = src.find("#endif", idx)
    if end < 0:
        print(f"  FEHLER: Marker gefunden, aber kein '#endif' danach — Datei unerwartet")
        return 1
    end += len("#endif")

    # Der Block kann in einem 'Matrix_Multiply'-Body stecken. Ersetze den
    # gesamten Bereich [Marker .. #endif] durch die korrekte Skalar-Zeile.
    src = src[:idx] + FIXED_LINE + src[end:]
    PATH.write_text(src)
    print(f"  kaputten NEON-Matrix-Block in {PATH} entfernt")
    print(f"  Matrix_Multiply nutzt jetzt wieder mat_mul(b, a, dst)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
