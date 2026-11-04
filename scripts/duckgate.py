"""The duck gate: everything that has to match before a new or redrawn duck goes into Dakku, measured against the
ducks already in it (the ones committed in HEAD), and one picture per duck to look at.

    python3 scripts/duckgate.py ID[=chatgpt.png] [ID[=chatgpt.png] ...]   [--brief]   [--all]

ID alone checks its finished picture in art/ducks; ID=path checks ChatGPT's picture exactly as `duck.py add` would
finish it, without adding anything. --all checks every duck; --brief prints one line a duck and draws no pictures.
Every size is in the app's units (what Dakku draws), so a duck that would look bigger, smaller, taller or shorter than
Shiro shows up. The pictures go to art/review/gate/gate-<id>.png.

Measured (FLAG: outside the limit; LOOK: for looking at in the picture):
  size     the overall size (beak, eye, beak and body together: "scale" in art/ducks.json fixes it), beak width and
           height, eye size, how big the whole figure is with its outfit
  heights  eye and beak above the water; head top and back no lower than Shiro's; the proportions once size is out
  shape    the bottom's curve and flatness, a tilt on the water, the wing (one short curved line where Shiro's is)
  look     the outline's crayon grain and thickness (around Shiro's, neither smooth nor heavy), its color, the white's
           cream, paper grain, color saturation; marks on a calm face, blush, feet
  picture  parts left behind when cut out, specks, leftover background, a duplicate of another duck, how far a redraw
           drifted from the committed picture, and what's missing from art/ducks.json or what Dakku loads
Then look at the picture for what numbers can't catch: the outfit matches its look, nothing is held, no stray marks."""
import colorsys
import json
import math
import statistics
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "art" / "review" / "gate"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "scripts"))
import duck  # noqa: E402
import import_art as ia  # noqa: E402

LIST = duck.load()
PEACH = (251, 190, 122)
WORK_BODY = 360  # px: every picture is measured with its body this wide (fast, and the same for all)
TEX_BODY = 330  # px: texture is compared at the smallest native body any duck has, so none is favored

# limits, as fractions of the others' median (sizes and heights) or absolute (shape, look)
LIMITS = {"beak_w": 0.10, "beak_h": 0.12, "eye_y": 0.05, "beak_y": 0.05, "eye_size": 0.25}
# the overall size: the median of these against the others' (one thrown off by a tail or a cape doesn't move it)
SIZE_KEYS = ("beak_w", "beak_h", "eye_y", "beak_y", "beak_reach", "body_w")
SIZE_LIMIT = 0.04
# at least this share of Shiro's: an outfit only ever raises them, so lower means a lower head or a squashed back
FLOORS = {"head_top": 0.95, "back_y": 0.94}
# the outline's ragged crayon edge, at the size phones show a duck: Dakku's first ducks 1.34–1.98 (Shiro 1.80), the
# licensed ducks 1.03–1.33, the first new originals that lost the look 1.07–1.20
CRAYON, CRAYON_MAX = 1.15, 2.25  # around Shiro's 1.80: a smoother line is only noted (Alex: subtle, "dont over correct"); rougher is a flag
LINE_W = (1.5, 2.6)  # the outline's thickness, around Shiro's 2.02 (the first ducks 1.96-2.58; touch-ups that asked for
                     # "a little thicker" came out 2.7-3.4, which Alex saw as too heavy)
# the rest, as (FLAG or LOOK, low, high, what's wrong): the accepted ducks all sit inside these
EXTRA = {
    "beak_ratio": ("LOOK", 1.45, 1.85, "the beak's shape is unlike the others' (accepted 1.49-1.80)"),
    "eye_behind": ("LOOK", 4.8, 8.6, "the eye sits unusually near or far behind the beak (accepted 5.0-8.5)"),
    "outline_max": ("FLAG", 30, 75, "the outline is too black or too pale (Dakku's is soft charcoal; accepted 34-61)"),
    "outline_sat": ("LOOK", None, 0.7, "the outline looks colored rather than charcoal"),
    "haze": ("FLAG", None, 0.1, "leftover background: half-see-through pixels away from the duck (accepted: none)"),
    "specks": ("FLAG", None, 3, "stray specks around the duck (accepted: none)"),
    "tilt": ("FLAG", -3.0, 3.0, "it sits tilted: the bottom slopes where it rests on the water (degrees)"),
    "feet": ("LOOK", None, 25, "orange at the very bottom: feet? (or an orange outfit)"),
    "blush": ("LOOK", None, 0.05, "pink on the cheek: blush? (or pink hair)"),
    "pieces": ("LOOK", None, 1, "separate pieces besides the duck: a halo or sparks, as asked?"),
}
WHITE_DE = 4.5  # how far the body's white may be from Shiro's cream (accepted: 2.7 at most)
FLAT_MAX, CURVE_MIN = 0.585, 2.05  # (round: King, Cloud 0.58 / 2.07; flat-looking: Loid 0.59 / 2.03, Sonic, Yuta, Monokuma, Godzilla)


def committed():
    out = subprocess.run(["git", "-C", str(ROOT), "ls-tree", "--name-only", "HEAD", "art/ducks/"], capture_output=True, text=True).stdout
    return [Path(p).stem for p in out.split() if p.endswith(".png")]


def finished(did, src=None):
    """(picture, body px, notes, dropped share) for a duck: its finished picture, or ChatGPT's finished as add() would."""
    d = LIST.get(did, {})
    if src:
        sheet = ia.with_alpha(Image.open(src))
        piece, notes = duck.from_chatgpt(Path(src))
        img, facts = duck.finish(piece, notes=notes, hidden_eye=d.get("eye") == "hidden")
        # what cutting it out left behind: opaque pixels in ChatGPT's picture that aren't in the piece
        total = sum(1 for v in sheet.getchannel("A").get_flattened_data() if v > 128)
        kept = sum(1 for v in piece.getchannel("A").get_flattened_data() if v > 128)
        return img, facts["body"], notes + facts["problems"], (total - kept) / max(1, kept)
    img = Image.open(ROOT / "art" / "ducks" / f"{did}.png").convert("RGBA")
    body = d.get("body") or ia.BODY_UNITS / ia.measure(img, ia.BODY_UNITS)["unit"]
    return img, body, [], None


