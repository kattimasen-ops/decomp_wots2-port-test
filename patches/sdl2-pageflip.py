#!/usr/bin/env python3
"""Fügt SDL2 2.30.10 einen Fallback für Mali-G31-Pageflips hinzu."""
import sys, re, pathlib

p = pathlib.Path(sys.argv[1])
t = p.read_text()

m = re.search(
    r'(ret = KMSDRM_drmModePageFlip\(viddata->drm_fd,\s*'
    r'dispdata->crtc->crtc_id,\s*'
    r'fb_info->fb_id, flip_flags,\s*'
    r'&windata->waiting_for_flip\);)',
    t)
if not m:
    print("FEHLER: KMSDRM_drmModePageFlip-Aufruf nicht gefunden.", file=sys.stderr)
    sys.exit(1)

fallback = (
    '\n    if (ret != 0 && (flip_flags & DRM_MODE_PAGE_FLIP_ASYNC)) {\n'
    '        SDL_LogInfo(SDL_LOG_CATEGORY_VIDEO,\n'
    '            "Async pageflip rejected by the driver; using synchronous flips.");\n'
    '        viddata->async_pageflip_support = SDL_FALSE;\n'
    '        flip_flags &= ~DRM_MODE_PAGE_FLIP_ASYNC;\n'
    '        ret = KMSDRM_drmModePageFlip(viddata->drm_fd, dispdata->crtc->crtc_id,\n'
    '            fb_info->fb_id, flip_flags, &windata->waiting_for_flip);\n'
    '    }'
)

t = t[:m.end()] + fallback + t[m.end():]
p.write_text(t)
print("OK: Pageflip-Fallback eingefügt")
