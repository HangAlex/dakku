#!/usr/bin/env python3
"""Brings the ducks painted with ChatGPT into Dakku.

Save ChatGPT's pictures in art/incoming/ (PNG, WebP or JPEG) with these names, then run, in Dakku's folder,
    python3 scripts/import_art.py
and reload Dakku. Any you haven't made yet keep their drawn placeholders.

    <duck id> one duck, like goku.png, for a duck in art/ducks.json (scripts/duck.py makes its prompt);
              it's finished and kept in art/ducks/, one picture per duck
    eggs      4 pictures: egg in its nest, a small crack, a big crack with eyes peeking, a cold egg
    pond-wide the pond the ducks float in (landscape)
    pond-tall the same kind of pond for phones (portrait; optional, the wide one is used otherwise)
    pond-spring-wide, pond-autumn-wide, pond-winter-wide, pond-night-wide, pond-garden-wide,
              pond-sakura-wide, pond-halloween-wide, pond-thanksgiving-wide, pond-christmas-wide
              more ponds to pick from (each with an optional -tall one too)
    deco-torii, deco-lantern, deco-koi, deco-lanterns, deco-lotus
              decorations to put on the pond's water (one picture each)
    ripples   3 ripple rings, left to right, that go under the floating ducks
    icon      the app icon (square)

Each sheet is cut into its separate pictures by their transparent background. A plain white
background is removed too, and so is a fake gray checkerboard painted in where transparency should be.
A pond is kept whole, with a map of its open water so Dakku only puts ducks where they can float.
"""
import base64
import hashlib
import json
import math
import os
import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
INCOMING = ROOT / "art" / "incoming"
OUT = ROOT / "web" / "ducks"
ICONS = ROOT / "web" / "icons"
SHEETS = {"eggs": ["egg-0", "egg-1", "egg-2", "cold"]}  # the ducks are one picture each: see scripts/duck.py
BODY_UNITS = 62   # a duck's body is this many units wide in Dakku's 100 × 120 box
EGG_UNITS = 62    # so is the nest (and the cold egg's lily pad)
MAX_HEIGHT = 512  # pixels kept per picture: plenty for phones, small enough to load fast
# Each duck also gets a small copy, which is all most screens need: the picker, the log, ponds and the
# gallery never show a duck's 100 × 120 box bigger than this many pixels (on a 3x phone). Dakku loads
# the small ones first, and a duck's full picture only for its own page, its hatching and share pictures.
SMALL_BOX = 220
RIPPLE_UNITS = 104  # a ripple ring is this wide in the duck's 100 × 120 box (its body is BODY_UNITS)
RIPPLES = 3
# each pond picture: (its theme, its shape, the widest kept); the plain pond-wide/-tall are the classic pond
THEMES = ("spring", "autumn", "winter", "night", "garden", "sakura", "halloween", "thanksgiving", "christmas")
PONDS = {"pond-wide": ("classic", "wide", 1600), "pond-tall": ("classic", "tall", 1100)}
for _theme in THEMES:
    PONDS[f"pond-{_theme}-wide"] = (_theme, "wide", 1600)
    PONDS[f"pond-{_theme}-tall"] = (_theme, "tall", 1100)
GRID = 100        # the water map is this many cells across (Dakku's pond is 1000 units wide)
POND_THUMB = 480  # pixels across a pond's thumbnail, for the pond pickers in Settings
DECOR = ("torii", "lantern", "koi", "lanterns", "lotus")  # each saved as deco-<id>
DECOR_WIDEST = 640  # pixels kept across a decoration
DECOR_SMALL = 360  # and across its small copy, which is what Dakku shows: no screen draws one wider than ~300


EXTS = (".png", ".webp", ".jpg", ".jpeg")


def find(stem):
    """The picture saved under this name, also as "ducks 7" or "ducks_7" for ducks-7."""
    for name in (stem, stem.replace("-", " "), stem.replace("-", "_")):
        for ext in EXTS:
            path = INCOMING / (name + ext)
            if path.exists():
                return path
    return None


