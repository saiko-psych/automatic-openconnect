# scripts/gen_backgrounds.py
# -*- coding: utf-8 -*-
"""Dev tool — regenerate the looping backdrop GIFs bundled with the app.

These are our OWN procedurally-drawn loops (Pillow only, no third-party
artwork), so they are effectively CC0 and safe to ship. The GIFs live under
``src/automatic_openconnect/assets/backgrounds/`` and are wired to the
``kawaii`` and ``meme`` themes (see gui._THEME_GIF). The script is NOT shipped;
it just lets us re-create the assets:

    .venv\\Scripts\\python.exe scripts\\gen_backgrounds.py

Produces:
  * kawaii.gif — pastel anime loop: a cute chibi face (big sparkly blinking
    eyes + blush) with floating hearts and 4-point twinkle stars drifting up.
  * meme.gif   — deep-fried warm glow pulsing behind a green "stonks" up-arrow
    with a sparkly lens-flare. Bold and funny.

Both loop seamlessly (the animation phase wraps over the frame count) and are
kept small (modest size + GIF optimise + a tight palette) so they stay well
under ~1 MB and don't bloat the bundle.
"""
from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw, ImageOps

# Output lives next to the bundled fonts so the PyInstaller spec (which bundles
# the whole assets dir) ships it automatically.
_ASSETS = os.path.join(os.path.dirname(__file__), "..", "src",
                       "automatic_openconnect", "assets", "backgrounds")

# Modest canvas — the backdrop is scaled to the window anyway, so a small,
# cheap-to-decode GIF is plenty. Supersample x2 while drawing, then downscale
# for clean anti-aliased edges without a big file.
W, H = 480, 320
SS = 2                      # supersample factor
FRAMES = 24                 # smooth loop, divides evenly into the phase
DURATION = 60               # ms per frame (~16 fps)


def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _vgrad(size, top, bottom):
    """A vertical gradient image (top→bottom)."""
    w, h = size
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(h):
        col = _lerp(top, bottom, y / max(1, h - 1))
        for x in range(w):
            px[x, y] = col
    return img


def _radial(size, center, radius, inner, outer):
    """A radial gradient (inner colour at center → outer at radius)."""
    w, h = size
    img = Image.new("RGB", size)
    px = img.load()
    cx, cy = center
    for y in range(h):
        for x in range(w):
            d = math.hypot(x - cx, y - cy) / max(1.0, radius)
            px[x, y] = _lerp(inner, outer, min(1.0, d))
    return img


def _star(draw, cx, cy, s, fill):
    """A 4-point twinkle star (kawaii sticker style)."""
    k = s * 0.28
    draw.polygon([(cx, cy - s), (cx + k, cy - k), (cx + s, cy),
                  (cx + k, cy + k), (cx, cy + s), (cx - k, cy + k),
                  (cx - s, cy), (cx - k, cy - k)], fill=fill)


def _heart(draw, cx, cy, s, fill):
    """A filled heart — two lobes + a triangle, snapped to the supersampled
    canvas so it stays crisp after downscaling."""
    r = s * 0.5
    draw.ellipse([cx - s, cy - r, cx, cy + r], fill=fill)
    draw.ellipse([cx, cy - r, cx + s, cy + r], fill=fill)
    draw.polygon([(cx - s + 1, cy + r * 0.25), (cx + s - 1, cy + r * 0.25),
                  (cx, cy + s * 1.15)], fill=fill)


# --- kawaii: chibi face + floating hearts/stars on a pastel sky --------------

def _kawaii_frame(i):
    """One frame of the kawaii loop. ``ph`` in [0,1) is the loop phase."""
    ph = i / FRAMES
    w, h = W * SS, H * SS
    img = _vgrad((w, h), (255, 217, 236), (214, 194, 255))  # peach → lavender
    d = ImageDraw.Draw(img, "RGBA")

    # drifting hearts + stars rising and gently swaying (stable layout via a
    # cheap hash of the index → reproducible placement, no RNG dependency).
    items = 14
    for n in range(items):
        fx = ((n * 73 + 11) % 97) / 97.0
        fz = ((n * 37 + 5) % 53) / 53.0
        base = (ph + n / items) % 1.0           # seamless: wraps with the loop
        y = h * (1.05 - base * 1.15)
        sway = math.sin((base + fz) * 2 * math.pi) * (10 + fz * 26) * SS
        x = fx * w + sway
        s = (10 + fz * 16) * SS
        if n % 3 == 0:
            twk = 0.8 + 0.2 * math.sin((ph + fz) * 4 * math.pi)
            _star(d, x, y, s * twk, (255, 245, 160, 200))
        else:
            pal = [(255, 95, 162), (255, 143, 191), (185, 139, 255)][n % 3]
            _heart(d, x, y, s, pal + (190,))

    # --- the chibi face: a soft round head, blush, big sparkly eyes ---------
    cx, cy = w * 0.5, h * 0.52
    hr = h * 0.30                               # head radius
    d.ellipse([cx - hr, cy - hr, cx + hr, cy + hr], fill=(255, 250, 252, 255),
              outline=(255, 178, 209, 255), width=3 * SS)
    # rosy cheeks
    br = hr * 0.20
    for sgn in (-1, 1):
        bx = cx + sgn * hr * 0.55
        by = cy + hr * 0.22
        d.ellipse([bx - br, by - br * 0.7, bx + br, by + br * 0.7],
                  fill=(255, 158, 197, 150))

    # blink: eyes are open most of the loop, snap shut briefly near ph~0.5
    blink = 0.5 < ph < 0.58
    ew, eh = hr * 0.26, hr * 0.34
    for sgn in (-1, 1):
        ex = cx + sgn * hr * 0.42
        ey = cy - hr * 0.05
        if blink:
            d.line([ex - ew, ey, ex + ew, ey], fill=(90, 60, 80, 255),
                   width=4 * SS)
            continue
        # glossy eye: dark base + iris glint + a moving sparkle highlight
        d.ellipse([ex - ew, ey - eh, ex + ew, ey + eh], fill=(60, 40, 70, 255))
        d.ellipse([ex - ew * 0.7, ey - eh * 0.55, ex + ew * 0.7,
                   ey + eh * 0.85], fill=(150, 90, 180, 255))
        gx = ex - ew * 0.3 + math.sin(ph * 2 * math.pi) * ew * 0.15
        gy = ey - eh * 0.45
        d.ellipse([gx - ew * 0.42, gy - ew * 0.42, gx + ew * 0.42,
                   gy + ew * 0.42], fill=(255, 255, 255, 255))
        d.ellipse([ex + ew * 0.25, ey + eh * 0.25, ex + ew * 0.5,
                   ey + eh * 0.5], fill=(255, 255, 255, 200))
    if not blink:
        # a tiny smiling mouth (small upward arc — the lower half of an ellipse)
        mw = hr * 0.22
        d.arc([cx - mw, cy + hr * 0.10, cx + mw, cy + hr * 0.46],
              20, 160, fill=(200, 110, 150, 255), width=3 * SS)

    return img.resize((W, H), Image.LANCZOS)


