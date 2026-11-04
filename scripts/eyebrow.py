"""eyebrow.py <in.png> <out.png>: draw Dakku's angry eyebrow on a finished ChatGPT picture (when ChatGPT's redraw
isn't worth the drift): one straight crayon stroke above the eye, tilted down toward the beak, a white gap under it,
in the outline's own charcoal, with a ragged edge and paper specks like the outline. Then: duck.py add <id> <out.png>."""
import sys, random
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import duck
from PIL import Image, ImageDraw, ImageFilter


def draw(src, dst, seed=7, length=1.9, thick=0.42, tilt=0.65, gap=0.4, shift=-0.1):
    """length, thick, gap, shift: in eye diameters (shift: the stroke's middle, left of the eye's middle when negative);
    tilt: how much lower the beak-side end is than the other, in eye diameters."""
    random.seed(seed)
    im = Image.open(src).convert("RGBA"); w, h = im.size
    e = duck.find_eyes(im, 0.5 * w)[0]; cx, cy, d = e["x"], e["y"], e["size"]
    px = im.load()
    dark = [px[x, y][:3] for x in range(int(cx - d), int(cx + d)) for y in range(int(cy - d), int(cy + d))
            if px[x, y][3] > 200 and max(px[x, y][:3]) < 90]
    col = tuple(sum(c[i] for c in dark) // len(dark) for i in range(3))
    mx, my = cx + shift * d, cy - d / 2 - gap * d - thick * d / 2 - tilt * d / 2
    x0, y0 = mx - length * d / 2, my + tilt * d / 2   # the beak side (left): lower
    x1, y1 = mx + length * d / 2, my - tilt * d / 2
    S = 4
    layer = Image.new("L", (w * S, h * S), 0)
    dr = ImageDraw.Draw(layer)
    width = thick * d * S
    dr.line([(x0 * S, y0 * S), (x1 * S, y1 * S)], fill=255, width=int(width))
    for X, Y in ((x0, y0), (x1, y1)):
        r = width / 2; dr.ellipse([X * S - r, Y * S - r, X * S + r, Y * S + r], fill=255)
    layer = layer.resize((w, h), Image.LANCZOS)
    noise = Image.effect_noise((w, h), 70).filter(ImageFilter.GaussianBlur(0.5))
    lp, npx = layer.load(), noise.load()
    for y in range(int(y1 - d), int(y0 + d)):
        for x in range(int(x0 - d), int(x1 + d)):
            a = lp[x, y]
            if a:
                n = (npx[x, y] - 128) / 128
                if a < 230: a = a * (0.35 + 0.65 * (1 - 0.8 * abs(n)))     # a ragged edge
                else: a = a * (0.72 + 0.28 * (1 - 1.0 * max(0, n)))        # paper specks inside
                lp[x, y] = int(max(0, min(255, a)))
    stroke = Image.new("RGBA", (w, h), col + (0,)); stroke.putalpha(layer)
    out = Image.alpha_composite(im, stroke)
    out.save(dst)
    return (round(cx), round(cy), d, col)


if __name__ == "__main__":
    # eyebrow.py in.png out.png [shift=-0.3 length=1.7 ...]: the numbers are in eye diameters (see draw)
    opts = {k: float(v) for k, v in (a.split("=") for a in sys.argv[3:])}
    print(draw(sys.argv[1], sys.argv[2], **opts))