def write(path, save):
    """Writes a file all at once, so Dakku never sees half a file: not while it's being written, not if
    the run is interrupted, and not if two runs overlap (each writes its own temporary file)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(f"{path.name}.{os.getpid()}.part")
    try:
        save(part)
        os.replace(part, path)
    finally:
        part.unlink(missing_ok=True)


def stamped(manifest):
    """The picture list with each picture's address ending in its version (?v= and a hash of the file), so
    a phone can keep a picture for good and still never show an old one: a new picture is a new address."""
    def walk(v):
        if isinstance(v, dict):
            return {k: (stamp(x) if k in ("src", "small", "thumb") and isinstance(x, str) else walk(x)) for k, x in v.items()}
        return [walk(x) for x in v] if isinstance(v, list) else v

    def stamp(src):
        path = src.split("?")[0]
        file = OUT / path.removeprefix("/ducks/")
        return f"{path}?v={hashlib.sha256(file.read_bytes()).hexdigest()[:10]}" if file.is_file() else path
    return walk(manifest)


def write_manifest(manifest):
    path = OUT / "ducks.json"
    text = json.dumps(stamped(manifest), ensure_ascii=False, indent=1)
    write(path, lambda part: part.write_text(text, encoding="utf-8"))


def webp(img, path, quality=90, method=5, alpha_quality=100):
    write(path, lambda part: img.save(part, "WEBP", quality=quality, method=method, alpha_quality=alpha_quality))


def save_small(source, name, entry):
    """The small copy of a duck's picture (see SMALL_BOX), next to the full one `entry` describes, made
    from `source` (the same picture, at any size): it's added to `entry`."""
    k = min(1.0, SMALL_BOX * entry["unit"] / 100)
    if k > 0.9:  # hardly smaller: the full picture will do
        return entry
    small = source.resize((max(1, round(entry["w"] * k)), max(1, round(entry["h"] * k))), Image.LANCZOS)
    webp(small, OUT / f"{name}.small.webp", quality=85, method=6)
    return {**entry, "small": f"/ducks/{name}.small.webp"}


def with_alpha(img):
    """The picture with a real alpha channel; a plain background color is made transparent."""
    img = img.convert("RGBA")
    lo, _ = img.getchannel("A").getextrema()
    if lo < 250:
        # drop the faint glow some pictures come with, so it can't join neighbors or leave a fuzzy rim
        img.putalpha(img.getchannel("A").point(lambda v: 0 if v < 24 else v))
        return img
    w, h = img.size
    px = img.load()
    # a fake transparent background: a checkerboard of two grays, painted in
    border = [px[x, y][:3] for x in range(0, w, 2) for y in (0, h - 1)] + [px[x, y][:3] for y in range(0, h, 2) for x in (0, w - 1)]
    grays = sorted(sum(c) / 3 for c in border if max(c) - min(c) < 14)
    if len(grays) > 0.9 * len(border) and grays[int(len(grays) * 0.85)] - grays[int(len(grays) * 0.15)] > 25:
        return without_checkerboard(img, grays[int(len(grays) * 0.15)], grays[int(len(grays) * 0.85)])
    bg = px[0, 0]
    close = lambda p: max(abs(p[0] - bg[0]), abs(p[1] - bg[1]), abs(p[2] - bg[2])) < 18  # noqa: E731
    seen = bytearray(w * h)
    q = deque((x, y) for x in range(w) for y in (0, h - 1))
    q.extend((x, y) for y in range(h) for x in (0, w - 1))
    while q:
        x, y = q.popleft()
        i = y * w + x
        if seen[i] or not close(px[x, y]):
            continue
        seen[i] = 1
        px[x, y] = (0, 0, 0, 0)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx]:
                q.append((nx, ny))
    return img