# --- meme: deep-fried glow + green "stonks" arrow + lens-flare ---------------

def _meme_frame(i):
    ph = i / FRAMES
    w, h = W * SS, H * SS
    # deep-fried warm glow that PULSES (orange core breathing in/out)
    pulse = 0.5 + 0.5 * math.sin(ph * 2 * math.pi)
    radius = max(w, h) * (0.6 + 0.12 * pulse)
    inner = _lerp((255, 120, 30), (255, 60, 0), pulse)   # deep-fried orange/red
    img = _radial((w, h), (w * 0.5, h * 0.55), radius, inner, (40, 8, 60))
    # Posterize the smooth gradient into hard bands — it reads as the classic
    # "deep-fried" banding AND keeps the GIF small (few unique colours).
    img = ImageOps.posterize(img, 3)
    d = ImageDraw.Draw(img, "RGBA")

    # scattered "deep-fried" sparkles + jpeg-ish noise dots
    for n in range(60):
        sx = ((n * 89 + 13) % 101) / 101.0 * w
        sy = ((n * 53 + 7) % 79) / 79.0 * h
        twk = 0.5 + 0.5 * math.sin((ph + n * 0.13) * 2 * math.pi)
        r = (1 + (n % 3)) * SS
        a = int(60 + 120 * twk)
        d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(255, 240, 120, a))

    # the green STONKS up-arrow: a thick rising line + a big arrowhead, nudged
    # up/down a touch so it looks like it's "pumping".
    bob = math.sin(ph * 2 * math.pi) * 8 * SS
    g = (60, 230, 90, 255)
    x0, y0 = w * 0.22, h * 0.78 + bob
    x1, y1 = w * 0.74, h * 0.30 + bob
    d.line([x0, y0, x1, y1], fill=g, width=10 * SS)
    # zig-zag "chart" feet under the main shaft for extra stonks energy
    d.line([w * 0.12, h * 0.70 + bob, x0, y0], fill=(60, 230, 90, 160),
           width=6 * SS)
    # arrowhead
    ah = 26 * SS
    d.polygon([(x1 + ah * 0.4, y1 - ah * 0.4),
               (x1 - ah, y1 - ah * 0.1),
               (x1 + ah * 0.1, y1 + ah)], fill=g)

    # rotating lens-flare glint top-left (the classic meme shine)
    fx, fy = w * 0.30, h * 0.28
    spin = ph * 2 * math.pi
    for k in range(4):
        ang = spin + math.pi * k / 4
        dx, dy = math.cos(ang), math.sin(ang)
        R = max(w, h) * 0.18
        wdt = 3 * SS
        d.polygon([(fx + dy * wdt, fy - dx * wdt),
                   (fx + dx * R, fy + dy * R),
                   (fx - dy * wdt, fy + dx * wdt),
                   (fx - dx * R, fy - dy * R)],
                  fill=(255, 255, 255, 150))
    d.ellipse([fx - 14 * SS, fy - 14 * SS, fx + 14 * SS, fy + 14 * SS],
              fill=(255, 255, 255, 220))

    return img.resize((W, H), Image.LANCZOS)


def _save_gif(path, frames, colors=64):
    """Save a quantised, optimised, infinitely-looping GIF. A tight palette
    (few colours) keeps the file small without a visible quality hit on these
    flat/banded scenes."""
    quant = [f.convert("RGB").quantize(colors=colors, method=Image.MEDIANCUT)
             for f in frames]
    quant[0].save(path, save_all=True, append_images=quant[1:],
                  duration=DURATION, loop=0, optimize=True, disposal=2)


def main() -> int:
    os.makedirs(_ASSETS, exist_ok=True)
    for name, maker in (("kawaii", _kawaii_frame), ("meme", _meme_frame)):
        frames = [maker(i) for i in range(FRAMES)]
        path = os.path.join(_ASSETS, f"{name}.gif")
        _save_gif(path, frames)
        kb = os.path.getsize(path) / 1024
        print(f"wrote {path}  ({kb:.0f} KB, {FRAMES} frames, {W}x{H})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
