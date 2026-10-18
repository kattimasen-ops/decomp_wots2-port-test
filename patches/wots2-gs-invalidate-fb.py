#!/usr/bin/env python3
"""Fügt glInvalidateFramebuffer am Ende von play() ein (Mali-Optimierung)."""
import sys, pathlib

p = pathlib.Path(sys.argv[1])
t = p.read_text()

# Finde das Ende der play-Funktion (vor dem Zurücksetzen des States)
anchor = "    state_2d();\n}"

if anchor not in t:
    print("FEHLER: play()-Ende nicht gefunden.", file=sys.stderr)
    sys.exit(1)

new_code = """    state_2d();
    // Mali-G31 Optimization: Depth-Buffer für den nächsten Frame verwerfen
    const GLenum invalidate_attachments[] = { GL_DEPTH_STENCIL_ATTACHMENT };
    glInvalidateFramebuffer(GL_FRAMEBUFFER, 1, invalidate_attachments);
}"""

t = t.replace(anchor, new_code, 1)
p.write_text(t)
print("OK: glInvalidateFramebuffer in gs.cpp eingebaut.")