def without_checkerboard(img, dark, light):
    """Clears a painted-in checkerboard: every patch of flat gray made of both its grays, wherever it
    is (also the gaps inside a drawing, like a key's teeth). The drawings are ringed by dark outlines,
    and a silver sword is one gray, so nothing of theirs goes. Then any lone specks left over go too."""
    w, h = img.size
    px = img.load()
    grayish = lambda c: max(c[:3]) - min(c[:3]) < 14 and dark - 30 <= sum(c[:3]) / 3 <= light + 25  # noqa: E731
    seen = bytearray(w * h)
    for sy in range(h):
        for sx in range(w):
            if seen[sy * w + sx] or not grayish(px[sx, sy]):
                continue
            part, q = [], deque([(sx, sy)])
            seen[sy * w + sx] = 1
            while q:
                x, y = q.popleft()
                part.append((x, y))
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx] and grayish(px[nx, ny]):
                        seen[ny * w + nx] = 1
                        q.append((nx, ny))
            levels = [sum(px[x, y][:3]) / 3 for x, y in part]
            if len(part) >= 40 and sum(abs(v - light) < 22 for v in levels) >= 0.2 * len(part) and sum(abs(v - dark) < 22 for v in levels) >= 0.2 * len(part):
                for x, y in part:
                    px[x, y] = (0, 0, 0, 0)
    a = img.getchannel("A").load()
    seen = bytearray(w * h)
    for sy in range(h):
        for sx in range(w):
            if seen[sy * w + sx] or not a[sx, sy]:
                continue
            part, q = [], deque([(sx, sy)])
            seen[sy * w + sx] = 1
            while q:
                x, y = q.popleft()
                part.append((x, y))
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx] and a[nx, ny]:
                        seen[ny * w + nx] = 1
                        q.append((nx, ny))
            if len(part) < 30:
                for x, y in part:
                    px[x, y] = (0, 0, 0, 0)
    return img


def pieces(img, count):
    """The `count` biggest separate pictures on a sheet, left to right."""
    w, h = img.size
    a = img.getchannel("A").load()
    label = [0] * (w * h)
    found, n = [], 0
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if label[i] or a[x, y] <= 8:
                continue
            n += 1
            label[i] = n
            q = deque([i])
            x0 = x1 = x
            y0 = y1 = y
            size = 0
            while q:
                j = q.popleft()
                size += 1
                cx, cy = j % w, j // w
                x0, x1, y0, y1 = min(x0, cx), max(x1, cx), min(y0, cy), max(y1, cy)
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < w and 0 <= ny < h:
                        k = ny * w + nx
                        if not label[k] and a[nx, ny] > 8:
                            label[k] = n
                            q.append(k)
            found.append((size, n, x0, y0, x1, y1))
    biggest = sorted(found, reverse=True)[:count]
    if len(biggest) < count or biggest[-1][0] < biggest[0][0] * 0.04:
        return None
    out = []
    src = img.load()
    for size, lab, x0, y0, x1, y1 in sorted(biggest, key=lambda p: p[2]):
        # keep this picture's own pixels, plus any small bits (a sparkle, a hair tip) that sit inside its box
        small = {p[1] for p in found if p[0] < size * 0.02 and x0 <= p[2] and p[4] <= x1 and y0 <= p[3] and p[5] <= y1}
        keep = small | {lab}
        piece = Image.new("RGBA", (x1 - x0 + 1, y1 - y0 + 1), (0, 0, 0, 0))
        dst = piece.load()
        for y in range(y0, y1 + 1):
            row = y * w
            for x in range(x0, x1 + 1):
                if label[row + x] in keep:
                    dst[x - x0, y - y0] = src[x, y]
        out.append(piece)
    return out


def touching(img, count):
    """pieces() for a sheet whose neighbors touch (a strand of hair across the gap): cut it into
    `count` slabs at the emptiest column near each gap (the ducks are evenly spaced), then keep
    each slab's own duck."""
    w, h = img.size
    a = img.getchannel("A").load()
    filled = [sum(1 for y in range(0, h, 2) if a[x, y] > 8) for x in range(w)]
    used = [x for x in range(w) if filled[x]]
    if not used:
        return None
    left, right = used[0], used[-1]
    step = (right - left) / count
    cuts = [left]
    for i in range(1, count):
        mid = left + step * i
        near = range(int(mid - step * 0.3), int(mid + step * 0.3) + 1)
        cuts.append(min(near, key=lambda x: (filled[x], abs(x - mid))))
    cuts.append(right + 1)
    out = []
    for x0, x1 in zip(cuts, cuts[1:]):
        found = pieces(img.crop((x0, 0, x1, h)), 1)
        if not found:
            return None
        out.append(found[0])
    return out


