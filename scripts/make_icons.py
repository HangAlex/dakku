#!/usr/bin/env python3
"""Draws Dakku's icons: a chibi white call duck on an indigo night.

Run again after changing the design:  python3 scripts/make_icons.py
(If you'd rather use a picture painted with ChatGPT, scripts/import_art.py makes the icons from it.)
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "icons"
INDIGO, INDIGO_LIGHT = (15, 23, 39), (34, 52, 84)
WHITE, SHADE, BEAK, BEAK_DARK, EYE, BLUSH = (251, 248, 242), (231, 225, 214), (245, 163, 59), (222, 133, 38), (42, 37, 48), (250, 172, 188)


def background(size):
    img = Image.new("RGB", (size, size), INDIGO)
    glow = Image.new("L", (size, size), 0)
    ImageDraw.Draw(glow).ellipse([size * 0.12, size * 0.1, size * 0.88, size * 0.86], fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(size * 0.16))
    return Image.composite(Image.new("RGB", (size, size), INDIGO_LIGHT), img, glow)


def duck(size, scale):
    """A duck face filling `scale` of the icon, drawn big and shrunk for smooth edges."""
    big = size * 4
    layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    u = big * scale / 100  # the face is 100 units across
    cx, cy = big / 2, big / 2 + 6 * u

    def ell(x, y, rx, ry, fill):
        d.ellipse([cx + (x - rx) * u, cy + (y - ry) * u, cx + (x + rx) * u, cy + (y + ry) * u], fill=fill)

    ell(0, 0, 50, 46, WHITE)                    # head
    ell(6, 22, 34, 16, SHADE)                   # shading under the chin
    ell(0, 3, 47, 41, WHITE)
    ell(-6, -50, 9, 7, WHITE)                   # a little tuft on top
    ell(5, -51, 7, 6, WHITE)
    ell(-27, 14, 10, 6, BLUSH + (190,))         # cheeks
    ell(27, 14, 10, 6, BLUSH + (190,))
    ell(-19, -4, 7.5, 8, EYE)                   # eyes, with a sparkle
    ell(19, -4, 7.5, 8, EYE)
    ell(-16.5, -7, 2.6, 2.6, (255, 255, 255))
    ell(21.5, -7, 2.6, 2.6, (255, 255, 255))
    ell(0, 15, 17, 8.5, BEAK)                   # a short, wide beak
    ell(0, 19.5, 12.5, 4.8, BEAK_DARK)
    return layer.resize((size, size), Image.LANCZOS)


def icon(size, scale=0.62):
    img = background(size).convert("RGBA")
    img.alpha_composite(duck(size, scale))
    return img.convert("RGB")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    icon(512).save(OUT / "icon-512.png", optimize=True)
    icon(192).save(OUT / "icon-192.png", optimize=True)
    icon(180, 0.64).save(OUT / "apple-touch-icon.png", optimize=True)  # iPhone rounds the corners itself
    icon(512, 0.48).save(OUT / "maskable-512.png", optimize=True)  # Android crops to a circle
    icon(64, 0.74).save(OUT / "favicon.png", optimize=True)
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