def resized(img, body, target):
    k = target / body
    return img.resize((max(1, round(img.width * k)), max(1, round(img.height * k))), Image.LANCZOS), target


def lum(p):
    return 0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2]


def sat(p):
    mx, mn = max(p[:3]), min(p[:3])
    return 0 if mx == 0 else (mx - mn) / mx


def is_peach(p):
    return p[3] > 200 and abs(p[0] - PEACH[0]) + abs(p[1] - PEACH[1]) + abs(p[2] - PEACH[2]) < 34


def metrics(did, img, body, hidden):
    """Everything measurable, in app units (sizes, heights) or plain numbers (shape, look)."""
    scale = float(LIST.get(did, {}).get("scale", 1))
    small, sb = resized(img, body, WORK_BODY)
    m = ia.measure(small, ia.BODY_UNITS, width=sb / scale)
    unit, base_y, base_x = m["unit"], m["baseY"], m["baseX"]
    w, h = small.size
    px = small.load()
    a = small.getchannel("A").load()
    r = {}

    def span(y):
        xs = [x for x in range(w) if a[x, y] > 128]
        return (xs[0], xs[-1]) if xs else None

    bh = 60 / unit
    spans = [span(int(base_y - bh * f)) for f in (0.04, 0.07, 0.10, 0.14) if 0 <= int(base_y - bh * f) < h]
    spans = [s for s in spans if s]
    widest = max(spans, key=lambda s: s[1] - s[0])
    r["body_w"] = (widest[1] - widest[0]) * unit
    front, back = widest

    # the beak: the peach patch next to the eye, as duck.py finds it (a gold stole or tassel can be peach too); for a
    # duck whose eye isn't on white, the biggest patch of Dakku's exact peach in the front two thirds
    beak = None if hidden else duck.face(small, sb)[1]
    if not beak:
        mask = bytearray(w * h)
        for y in range(h):
            for x in range(int(w * 0.65)):
                if is_peach(px[x, y]):
                    mask[y * w + x] = 1
        parts = sorted(duck.components(mask, w, h, 30), key=len, reverse=True)
        beak = [(j % w, j // w) for j in parts[0]] if parts else None
    eye = None
    if beak:
        xs = sorted(x for x, _ in beak)
        ys = sorted(y for _, y in beak)
        bx0, bx1 = xs[int(len(xs) * .02)], xs[int(len(xs) * .98)]
        by0, by1 = ys[int(len(ys) * .02)], ys[int(len(ys) * .98)]
        ymid = (by0 + by1) / 2
        r["beak_w"] = (bx1 - bx0) * unit
        r["beak_h"] = (by1 - by0) * unit
        r["beak_y"] = (base_y - ymid) * unit
        r["beak_reach"] = (base_x - bx0) * unit
        if not hidden:
            # the eye: a dark dot just above the beak's middle and a little behind its back edge
            for dot in duck.find_eyes(small, sb) + duck.find_eyes(small, sb * 0.8):
                up = (ymid - dot["y"]) * unit
                behind = (dot["x"] - bx1) * unit
                if 0 < up < 9 and -4 < behind < 14 and 1.8 < dot["size"] * unit < 6:
                    eye = dot
                    break
    if eye:
        r["eye_y"] = (base_y - eye["y"]) * unit
        r["eye_size"] = eye["size"] * unit
        if "beak_y" in r:
            r["eye_over_beak"] = r["eye_y"] - r["beak_y"]
        # the head's top: straight up from the eye, as far as the picture stays solid (a gap ends it, so a floating
        # halo isn't counted; a hat or hair sitting on the head is)
        tops = []
        for x in range(max(0, int(eye["x"] - 0.04 * sb)), min(w, int(eye["x"] + 0.04 * sb) + 1)):
            y, gap = int(eye["y"]), 0
            top = y
            while y > 0:
                y -= 1
                if a[x, y] > 128:
                    top, gap = y, 0
                else:
                    gap += 1
                    if gap > 2:
                        break
            tops.append(top)
        r["head_top"] = (base_y - statistics.median(tops)) * unit
    # the back: the silhouette's top over the back half of the body (an outfit only raises it)
    tops = []
    for x in range(int(front + 0.55 * (back - front)), int(front + 0.85 * (back - front))):
        top = min((y for y in range(h) if a[x, y] > 128), default=None)
        if top is not None:
            tops.append(top)
    r["back_y"] = (base_y - statistics.median(tops)) * unit if tops else None
    r["figure_top"] = (base_y - min(y for y in range(h) if any(a[x, y] > 128 for x in range(0, w, 2)))) * unit
    # how much there is of it, outfit and all: a bulky hood or a big tail makes a duck look bigger than one its size
    solid = small.getchannel("A").point(lambda v: 255 if v > 128 else 0)
    r["area"] = sum(1 for v in solid.get_flattened_data() if v) * unit * unit
    box = solid.getbbox()
    r["figure_w"] = (box[2] - box[0]) * unit

    # the bottom: how far its outline rises above its lowest point across the body (8 units up), overall, at the
    # front quarter and at the back quarter; and how wide it is just above the water against a little higher. On a
    # big copy (the app's body 1000px wide): 1.2 units is only a few pixels at the working size
    big, _ = resized(img, body / scale, 1000)
    bu = ia.BODY_UNITS / 1000
    ba = big.getchannel("A").point(lambda v: 255 if v > 128 else 0)
    bal = ba.load()
    bwid = big.width
    low = ba.getbbox()[3] - 1
    y8 = int(low - 8 / bu)
    xs8 = [x for x in range(bwid) if bal[x, y8]]
    if xs8:
        x0, x1 = xs8[0], xs8[-1]
        rises = []
        for i in range(21):
            x = int(x0 + (x1 - x0) * i / 20)
            ys = [y for y in range(y8, low + 1) if bal[x, y]]
            rises.append((low - max(ys)) * bu if ys else 8)
        r["bottom"] = statistics.mean(rises)
        r["bottom_front"] = statistics.mean(rises[:6])
        r["bottom_back"] = statistics.mean(rises[-6:])

        def width(up):
            y = int(round(low - up / bu))
            xs = [x for x in range(bwid) if bal[x, y]]
            return (xs[-1] - xs[0]) if xs else 0
        r["flat"] = width(1.2) / max(1, width(8.0))

    r.update(extras(did, small, sb, unit, base_x, base_y, eye, beak, front, back))

    lw = line_width(img, body / scale)
    if lw:  # (a duck that isn't white, like the Golden one, has no white for it to meet)
        r["line_w"] = lw

    # the look, at one common size
    tex, tb = resized(img, body / scale, TEX_BODY)
    r.update(texture(tex))
    return r, {"unit": unit, "base": (base_x, base_y), "small": small, "eye": eye, "front": front, "back": back}


def line_width(img, body):
    """How thick the outline is where it meets the white at the bottom of the body, in app units: from the first solid
    pixel inward, how many are dark, on each side, median (Shiro 2.02; a run through a dark outfit isn't counted)."""
    big, _ = resized(img, body, 600)
    m = ia.measure(big, ia.BODY_UNITS, width=600)
    u, px, w = m["unit"], big.load(), big.width
    runs = []
    for y in range(int(m["baseY"] - 0.22 * 600), int(m["baseY"] - 0.04 * 600), 2):
        xs = [x for x in range(w) if px[x, y][3] > 128]
        if not xs:
            continue
        for x, step in ((xs[0], 1), (xs[-1], -1)):
            n = miss = 0
            light = False
            while 0 <= x < w and px[x, y][3] > 128:
                if lum(px[x, y]) < 130:
                    n, miss = n + 1, 0
                else:
                    miss += 1
                    if miss > 1 and n:
                        light = lum(px[x, y]) > 200 and sat(px[x, y]) < 0.16
                        break
                x += step
            if n and light and n * u < 6:
                runs.append(n)
    return statistics.median(runs) * u if len(runs) > 8 else None


def lab(rgb):
    """sRGB (0-255) to CIE Lab, for telling how far apart two colors look."""
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(float(c)) for c in rgb[:3])
    x, y, z = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047, 0.2126 * r + 0.7152 * g + 0.0722 * b, (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116  # noqa: E731
    return (116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z)))