def columns(img, count):
    """The `count` pictures on a sheet laid out in a row, split at the widest empty gaps between
    them. Unlike pieces(), this keeps together a picture made of separate strokes, like a ripple."""
    w, h = img.size
    a = img.getchannel("A").load()
    used = [any(a[x, y] > 8 for y in range(0, h, 2)) for x in range(w)]
    runs, x = [], 0
    while x < w:
        if used[x]:
            start = x
            while x < w and used[x]:
                x += 1
            runs.append([start, x])
        else:
            x += 1
    if len(runs) < count:
        return None
    gaps = sorted(range(len(runs) - 1), key=lambda i: runs[i + 1][0] - runs[i][1], reverse=True)[:count - 1]
    cuts = sorted(gaps)
    groups, first = [], 0
    for i in cuts + [len(runs) - 1]:
        groups.append((runs[first][0], runs[i][1]))
        first = i + 1
    out = []
    for x0, x1 in groups:
        part = img.crop((x0, 0, x1, h))
        box = part.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
        if not box:
            return None
        out.append(part.crop(box))
    widths = [p.width for p in out]
    return out if min(widths) > max(widths) * 0.3 else None


def save_ripple(piece, name):
    """A ripple ring: centered on its picture, and scaled so it's RIPPLE_UNITS wide."""
    scale = min(1.0, 600 / piece.width)
    if scale < 1:
        piece = piece.resize((round(piece.width * scale), round(piece.height * scale)), Image.LANCZOS)
    box = piece.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox() or (0, 0, piece.width, piece.height)
    webp(piece, OUT / f"{name}.webp")
    return {"src": f"/ducks/{name}.webp", "w": piece.width, "h": piece.height,
            "cx": round((box[0] + box[2]) / 2, 1), "cy": round((box[1] + box[3]) / 2, 1), "unit": round(RIPPLE_UNITS / max(1, box[2] - box[0]), 5)}


def measure(piece, units, body=True, width=None):
    """Where the picture touches the water, and how many Dakku units one of its pixels is (from its
    body's width, unless `width` says what that is)."""
    w, h = piece.size
    a = piece.getchannel("A").load()
    rows = [y for y in range(h) if any(a[x, y] > 128 for x in range(0, w, 2))]
    bottom = rows[-1]
    base = [x for y in range(max(0, bottom - h // 25), bottom + 1) for x in range(w) if a[x, y] > 128]
    band = range(int(h * 0.55), int(h * 0.95)) if body else range(h)
    widths = []
    for y in band:
        xs = [x for x in range(w) if a[x, y] > 128]
        if xs:
            widths.append(xs[-1] - xs[0])
    width = width or (sorted(widths)[int(len(widths) * 0.9)] if widths else w)
    return {"baseX": sum(base) / len(base), "baseY": bottom, "unit": units / max(1, width)}


def body_widths(found, units):
    """Each duck's body width on a sheet. Every body on a sheet is drawn the same size, so one that
    measures much wider (long hair falling behind it, a cape) is taken to be the usual width."""
    widths = [units / measure(p, units)["unit"] for p in found]
    usual = sorted(widths)[(len(widths) - 1) // 2]
    return [usual if w > usual * 1.04 else w for w in widths]


def save(piece, name, units, body=True, width=None):
    m = measure(piece, units, body, width)
    scale = min(1.0, MAX_HEIGHT / piece.height)
    if scale < 1:
        piece = piece.resize((round(piece.width * scale), round(piece.height * scale)), Image.LANCZOS)
        m = {"baseX": m["baseX"] * scale, "baseY": m["baseY"] * scale, "unit": m["unit"] / scale}
    webp(piece, OUT / f"{name}.webp")
    return {"src": f"/ducks/{name}.webp", "w": piece.width, "h": piece.height,
            "baseX": round(m["baseX"], 1), "baseY": round(m["baseY"], 1), "unit": round(m["unit"], 5)}


def water_map(img):
    """Where ducks can float on a pond picture: each grid cell's distance to the shore (or to a lily
    pad), and how high the picture reaches in each column. None if no open water can be found."""
    work = img.resize((400, max(1, round(img.height * 400 / img.width))), Image.LANCZOS)
    px = work.load()
    # the water is one of the commonest bluish colors in the picture: light by day, dark at night.
    # A night pond's dark banks can be bluish too, so the few commonest are tried, and the one that
    # makes the most open water wins (a bank is a thin ring; the water is wide open).
    bins = {}
    for y in range(work.height):
        for x in range(work.width):
            r, g, b, a = px[x, y]
            if a > 200 and b > r + 12 and b >= g - 4 and r + g + b > 60:
                bins.setdefault((r >> 4, g >> 4, b >> 4), []).append((r, g, b))
    if not bins:
        return None
    common = sorted(bins.values(), key=len, reverse=True)
    tried = []
    for colors in common[:4]:
        if len(colors) * 10 < len(common[0]):
            break
        ref = [sum(c[i] for c in colors) / len(colors) for i in range(3)]
        found, openness, inside = water_of(work, ref)
        if found:
            tried.append((inside, openness, found))
    # water sits inside its bank: a color reaching the picture's edge is the bank, or land around the pond
    tried.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return tried[0][2] if tried else None


def water_of(work, ref):
    """The water map for one guess at the water's color, how much open water it makes, and whether
    the water stays inside the picture (True), as a pond's does, or reaches its edge."""
    w, h = work.size
    px = work.load()
    mask = Image.new("L", (w, h), 0)
    m = mask.load()
    near = min(40, max(16, 0.3 * max(ref)))  # dark colors sit closer together: a night pond's banks too
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a > 200 and max(abs(r - ref[0]), abs(g - ref[1]), abs(b - ref[2])) < near:
                m[x, y] = 255
    # fill in the ripple dashes and highlights drawn on the water (lily pads are too big to fill)
    mask = mask.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
    m = mask.load()
    # keep only the main body of water
    seen = bytearray(w * h)
    best = []
    for sy in range(h):
        for sx in range(w):
            if seen[sy * w + sx] or not m[sx, sy]:
                continue
            seen[sy * w + sx] = 1
            part, q = [], deque([(sx, sy)])
            while q:
                x, y = q.popleft()
                part.append((x, y))
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx] and m[nx, ny]:
                        seen[ny * w + nx] = 1
                        q.append((nx, ny))
            if len(part) > len(best):
                best = part
    water = bytearray(w * h)
    for x, y in best:
        water[y * w + x] = 1
    # a grid cell is water when nearly all of it is
    size = w / GRID
    rows = math.ceil(h / size)
    cells = []
    for r in range(rows):
        for c in range(GRID):
            xs = range(int(c * size), min(w, int((c + 1) * size)))
            ys = range(int(r * size), min(h, int((r + 1) * size)))
            total = len(xs) * len(ys)
            wet = sum(water[y * w + x] for y in ys for x in xs)
            cells.append(1 if total and wet >= 0.8 * total else 0)
    # each cell's distance to the nearest dry cell (off the grid counts as dry), in cells
    INF = 1e9
    d = [INF if v else 0.0 for v in cells]
    at = lambda r, c: d[r * GRID + c] if 0 <= r < rows and 0 <= c < GRID else 0.0  # noqa: E731
    diag = math.sqrt(2)
    for r in range(rows):
        for c in range(GRID):
            i = r * GRID + c
            if d[i]:
                d[i] = min(d[i], at(r, c - 1) + 1, at(r - 1, c) + 1, at(r - 1, c - 1) + diag, at(r - 1, c + 1) + diag)
    for r in range(rows - 1, -1, -1):
        for c in range(GRID - 1, -1, -1):
            i = r * GRID + c
            if d[i]:
                d[i] = min(d[i], at(r, c + 1) + 1, at(r + 1, c) + 1, at(r + 1, c + 1) + diag, at(r + 1, c - 1) + diag)
    unit = 1000 / GRID  # pond units per cell
    # stored in steps of 2 units, measured from the cell's center; 0 means no water
    dist = bytes(0 if not v else max(1, min(255, round((v - 0.5) * unit / 2))) for v in d)
    if not any(dist):
        return None, 0, False
    alpha = work.getchannel("A").load()
    tops = []
    for c in range(GRID):
        xs = range(int(c * size), min(w, int((c + 1) * size)))
        y = next((y for y in range(h) if any(alpha[x, y] > 128 for x in xs)), h)
        tops.append(round(y * 1000 / w))
    openness = sum(min(v, 8) for v in d)  # open water counts, a thin ring of bank hardly does
    # how much of the water's edge is right by the picture's transparent outside (or its border)
    outside = work.getchannel("A").point(lambda v: 255 if v <= 200 else 0).filter(ImageFilter.MaxFilter(9)).load()
    edge = out = 0
    for x, y in best:
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not (0 <= nx < w and 0 <= ny < h) or not water[ny * w + nx]:
                edge += 1
                out += not (0 <= nx < w and 0 <= ny < h) or outside[nx, ny] > 0
                break
    inside = out < 0.25 * edge
    return {"cols": GRID, "rows": rows, "dist": base64.b64encode(dist).decode(), "top": tops}, openness, inside


def save_pond(path, name, widest):
    img = with_alpha(Image.open(path))
    box = img.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    if not box:
        return None
    img = img.crop(box)
    if img.width > widest:
        img = img.resize((widest, round(img.height * widest / img.width)), Image.LANCZOS)
    found = water_map(img)
    if not found:
        return None
    webp(img, OUT / f"pond-{name}.webp", quality=88)
    return {"src": f"/ducks/pond-{name}.webp", "w": img.width, "h": img.height, **found, "thumb": pond_thumb(img, name)}


def pond_thumb(img, name):
    """A pond's thumbnail (see POND_THUMB): its address."""
    thumb = img.resize((POND_THUMB, round(img.height * POND_THUMB / img.width)), Image.LANCZOS)
    webp(thumb, OUT / f"pond-{name}.thumb.webp", quality=78, method=6, alpha_quality=60)  # (its edge is soft anyway)
    return f"/ducks/pond-{name}.thumb.webp"


def save_decor(path, name):
    """A decoration, trimmed to what's drawn and kept whole."""
    img = with_alpha(Image.open(path))
    box = img.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    if not box:
        return None
    img = img.crop(box)
    if img.width > DECOR_WIDEST:
        img = img.resize((DECOR_WIDEST, round(img.height * DECOR_WIDEST / img.width)), Image.LANCZOS)
    webp(img, OUT / f"deco-{name}.webp")
    return decor_small(img, name, {"src": f"/ducks/deco-{name}.webp", "w": img.width, "h": img.height})


def decor_small(img, name, entry):
    """A decoration's small copy (see DECOR_SMALL), added to its `entry`."""
    if img.width <= DECOR_SMALL * 1.1:
        return entry
    small = img.resize((DECOR_SMALL, round(img.height * DECOR_SMALL / img.width)), Image.LANCZOS)
    webp(small, OUT / f"deco-{name}.small.webp", quality=85, method=6)
    return {**entry, "small": f"/ducks/deco-{name}.small.webp"}


def icons(path):
    img = Image.open(path).convert("RGB")
    side = min(img.size)
    left, top = (img.width - side) // 2, (img.height - side) // 2
    img = img.crop((left, top, left + side, top + side))
    for name, size in (("icon-512.png", 512), ("icon-192.png", 192), ("apple-touch-icon.png", 180), ("favicon.png", 64)):
        small = img.resize((size, size), Image.LANCZOS)
        write(ICONS / name, lambda part: small.save(part, "PNG", optimize=True))
    pad = Image.new("RGB", (512, 512), img.getpixel((2, 2)))  # Android crops to a circle: leave a margin
    pad.paste(img.resize((400, 400), Image.LANCZOS), (56, 56))
    write(ICONS / "maskable-512.png", lambda part: pad.save(part, "PNG", optimize=True))


def main():
    manifest_path = OUT / "ducks.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"kinds": {}, "eggs": [None, None, None], "cold": None}
    did = 0
    say = lambda line: print(line, flush=True)  # noqa: E731  (as it goes, so a slow step doesn't look stuck)
    say(f"Importing from {INCOMING}:")
    for stem, names in SHEETS.items():
        path = find(stem)
        if not path:
            continue
        sheet = with_alpha(Image.open(path))
        found = pieces(sheet, len(names)) or touching(sheet, len(names))
        if not found:
            say(f"  {path.name}: couldn't find {len(names)} separate pictures. Ask ChatGPT for a transparent background with space between them.")
            continue
        widths = body_widths(found, BODY_UNITS) if not stem == "eggs" else [None] * len(found)
        for name, piece, width in zip(names, found, widths):
            if name.startswith("egg-"):
                manifest["eggs"][int(name[-1])] = save(piece, name, EGG_UNITS, body=False)
            elif name == "cold":
                manifest["cold"] = save(piece, name, EGG_UNITS * 0.85, body=False)
            else:
                manifest["kinds"][name] = save(piece, name, BODY_UNITS, width=width)
        say(f"  {path.name} → {', '.join(names)}")
        did += 1
    path = find("ripples")
    if path:
        found = columns(with_alpha(Image.open(path)), RIPPLES)
        if found:
            manifest["ripples"] = [save_ripple(piece, f"ripple-{i + 1}") for i, piece in enumerate(found)]
            say(f"  {path.name} → {RIPPLES} ripple rings")
            did += 1
        else:
            say(f"  {path.name}: couldn't find {RIPPLES} ripple rings in a row. Ask ChatGPT for clear space between them.")
    ponds = manifest.get("ponds") or {}
    if "wide" in ponds or "tall" in ponds:  # the first ponds were just the classic one
        ponds = {"classic": ponds}
    for stem, (theme, shape, widest) in PONDS.items():
        path = find(stem)
        if not path:
            continue
        found = save_pond(path, shape if theme == "classic" else f"{theme}-{shape}", widest)
        if not found:
            say(f"  {path.name}: couldn't find the pond's water. Ask ChatGPT for flat blue water and a transparent background.")
            continue
        ponds.setdefault(theme, {})[shape] = found
        say(f"  {path.name} → the {theme} pond ({shape})")
        did += 1
    manifest["ponds"] = ponds
    decor = manifest.get("decor") or {}
    for name in DECOR:
        path = find(f"deco-{name}")
        if not path:
            continue
        found = save_decor(path, name)
        if not found:
            say(f"  {path.name}: it's empty. Ask ChatGPT for the decoration on a transparent background.")
            continue
        decor[name] = found
        say(f"  {path.name} → the {name} decoration")
        did += 1
    manifest["decor"] = decor
    icon = find("icon")
    if icon:
        icons(icon)
        say(f"  {icon.name} → app icons")
        did += 1
    manifest["eggs"] = (manifest.get("eggs") or [None, None, None])[:3]
    write_manifest(manifest)
    # the ducks: new ones from art/incoming, then every duck in art/ducks into Dakku (it adds them to the
    # list just written)
    import duck  # noqa: PLC0415  (it uses this file's helpers)
    did += duck.incoming(say)
    ducks = duck.publish(say)
    # ChatGPT names its downloads with long random ids: those can't be told apart, so say so
    known = set(SHEETS) | set(PONDS) | {f"deco-{d}" for d in DECOR} | {"ripples", "icon"} | set(duck.load())
    unnamed = sorted(p.name for p in INCOMING.glob("*") if p.suffix.lower() in EXTS
                     and p.stem.replace(" ", "-").replace("_", "-") not in known
                     and p.stem.lower().replace(" ", "").replace("_", "").replace("-", "") not in known) if INCOMING.exists() else []
    if unnamed:
        say("Not imported, because their names don't say what they are: " + ", ".join(unnamed))
        say("  Rename each one to what it shows (ripples.png, pond-wide.png, a duck's id like goku.png, …) and run this again.")
    if not did and not ducks:
        say(f"Nothing imported: save ChatGPT's pictures in {INCOMING}, named as listed at the top of this script.")
        return 1
    say("Done. Reload Dakku to see them. (On iPhone, a new icon needs Dakku re-added to the Home Screen.)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