def extras(did, small, sb, unit, base_x, base_y, eye, beak, front, back):
    """The rest of what can go wrong in a picture: marks on the face, the beak's shape, the colors of the white and
    the outline, leftover background, specks, a tilt, feet."""
    w, h = small.size
    px = small.load()
    a = small.getchannel("A").load()
    out = {}
    beak_box = None
    if beak:
        bx = [x for x, _ in beak]
        by = [y for _, y in beak]
        beak_box = (min(bx), min(by), max(bx), max(by))
        bw, bh = beak_box[2] - beak_box[0], beak_box[3] - beak_box[1]
        out["beak_ratio"] = bw / max(1, bh)
        if eye:
            out["eye_behind"] = (eye["x"] - beak_box[2]) * unit
    if eye:
        # marks on the face: dark bits near the eye that aren't the eye, the beak's outline or a line coming in from
        # outside (the head's outline, hair, a hood): an eyebrow, a mouth, a frown, on a duck that should have none
        x0, x1 = int(max(0, eye["x"] - 0.22 * sb)), int(min(w - 1, eye["x"] + 0.22 * sb))
        y0, y1 = int(max(0, eye["y"] - 0.18 * sb)), int(min(h - 1, eye["y"] + 0.10 * sb))
        bw_, bh_ = x1 - x0 + 1, y1 - y0 + 1
        mask = bytearray(bw_ * bh_)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                p = px[x, y]
                if p[3] > 200 and lum(p) < 110:
                    mask[(y - y0) * bw_ + (x - x0)] = 1
        marks = 0
        for part in duck.components(mask, bw_, bh_, max(6, int((0.012 * sb) ** 2))):
            xs = [j % bw_ + x0 for j in part]
            ys = [j // bw_ + y0 for j in part]
            if min(xs) <= x0 or max(xs) >= x1 or min(ys) <= y0 or max(ys) >= y1:
                continue  # a line from outside the face
            if min(xs) <= eye["x"] <= max(xs) and min(ys) <= eye["y"] <= max(ys):
                continue  # the eye
            if beak_box and not (max(xs) < beak_box[0] - 6 or min(xs) > beak_box[2] + 6 or max(ys) < beak_box[1] - 6 or min(ys) > beak_box[3] + 6):
                continue  # the beak's own outline
            marks += 1
        out["face_marks"] = marks
        # blush: pink on the cheek, behind and below the eye
        pink = 0
        for y in range(int(eye["y"]), int(min(h, eye["y"] + 0.16 * sb))):
            for x in range(int(max(0, eye["x"] - 0.05 * sb)), int(min(w, eye["x"] + 0.2 * sb))):
                p = px[x, y]
                if p[3] < 200:
                    continue
                hh, ss, vv = colorsys.rgb_to_hsv(p[0] / 255, p[1] / 255, p[2] / 255)
                if (hh > 0.9 or hh < 0.03) and 0.12 < ss < 0.55 and vv > 0.75:
                    pink += 1
        out["blush"] = pink / max(1, (0.12 * sb) ** 2)
    # the white: how far the body's white is from Shiro's cream
    whites = []
    for y in range(int(base_y - 0.45 * sb), int(base_y - 0.08 * sb), 2):
        for x in range(int(front), int(back), 2):
            if 0 <= x < w and 0 <= y < h:
                p = px[x, y]
                if p[3] > 250 and lum(p) > 215 and sat(p) < 0.1:
                    whites.append(p)
    if len(whites) > 100:
        out["white_lab"] = [statistics.median(lab(p)[i] for p in whites[::3]) for i in range(3)]
    # the outline's color: the dark pixels just inside the silhouette
    tone = duck.outline_tone(small)
    if tone and whites:  # (on a duck that isn't white, the Golden one, the dark pixels by its edge are its own color)
        out["outline_max"] = max(tone)
        out["outline_sat"] = (max(tone) - min(tone)) / max(1, max(tone))
    # leftover background: half-transparent pixels away from the duck (a halo of the old white, a shadow, water)
    solid = small.getchannel("A").point(lambda v: 255 if v > 200 else 0)
    near = solid.filter(ImageFilter.MaxFilter(9)).load()
    haze = sum(1 for y in range(0, h, 2) for x in range(0, w, 2) if 10 < a[x, y] < 200 and not near[x, y])
    out["haze"] = haze * 4 / (w * h) * 100  # % of the picture
    # specks: separate bits besides the duck (a halo or sparks are fine, and counted)
    m2 = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            if a[x, y] > 128:
                m2[y * w + x] = 1
    parts = sorted((len(p) for p in duck.components(m2, w, h, 12)), reverse=True)
    out["pieces"] = len(parts)
    out["specks"] = sum(1 for n in parts[1:] if n < 0.002 * parts[0])
    # a tilt: the slope of the bottom where it sits on the water (the columns within 2 units of the lowest point), in
    # degrees; a tail or a cape hanging at one end doesn't count, only the stretch the duck rests on
    lows = {}
    for x in range(w):
        for y in range(h - 1, -1, -1):
            if a[x, y] > 128:
                lows[x] = y
                break
    if lows:
        bottom = max(lows.values())
        contact = sorted(x for x, y in lows.items() if y >= bottom - 2 / unit)
        if len(contact) > 10:
            c0, c1 = contact[0], contact[-1]
            xs = [x for x in contact if c0 + 0.1 * (c1 - c0) <= x <= c1 - 0.1 * (c1 - c0)]
            if len(xs) > 5:
                mx = statistics.mean(xs)
                my = statistics.mean(lows[x] for x in xs)
                slope = sum((x - mx) * (lows[x] - my) for x in xs) / max(1e-9, sum((x - mx) ** 2 for x in xs))
                out["tilt"] = math.degrees(math.atan(slope))
    # the duck's own wing: the dark strokes inside the lower back of the body, the outer outline worn away (Shiro: one
    # curved line about 17 x 11 units, its middle 17 units behind the base point and 15 above the water)
    inner = small.getchannel("A").point(lambda v: 255 if v > 200 else 0).filter(ImageFilter.MinFilter(9)).load()
    wx0, wx1 = int(base_x - 0.05 * sb), int(min(w - 1, base_x + 0.5 * sb))
    wy0, wy1 = int(base_y - 0.42 * sb), int(base_y - 0.06 * sb)
    ww, wh = wx1 - wx0 + 1, wy1 - wy0 + 1
    wmask = bytearray(ww * wh)
    for y in range(wy0, wy1 + 1):
        for x in range(wx0, wx1 + 1):
            if inner[x, y] and lum(px[x, y]) < 120:
                wmask[(y - wy0) * ww + (x - wx0)] = 1
    strokes = []
    for part in duck.components(wmask, ww, wh, 25):
        xs = [j % ww for j in part]
        ys = [j // ww for j in part]
        if min(xs) == 0 or max(xs) == ww - 1 or min(ys) == 0 or max(ys) == wh - 1:
            continue  # it runs out of the wing's area: an outfit's line, not the wing
        strokes.append((len(part), (statistics.mean(xs) + wx0 - base_x) * unit, (base_y - statistics.mean(ys) - wy0) * unit,
                        (max(xs) - min(xs)) * unit, (max(ys) - min(ys)) * unit))
    strokes.sort(reverse=True)
    main = [t for t in strokes if t[0] > 0.3 * strokes[0][0]] if strokes else []
    out["wing_strokes"] = len(main)
    if main:
        out["wing"] = list(main[0][1:])  # where its middle is (behind, up) and how wide and tall, in app units

    # feet: orange (not the beak) at the very bottom
    feet = 0
    for y in range(int(base_y - 6 / unit), min(h, int(base_y) + 1)):
        for x in range(w):
            p = px[x, y]
            if p[3] > 200:
                hh, ss, vv = colorsys.rgb_to_hsv(p[0] / 255, p[1] / 255, p[2] / 255)
                if 0.03 < hh < 0.12 and ss > 0.4 and vv > 0.6 and not (beak_box and beak_box[0] - 4 <= x <= beak_box[2] + 4 and beak_box[1] - 4 <= y <= beak_box[3] + 4):
                    feet += 1
    out["feet"] = feet * unit * unit
    return out


def texture(img):
    """Paper grain in the white and in the colors (how much each pixel differs from its blurred surroundings), the
    outline's mottling (how uneven its darkness is) and ragged edge, and how saturated the colors are."""
    w, h = img.size
    rgb = img.convert("RGB")
    L = rgb.convert("L")
    blur = L.filter(ImageFilter.GaussianBlur(2.5))
    alpha = img.getchannel("A").filter(ImageFilter.MinFilter(7))
    dark = L.point(lambda v: 255 if v < 150 else 0).filter(ImageFilter.MaxFilter(7))
    px, lp, bp, ap, dp = img.load(), L.load(), blur.load(), alpha.load(), dark.load()
    white, color, line, sats = [], [], [], []
    for y in range(0, h):
        for x in range(0, w):
            p = px[x, y]
            if p[3] < 250:
                continue
            v = lp[x, y]
            if v < 105:
                line.append(v)
                continue
            if ap[x, y] < 250 or dp[x, y]:
                continue
            s = sat(p)
            if is_peach(p):
                continue
            if v > 215 and s < 0.08:
                white.append(v - bp[x, y])
            elif s > 0.18 and 50 < v < 235:
                color.append(v - bp[x, y])
                sats.append(s)
    # a ragged edge: the outline mask's boundary, against the same mask smoothed
    mask = L.point(lambda v: 255 if v < 120 else 0)
    smooth = mask.filter(ImageFilter.MedianFilter(5))

    def boundary(im):
        e = im.filter(ImageFilter.FIND_EDGES)
        return sum(1 for v in e.get_flattened_data() if v > 128)
    out = {}
    if len(white) > 200:
        out["grain_white"] = statistics.pstdev(white)
    if len(color) > 200:
        out["grain_color"] = statistics.pstdev(color)
        out["sat_mean"] = statistics.mean(sats)
        out["sat_90"] = sorted(sats)[int(len(sats) * 0.9)]
    if len(line) > 200:
        out["line_mottle"] = statistics.pstdev(line)
        out["line_ragged"] = boundary(mask) / max(1, boundary(smooth))
    return out


# ── the others ─────────────────────────────────────────────────────────────────
def population(skip):
    cache_path = OUT / "gate-cache.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    found = {}
    for did in committed():
        if did in skip or did not in LIST:
            continue
        p = ROOT / "art" / "ducks" / f"{did}.png"
        key = f"{p.stat().st_size}:{p.stat().st_mtime_ns}:{LIST[did].get('body')}:{LIST[did].get('scale', 1)}:v11"
        if cache.get(did, {}).get("key") != key:
            img, body, _, _ = finished(did)
            r, _ = metrics(did, img, body, LIST[did].get("eye") == "hidden")
            cache[did] = {"key": key, "m": r}
        found[did] = cache[did]["m"]
    cache_path.write_text(json.dumps(cache, indent=1))
    return found


def judge(name, value, others, shiro):
    """The verdict on one number: against the others' median (and their middle 80%), and Shiro's."""
    vals = sorted(v for v in others if v is not None)
    med = statistics.median(vals)
    lo, hi = vals[len(vals) // 10], vals[-len(vals) // 10 - 1]
    flag = ""
    if value is None:
        return f"{name:13s}   (not found)", "missing"
    if name in FLOORS:
        floor = shiro * FLOORS[name]
        if value < floor:
            flag = f"FLAG lower than Shiro's {shiro:.2f} (floor {floor:.2f}): the head sits low or the body is squashed"
        return f"{name:13s} {value:6.2f}   shiro {shiro:6.2f} ({(value - shiro) / shiro * 100:+.0f}%; an outfit may only raise it)   median {med:.2f}", flag
    if name in EXTRA:
        kind, low, high, why = EXTRA[name]
        bad = (low is not None and value < low) or (high is not None and value > high)
        flag = f"{kind} {why}" if bad else ""
        return f"{name:13s} {value:6.2f}   median {med:6.2f}   accepted range {vals[0]:.2f}-{vals[-1]:.2f}", flag
    if name == "line_ragged":
        flag = (f"LOOK a smoother line than the first ducks' crayon (under {CRAYON}): fine if it's even and charcoal, like the older ducks' (never ask for a rougher one: it comes out crumbly)" if value < CRAYON
                else f"FLAG a rougher line than Shiro's (over {CRAYON_MAX}): ask for the reference's line, no rougher" if value > CRAYON_MAX else "")
        return f"{name:13s} {value:6.2f}   shiro {shiro:.2f}   the first ducks 1.34–1.98   licensed ducks 1.03–1.33", flag
    if name == "line_w":
        flag = (f"FLAG a thicker outline than Shiro's (over {LINE_W[1]}): ask for the plain duck's line thickness" if value > LINE_W[1]
                else f"FLAG a thinner outline than Shiro's (under {LINE_W[0]})" if value < LINE_W[0] else "")
        return f"{name:13s} {value:6.2f}   shiro {shiro:.2f}   the first ducks 1.96–2.58   accepted median {med:.2f}", flag
    if name in LIMITS:
        off = (value - med) / med
        if abs(off) > LIMITS[name]:
            flag = f"FLAG {off * 100:+.0f}% from the median (limit ±{LIMITS[name] * 100:.0f}%)"
        text = f"{value:6.2f}   median {med:6.2f} ({off * 100:+5.1f}%)   middle 80% {lo:.2f}–{hi:.2f}   shiro {shiro:.2f} ({(value - shiro) / shiro * 100:+.0f}%)"
    else:
        text = f"{value:6.2f}   median {med:6.2f}   middle 80% {lo:.2f}–{hi:.2f}   shiro {shiro:.2f}"
        # the bottom, as it looks: round up to 0.58 with a curve of 2.05 or more (Shiro 0.54 / 2.25, Samurai 0.57 / 2.08,
        # King 0.58 / 2.07), sitting on a long flat base past that (Loid 0.59 / 2.03, Sonic, Yuta, Monokuma, Godzilla)
        if name == "flat" and value > FLAT_MAX:
            flag = f"FLAG a flatter bottom than Shiro's (over {FLAT_MAX}): ask for the reference's round bottom"
        if name == "bottom" and value < CURVE_MIN:
            flag = f"FLAG the bottom barely curves up (under {CURVE_MIN})"
        if name in ("bottom_front", "bottom_back") and value < lo * 0.85:
            flag = f"FLAG flat at that end (under {lo * 0.85:.2f})"
        if name in ("area", "figure_w") and value > hi:
            flag = f"LOOK more duck than 90% of the others (over {hi:.0f}): does the outfit make it look bigger?"
        if name == "sat_mean" and value > 0.62:
            flag = "LOOK brighter colors than most: are they the reference's soft, muted tones?"
    return f"{name:13s} {text}", flag


ORDER = ["body_w", "beak_w", "beak_h", "eye_y", "beak_y", "head_top", "back_y", "figure_top", "area", "figure_w", "eye_size", "eye_over_beak",
         "beak_reach", "beak_ratio", "eye_behind", "bottom", "bottom_front", "bottom_back", "flat", "tilt", "grain_white",
         "grain_color", "line_mottle", "line_ragged", "line_w", "outline_max", "outline_sat", "sat_mean", "sat_90", "blush", "feet",
         "haze", "pieces", "specks"]


# ── the picture ────────────────────────────────────────────────────────────────
BG = (34, 44, 66, 255)
INK = (228, 230, 240, 255)


def at_app(did, img, body, K):
    """The picture as big as Dakku draws it (K sheet px per app unit), and its base point."""
    scale = float(LIST.get(did, {}).get("scale", 1))
    m = ia.measure(img, ia.BODY_UNITS, width=body / scale)
    s = m["unit"] * K
    return img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS), m["baseX"] * s, m["baseY"] * s


def sheet(did, img, body, r, others, compare):
    K = 6.0
    shiro_img, shiro_body, _, _ = finished("shiro")
    row = [("shiro", shiro_img, shiro_body), (did, img, body)] + [(c, *finished(c)[:2]) for c in compare]
    pics = [(n, *at_app(n, im, b, K)) for n, im, b in row]
    pad = 30
    lineup_h = int(max(by for *_, by in pics) + 80)
    lineup_w = int(sum(p.width for _, p, _, _ in pics) + pad * (len(pics) + 1))
    # overlays: Shiro's silhouette filled, the checked duck's outline in red on the same water point; once as Dakku
    # draws them, once with the size taken out (so what's left is shape: the head's height, the bottom, the back)
    sp, sbx, sby = pics[0][1], pics[0][2], pics[0][3]
    npic, nbx, nby = pics[1][1], pics[1][2], pics[1][3]
    f = r.get("size_factor", 1.0)
    npic2 = npic.resize((max(1, round(npic.width / f)), max(1, round(npic.height / f))), Image.LANCZOS)
    overlays = [("as drawn", npic, nbx, nby), (f"size taken out ({(f - 1) * 100:+.0f}%)", npic2, nbx / f, nby / f)]
    ov_w = int(max(sbx, nbx) + max(sp.width - sbx, npic.width - nbx) + 2 * pad)
    W = max(lineup_w + 2 * ov_w + pad, 1800)
    tex_h = 420
    H = lineup_h + tex_h + 380
    out = Image.new("RGBA", (W, H), BG)
    d = ImageDraw.Draw(out)
    water = lineup_h - 40
    x = pad
    for n, p, bx, by in pics:
        out.alpha_composite(p, (int(x), int(water - by)))
        d.text((x, 8), n + ("  <- checking" if n == did else ""), fill=(255, 210, 120, 255) if n == did else INK)
        if n == did:
            for key, color in (("head_top", (255, 120, 120, 255)), ("eye_y", (120, 220, 255, 255)), ("beak_y", (255, 200, 120, 255)), ("back_y", (170, 255, 170, 255))):
                if r.get(key):
                    yy = water - r[key] * K
                    d.line((x - 6, yy, x + p.width + 6, yy), fill=color, width=2)
        x += p.width + pad
    d.line((0, water, lineup_w, water), fill=(120, 150, 190, 255), width=2)
    sh = others["shiro"]
    for key, color in (("head_top", (255, 120, 120, 200)), ("eye_y", (120, 220, 255, 200)), ("beak_y", (255, 200, 120, 200)), ("back_y", (170, 255, 170, 200))):
        if sh.get(key):
            yy = water - sh[key] * K
            for xx in range(0, lineup_w, 14):
                d.line((xx, yy, xx + 7, yy), fill=color, width=1)
            d.text((lineup_w - 150, yy - 12), f"shiro {key}", fill=color)
    d.text((pad, lineup_h - 30), "dashed: Shiro's head top / back / eye / beak heights; solid: the checked duck's", fill=INK)
    for i, (label, q, qbx, qby) in enumerate(overlays):
        ox = lineup_w + pad + i * ov_w
        cx = ox + pad + max(sbx, qbx)
        gray = Image.new("RGBA", sp.size, (200, 200, 210, 255))
        gray.putalpha(sp.getchannel("A").point(lambda v: 110 if v > 128 else 0))
        out.alpha_composite(gray, (int(cx - sbx), int(water - sby)))
        edge = q.getchannel("A").point(lambda v: 255 if v > 128 else 0).filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3))
        red = Image.new("RGBA", q.size, (255, 70, 70, 255))
        red.putalpha(edge)
        out.alpha_composite(red, (int(cx - qbx), int(water - qby)))
        d.text((ox + 6, 8), f"red over Shiro (gray): {label}", fill=INK)
    d.line((lineup_w, water, W, water), fill=(120, 150, 190, 255), width=1)

    # texture close-ups: the back and bottom of the body, and the outfit's most colorful patch, at 2x native,
    # every picture with its body 600 px wide
    y0 = lineup_h + 10
    d.text((pad, y0), "texture, same size (body 600px): checking / shiro / " + (compare[0] if compare else ""), fill=INK)
    tiles = []
    for n in [did, "shiro"] + compare[:1]:
        im, b = (img, body) if n == did else finished(n)[:2]
        big, _ = resized(im, b, 600)
        m = ia.measure(big, ia.BODY_UNITS, width=600)
        bx, by = m["baseX"], m["baseY"]
        back = big.crop((int(bx + 60), int(by - 230), int(bx + 330), int(by + 10)))
        tiles.append(back)
        # most colorful 270x240 window (outfit), on a coarse grid
        sm = big.resize((big.width // 10, big.height // 10))
        spx = sm.load()
        best, bxy = -1, (0, 0)
        for yy in range(0, sm.height - 24):
            for xx in range(0, sm.width - 27):
                score = sum(sat(spx[xx + i, yy + j]) * (spx[xx + i, yy + j][3] > 200) for i in range(0, 27, 3) for j in range(0, 24, 3))
                if score > best:
                    best, bxy = score, (xx, yy)
        tiles.append(big.crop((bxy[0] * 10, bxy[1] * 10, bxy[0] * 10 + 270, bxy[1] * 10 + 240)))
    x = pad
    for t in tiles:
        t2 = t.resize((t.width * 3 // 2, t.height * 3 // 2), Image.LANCZOS)
        bgt = Image.new("RGBA", t2.size, (244, 241, 234, 255))
        bgt.alpha_composite(t2)
        out.alpha_composite(bgt, (x, y0 + 20))
        x += t2.width + 10
    # wing side and face, body 420px
    y1 = y0 + tex_h
    x = pad
    for n in [did, "shiro"]:
        im, b = (img, body) if n == did else finished(n)[:2]
        big, _ = resized(im, b, 420)
        wing = big.crop((big.width // 2 - 40, big.height - 300, big.width, big.height))
        bgw = Image.new("RGBA", wing.size, BG)
        bgw.alpha_composite(wing)
        out.alpha_composite(bgw, (x, y1))
        d.text((x + 4, y1 + 2), f"{n} wing side", fill=INK)
        x += wing.width + 10
        e = duck.find_eye(big, 420)
        if e:
            fc = big.crop((int(e["x"] - 140), int(e["y"] - 110), int(e["x"] + 120), int(e["y"] + 150)))
            bgf = Image.new("RGBA", fc.size, BG)
            bgf.alpha_composite(fc)
            out.alpha_composite(bgf, (x, y1))
            d.text((x + 4, y1 + 2), f"{n} face", fill=INK)
            x += fc.width + 10
    path = OUT / f"gate-{did}.png"
    out.save(path)
    return path


def thumb(img, body):
    """A tiny copy of a duck at its body's size, for telling pictures apart: its silhouette and its colors."""
    small, _ = resized(img, body, 64)
    box = small.getchannel("A").point(lambda v: 255 if v > 128 else 0).getbbox()
    small = small.crop(box).resize((40, 40), Image.LANCZOS)
    return small


def drift(img, body, did):
    """How far a new picture of a duck is from its current one: how much their outlines overlap (each at its body's
    size, on the same base point) and how far apart their colors are (the mean of each third of the picture, Lab)."""
    # against the committed picture (what Dakku had before this round of changes), else the current one
    import io
    got = subprocess.run(["git", "-C", str(ROOT), "show", f"HEAD:art/ducks/{did}.png"], capture_output=True)
    if got.returncode == 0 and got.stdout:
        cur = Image.open(io.BytesIO(got.stdout)).convert("RGBA")
        head = subprocess.run(["git", "-C", str(ROOT), "show", "HEAD:art/ducks.json"], capture_output=True, text=True).stdout
        cb = json.loads(head)["ducks"].get(did, {}).get("body") or cur.width
    else:
        cur = Image.open(ROOT / "art" / "ducks" / f"{did}.png").convert("RGBA")
        cb = LIST[did].get("body") or cur.width
    masks, cols = [], []
    for im, b in ((img, body), (cur, cb)):
        small, _ = resized(im, b, 120)
        m = ia.measure(small, ia.BODY_UNITS, width=120)
        canvas = Image.new("RGBA", (300, 260), (0, 0, 0, 0))
        canvas.alpha_composite(small, (int(150 - m["baseX"]), int(240 - m["baseY"])))
        masks.append(canvas.getchannel("A").point(lambda v: 255 if v > 128 else 0))
        px = canvas.load()
        thirds = []
        for k in range(3):
            pts = [px[x, y] for y in range(k * 80, k * 80 + 90) for x in range(0, 300, 2) if px[x, y][3] > 200]
            thirds.append([statistics.mean(lab(p)[i] for p in pts) for i in range(3)] if pts else [0, 0, 0])
        cols.append(thirds)
    a1, a2 = masks[0].load(), masks[1].load()
    inter = sum(1 for y in range(260) for x in range(300) if a1[x, y] and a2[x, y])
    union = sum(1 for y in range(260) for x in range(300) if a1[x, y] or a2[x, y])
    dcol = statistics.mean(math.dist(c1, c2) for c1, c2 in zip(*cols))
    return inter / max(1, union), dcol


def duplicate(img, body, did):
    """Another duck whose picture this is, near enough: the same outline and the same colors (a file mix-up)."""
    mine = thumb(img, body)
    mp = mine.load()
    for other in committed():
        if other == did or other not in LIST:
            continue
        o_img = Image.open(ROOT / "art" / "ducks" / f"{other}.png").convert("RGBA")
        theirs = thumb(o_img, LIST[other].get("body") or o_img.width).load()
        inter = union = diff = n = 0
        for y in range(40):
            for x in range(40):
                a1, a2 = mp[x, y][3] > 128, theirs[x, y][3] > 128
                inter += a1 and a2
                union += a1 or a2
                if a1 and a2:
                    diff += sum(abs(mp[x, y][i] - theirs[x, y][i]) for i in range(3)) / 3
                    n += 1
        if union and inter / union > 0.97 and n and diff / n < 10:
            return other
    return None


def listed_problems(did, src):
    """What's missing from the duck's line in art/ducks.json, and (for a finished one) from what Dakku loads."""
    d = LIST.get(did)
    if d is None:
        return [f"{did} isn't in art/ducks.json"]
    out = [f"no {k} in art/ducks.json" for k in ("name", "kanji", "blurb", "color", "look") if not d.get(k)]
    if d.get("category", "dakku") not in ("dakku", "holiday", "anime", "games", "screen", "sanrio", "music"):
        out.append(f"unknown category {d.get('category')!r}")
    if d.get("category", "dakku") not in ("dakku", "holiday") and not d.get("series"):
        out.append("a character without its series")
    if d.get("face", "calm") not in duck.FACES:
        out.append(f"unknown face {d.get('face')!r}")
    if not src:
        manifest = json.loads((ROOT / "web" / "ducks" / "ducks.json").read_text())["kinds"]
        if did not in manifest:
            out.append("not in web/ducks/ducks.json (run duck.py publish)")
        for f in (f"{did}.webp", f"{did}.small.webp"):
            if not (ROOT / "web" / "ducks" / f).exists():
                out.append(f"web/ducks/{f} is missing")
        if f'"{did}"' not in (ROOT / "web" / "kinds.js").read_text():
            out.append("not in web/kinds.js")
    return out


COMPARE = {"sanrio": ["snoopy", "kirby"], "anime": ["naruto", "senku"], "games": ["link", "sonic"],
           "screen": ["snoopy", "godzilla"], "holiday": ["witch", "santa"], "dakku": ["sailor", "nurse"]}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    brief = "--brief" in sys.argv  # one line a duck, no pictures (for going over all of them)
    if "--all" in sys.argv:
        args = [d for d in LIST if (ROOT / "art" / "ducks" / f"{d}.png").exists()]
    targets = []
    for arg in args:
        did, _, src = arg.partition("=")
        targets.append((did, src or None))
    # each duck against every accepted one but itself (a new one isn't among them yet)
    everyone = population(set())
    report = []
    for did, src in targets:
        others = {k: v for k, v in everyone.items() if k != did}
        others.setdefault("shiro", everyone["shiro"])
        img, body, notes, dropped = finished(did, src)
        hidden = LIST.get(did, {}).get("eye") == "hidden"
        r, _ = metrics(did, img, body, hidden)
        flags, looks = [], []
        lines = [f"\n== {did}" + (f"  (from {Path(src).name})" if src else "  (finished picture)")]
        meds = {k: statistics.median([o[k] for o in others.values() if o.get(k) is not None]) for k in SIZE_KEYS}
        ratios = {k: r[k] / meds[k] for k in SIZE_KEYS if r.get(k)}
        factor = statistics.median(ratios.values()) if ratios else 1.0
        r["size_factor"] = factor
        scale = float(LIST.get(did, {}).get("scale", 1))
        line = (f"overall size {(factor - 1) * 100:+.1f}% against the others ("
                + ", ".join(f"{k} {(v - 1) * 100:+.0f}%" for k, v in ratios.items()) + ")")
        if abs(factor - 1) > SIZE_LIMIT:
            flags.append("size")
            line = f"  !! {line}   FLAG: it would look {'bigger' if factor > 1 else 'smaller'}: \"scale\": {scale / factor:.3f} fixes the size"
        else:
            line = "     " + line
        lines.append(line)
        # the proportions, once the size is taken out: what "scale" can't fix (a low head, a long body) needs a redraw
        for k in ("eye_y", "beak_y", "body_w"):
            if k in ratios:
                rel = ratios[k] / factor - 1
                if k == "body_w" and abs(rel) > 0.05:
                    looks.append(f"body {rel * 100:+.0f}% wide at the water for its size (a tail or cape there, or a small body? see the overlay)")
                elif abs(rel) > 0.05:
                    flags.append(f"shape:{k}")
                    lines.append(f"  !! {k} for its size: {rel * 100:+.0f}%   FLAG: {'a lower head' if k != 'body_w' and rel < 0 else 'a higher head' if k != 'body_w' else 'wider at the water (a tail or costume there? look)' if rel > 0 else 'narrower at the water'}; scale won't fix it")
        for name in ORDER:
            if name not in r and name not in ("eye_y", "eye_size", "head_top", "eye_over_beak"):
                continue
            if name in ("eye_y", "eye_size", "head_top", "eye_over_beak") and hidden:
                continue
            vals = [o.get(name) for o in others.values()]
            line, flag = judge(name, r.get(name), vals, others["shiro"].get(name) or 0)
            lines.append(("  !! " if flag else "     ") + line + (f"   {flag}" if flag and flag != "missing" else ""))
            if flag.startswith("LOOK"):
                looks.append(f"{name}: {flag[5:]}")
            elif flag:
                flags.append(name)
        face = LIST.get(did, {}).get("face", "calm")
        if r.get("face_marks") is not None and not hidden:
            if face == "calm" and r["face_marks"]:
                looks.append(f"{r['face_marks']} mark(s) near the eye on a calm face: an eyebrow, a mouth? (or whiskers, a strap)")
            if face == "angry" and not r["face_marks"]:
                looks.append("no eyebrow found near the eye on an angry face")
        if not hidden or True:
            wing = r.get("wing")
            if not r.get("wing_strokes"):
                looks.append("no wing line found on the body's lower back (covered by the outfit, or missing?)")
            elif wing:
                bx_, by_, wwid, whgt = wing
                odd = []
                if not 10 <= bx_ <= 24 or not 7 <= by_ <= 19:
                    odd.append(f"in an odd place ({bx_:.0f} behind, {by_:.0f} up; Shiro's 17, 15)")
                if not 9 <= wwid <= 22 or not 5 <= whgt <= 13:
                    odd.append(f"an odd size ({wwid:.0f} x {whgt:.0f}; Shiro's 17 x 11)")
                if odd:
                    flags.append("wing")
                    lines.append(f"  !! wing: its line is {' and '.join(odd)}   FLAG: not the plain duck's one short curved line")
                else:
                    lines.append(f"     wing          one line {wwid:.0f} x {whgt:.0f} at ({bx_:.0f}, {by_:.0f})   (Shiro's 17 x 11 at (17, 15))")
                if r["wing_strokes"] > 1:
                    looks.append(f"{r['wing_strokes']} strokes where the wing is: a second curl (a tail, a swirl) beside the wing line?")
        if r.get("white_lab") and others["shiro"].get("white_lab"):
            de = math.dist(r["white_lab"], others["shiro"]["white_lab"])
            line = f"white_de      {de:6.2f}   (the body's white against Shiro's cream; accepted 2.7 at most)"
            if de > WHITE_DE:
                flags.append("white")
                line = "  !! " + line[5:] + f"   FLAG its white isn't Dakku's cream (over {WHITE_DE})"
            else:
                line = "     " + line
            lines.append(line)
        if (src and (ROOT / "art" / "ducks" / f"{did}.png").exists()) or did in committed():
            iou, dcol = drift(img, body, did)
            line = f"drift         outline overlap with the committed picture {iou * 100:.0f}%, colors {dcol:.1f} apart"
            if iou < 0.86 or dcol > 9:
                looks.append(f"it changed more than a touch-up should (outline overlap {iou * 100:.0f}%, colors {dcol:.1f} apart): is the design the same?")
                line = "  !! " + line
            else:
                line = "     " + line
            lines.append(line)
        twin = duplicate(img, body, did)
        if twin:
            flags.append("duplicate")
            lines.append(f"  !! duplicate: the picture is all but the same as {twin}'s   FLAG the wrong picture?")
        for problem in listed_problems(did, src):
            flags.append("listing")
            lines.append(f"  !! {problem}   FLAG")
        if dropped is not None:
            lines.append(f"     dropped when cut out: {dropped * 100:.1f}% of the duck's area" + ("   FLAG: a part was left behind" if dropped > 0.015 else ""))
            if dropped > 0.015:
                flags.append("dropped")
        for n in notes:
            lines.append(f"     note: {n}")
        if brief:
            scale = float(LIST.get(did, {}).get("scale", 1))
            fix = f"  scale {scale:.3f} -> {scale / factor:.3f}" if "size" in flags else ""
            print(f"{did:12} size {(factor - 1) * 100:+5.1f}%  {'FLAGGED: ' + ', '.join(flags) if flags else 'ok'}{fix}"
                  + (f"   (look: {'; '.join(looks)})" if looks else ""))
            report.append({"id": did, "flags": flags, "looks": looks, "factor": factor, "m": r})
            continue
        compare = COMPARE.get(LIST.get(did, {}).get("category", "dakku"), ["sailor", "nurse"])
        shot = sheet(did, img, body, r, others, compare)
        lines.append(f"     picture: {shot}")
        for item in looks:
            lines.append(f"     look: {item}")
        lines.append(f"     verdict: {'FLAGGED: ' + ', '.join(flags) if flags else 'numbers pass; now look at the picture'}")
        print("\n".join(lines))
        report.append({"id": did, "flags": flags, "looks": looks, "factor": factor, "m": r})
    (OUT / "gate-last.json").write_text(json.dumps(report, indent=1))
    print("\nLook at each picture for what numbers can't catch: the duck's own wing is one short curved line (nothing "
          "raised or outlined, nothing held); no feet, arms or hands; the outline grainy like Shiro's, the colors laid in "
          "like pencil, not flat; the bottom round at both ends; it reaches Shiro's lines; floating parts (halo) kept; "
          "the outfit matches its look; no stray marks or cut edges.")


main()
