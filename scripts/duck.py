#!/usr/bin/env python3
"""The duck maker: every duck in Dakku, one picture each, all in the same style.

The ducks live in two places, and this keeps them in step:
    art/ducks.json        the list: each duck's name, kanji, color, blurb, face and outfit (and "eye": "hidden"
                          for one whose outfit covers the eye on purpose, so the checks don't look for it)
    art/ducks/<id>.png    its picture, finished: transparent, facing left, beak in Dakku's peach

Making a new duck:
    1. python3 scripts/duck.py new goku "spiky black hair and an orange gi with a blue belt" --name Goku --kanji 悟
       adds it to the list and prints the exact prompt for ChatGPT (also saved in art/prompts/goku.txt)
    2. In ChatGPT, start a new chat in the "Dakku ducks" project (it has the style rules), pick
       Create image, attach art/reference.png (+ → Add from library, once it's been uploaded), paste
       the prompt, and save the picture as art/incoming/goku.png
    3. python3 scripts/import_art.py   (or: python3 scripts/duck.py add goku)
       finishes the picture (background, facing, beak color, size), checks it (a body drawn flatter than
       the others' is flagged, to be redrawn), puts it in Dakku and makes art/review/goku.png to look at.

Other commands:
    duck.py list                 every duck, and whether it has its picture
    duck.py prompt <id>          the prompt again (to remake a duck)
    duck.py check                checks every duck's picture against Dakku's style
    duck.py review [<id> ...]    a picture of the ducks side by side, at the size Dakku draws them
    duck.py reference            remakes art/reference.png, the style picture for ChatGPT
    duck.py publish              puts every duck in art/ducks into Dakku (import_art.py does this too)
    duck.py remove <id>          takes a duck out (its sessions then show as a plain duck)
"""
import argparse
import colorsys
import json
import math
import re
import shutil
import sys
from collections import deque
from pathlib import Path
from statistics import median

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_art as ia  # noqa: E402  (the picture helpers: cutting, backgrounds, sizing, saving)

ROOT = ia.ROOT
LIST = ROOT / "art" / "ducks.json"
PICTURES = ROOT / "art" / "ducks"
INCOMING = ia.INCOMING
ORIGINALS = ROOT / "art" / "originals"  # ChatGPT's pictures as they came, before finishing
PROMPTS = ROOT / "art" / "prompts"
REVIEW = ROOT / "art" / "review"
REFERENCE = ROOT / "art" / "reference.png"
KINDS_JS = ROOT / "web" / "kinds.js"
ID_RE = re.compile(r"^[a-z][a-z0-9]{1,23}$")
# Dakku's own first ten ducks: always there (drawn from shapes until they have pictures), never removed
BUILT_IN = ("shiro", "sailor", "neko", "super", "ninja", "kitsune", "yukata", "samurai", "king", "astro")
OLD_NAMES = ("matsu", "take", "sakura", "momiji", "icho", "sugi", "ume")  # the trees from before: taken
# The look every duck shares, measured on the first ten: the beak's color (hue, saturation, value)
# and the outline's. A beak that's off is brought back to this; the outline is only checked.
BEAK = (31.5 / 360, 0.515, 0.985)
OUTLINE = (52, 44, 38)
BEAK_TOLERANCE = (4 / 360, 0.05, 0.04)
# How high the eye sits over the water, in body widths, on the first ducks. ChatGPT sometimes draws
# the body lower and longer, which makes a duck look short next to the others. One whose eye sits
# lower than FLAT is flagged, to be redrawn: stretching the picture to fix it looks odd. The width
# here comes from the beak, which ChatGPT draws the same size on every duck (BEAK_TO_BODY: the beak's
# side, the square root of its area, to the body's width on the first ducks), because long hair, a
# ponytail or a sword can make the outline measure far wider than the body.
EYE_HEIGHT = 0.69
FLAT = 0.62
BEAK_TO_BODY = 0.134
REFERENCE_DUCKS = ("shiro", "super", "neko", "shizuku", "nurse", "naruto")  # soft outlines, hair, hoods, outfits


# ── the list ─────────────────────────────────────────────────────────────────
def load():
    if not LIST.exists():
        return {}
    return json.loads(LIST.read_text(encoding="utf-8")).get("ducks", {})


def store(ducks):
    text = json.dumps({"ducks": ducks}, ensure_ascii=False, indent=1)
    ia.write(LIST, lambda part: Path(part).write_text(text + "\n", encoding="utf-8"))


def hex_of(rgb):
    return "#" + "".join(f"{round(c):02X}" for c in rgb)


def beak_hex():
    return hex_of(c * 255 for c in colorsys.hsv_to_rgb(*BEAK))


# ── finding the face ─────────────────────────────────────────────────────────
def components(mask, w, h, min_size=1):
    seen = bytearray(w * h)
    for i in range(w * h):
        if not mask[i] or seen[i]:
            continue
        part, q = [], deque([i])
        seen[i] = 1
        while q:
            j = q.popleft()
            part.append(j)
            x, y = j % w, j // w
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                k = ny * w + nx
                if 0 <= nx < w and 0 <= ny < h and mask[k] and not seen[k]:
                    seen[k] = 1
                    q.append(k)
        if len(part) >= min_size:
            yield part


def find_eye(img, body):
    """The eye: a small, solid, roundish dark dot on the white face. Thin dark strokes (outlines, an
    angry eyebrow touching the eye) are worn away first, so only the dot's round core is left."""
    w, h = img.size
    px = img.load()
    dark = Image.new("L", (w, h), 0)
    d = dark.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a > 200 and max(r, g, b) < 90:
                d[x, y] = 255
    wear = max(1, round(body * 0.012))  # about a third of the dot's radius
    core = dark.filter(ImageFilter.MinFilter(2 * wear + 1)).load()
    mask = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            if core[x, y]:
                mask[y * w + x] = 1
    best = None
    for part in components(mask, w, h, max(4, int((0.012 * body) ** 2))):
        if len(part) > (0.13 * body) ** 2:
            continue
        xs = [j % w for j in part]
        ys = [j // w for j in part]
        bw, bh = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
        if not 0.5 < bw / bh < 2 or len(part) < 0.5 * bw * bh:
            continue
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        r0 = max(bw, bh) / 2 + wear  # the dot's own radius, before it was worn away
        ring = white = 0
        for k in range(48):
            ang = 2 * math.pi * k / 48
            for dd in (r0 + 3, r0 + 6):
                x, y = int(cx + dd * math.cos(ang)), int(cy + dd * math.sin(ang))
                if 0 <= x < w and 0 <= y < h:
                    ring += 1
                    q = px[x, y]
                    white += q[3] > 200 and min(q[:3]) > 215
        share = white / max(1, ring)
        if share > 0.4 and (best is None or share > best[0]):
            best = (share, cx, cy, 2 * r0)
    return best and {"x": best[1], "y": best[2], "size": best[3]}


def beakish(p):
    r, g, b, a = p
    if a <= 200:
        return False
    hh, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return 0.045 < hh < 0.105 and s > 0.28 and v > 0.7  # peach to orange: not red, not blond


def find_beak(img, body, eye):
    """The beak: the biggest-enough peach-to-orange patch nearest the eye. A beak is pale, so a pale
    patch wins over darker golden-brown ones (Link's hair sits as close to his eye as his beak does).
    Returns its pixels, or None."""
    w, h = img.size
    px = img.load()
    mask = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            if beakish(px[x, y]):
                mask[y * w + x] = 1
    best = None
    for part in components(mask, w, h, int((0.09 * body) ** 2)):  # a beak is at least this big
        xs = [j % w for j in part]
        ys = [j // w for j in part]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        if abs(cy - eye["y"]) > 0.4 * body or abs(cx - eye["x"]) > 0.6 * body:
            continue
        pale = median(colorsys.rgb_to_hsv(*(c / 255 for c in px[j % w, j // w][:3]))[2] for j in part[::7]) > 0.9
        rank = (not pale, math.hypot(cx - eye["x"], cy - eye["y"]))
        if best is None or rank < best[0]:
            best = (rank, part)
    return best and [(j % w, j // w) for j in best[1]]


def hsv_median(img, points):
    px = img.load()
    hsv = [colorsys.rgb_to_hsv(*(c / 255 for c in px[x, y][:3])) for x, y in points]
    return tuple(median(t[i] for t in hsv) for i in range(3))


def match_beak(img, beak):
    """Brings the beak to Dakku's peach, keeping the picture's own shading and crayon grain (each pixel
    moves by the same amount). Its soft edge comes along. Returns (before, after) as HSV."""
    before = hsv_median(img, beak)
    dh = BEAK[0] - before[0]
    ks, kv = BEAK[1] / max(0.01, before[1]), BEAK[2] / max(0.01, before[2])
    w, h = img.size
    px = img.load()
    inside = set(beak)
    edge = set()
    for x, y in beak:
        for nx in range(x - 2, x + 3):
            for ny in range(y - 2, y + 3):
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in inside:
                    edge.add((nx, ny))
    for (x, y), full in [(p, True) for p in inside] + [(p, False) for p in edge]:
        r, g, b, a = px[x, y]
        if a == 0:
            continue
        hh, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if not full and not (0.03 < hh < 0.12 and s > 0.15):  # the soft edge: only where it's beak-colored
            continue
        hh, s = (hh + dh) % 1, min(1, s * ks)
        if full:
            v = min(1, v * kv)
        r, g, b = colorsys.hsv_to_rgb(hh, s, v)
        px[x, y] = (round(r * 255), round(g * 255), round(b * 255), a)
    return before, hsv_median(img, beak)


def outline_tone(img):
    """The usual color of the outline around the duck: dark pixels just inside its silhouette."""
    w, h = img.size
    px = img.load()
    found = []
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b, a = px[x, y]
            if a < 250 or max(r, g, b) > 110:
                continue
            if any(0 <= nx < w and 0 <= ny < h and px[nx, ny][3] < 40 for nx, ny in ((x + 3, y), (x - 3, y), (x, y + 3), (x, y - 3))):
                found.append((r, g, b))
    return tuple(round(median(c[i] for c in found)) for i in range(3)) if found else None


def off(hsv):
    return abs(hsv[0] - BEAK[0]) > BEAK_TOLERANCE[0] or abs(hsv[1] - BEAK[1]) > BEAK_TOLERANCE[1] or abs(hsv[2] - BEAK[2]) > BEAK_TOLERANCE[2]


def describe(hsv):
    return f"{hex_of(c * 255 for c in colorsys.hsv_to_rgb(*hsv))} (hue {hsv[0] * 360:.0f}°, saturation {hsv[1] * 100:.0f}%)"


# ── finishing a picture ──────────────────────────────────────────────────────
def face(img, body):
    """Its eye and beak. When the outline measures far wider than the body (long hair, a ponytail,
    something it carries), the eye's dot looks too small to be one, so if no eye turns up it's
    looked for again as if the body were smaller."""
    for f in (1, 0.8, 0.65, 0.5):
        eye = find_eye(img, body * f)
        if eye:
            return eye, find_beak(img, body * f, eye)
    return None, None


def body_from_beak(beak):
    return math.sqrt(len(beak)) / BEAK_TO_BODY


def eye_height(img, eye, beak):
    """How high its eye sits over the water, in body widths as its beak gives them (Dakku's ducks:
    about 0.69)."""
    return (ia.measure(img, ia.BODY_UNITS)["baseY"] - eye["y"]) / body_from_beak(beak)


def finish(img, body=None, notes=None, hidden_eye=False):
    """A duck picture made ready for Dakku: cut out, facing left, with the beak in Dakku's peach.
    Returns (picture, facts). `body` is its body width when already known (from a sheet). `hidden_eye`:
    its outfit covers the eye on purpose ("eye": "hidden" in the list), so no eye is looked for."""
    notes = notes if notes is not None else []
    img = img.convert("RGBA")
    measured = body is None
    if measured:
        body = ia.BODY_UNITS / ia.measure(img, ia.BODY_UNITS)["unit"]
    eye, beak = face(img, body)
    if eye and beak and sum(x for x, _ in beak) / len(beak) > eye["x"]:
        # the beak is behind the eye: it faces right. Dakku's ducks face left, so it's turned round.
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
        notes.append("it faced right, so it was turned to face left")
        eye, beak = face(img, body)
    if measured and beak and body > 1.06 * body_from_beak(beak):
        # hair or something it carries made the outline wider than the body: that would make it small
        notes.append(f"its outline measures wider than its body (hair, or something it carries), so it's sized from its "
                     f"beak ({body:.0f} → {1.06 * body_from_beak(beak):.0f}px across)")
        body = 1.06 * body_from_beak(beak)
        eye, beak = face(img, body)
    facts = {"body": round(body), "eye": bool(eye), "beak": bool(beak), "problems": []}

    def problem(text):
        notes.append(text)
        facts["problems"].append(text)

    up = eye_height(img, eye, beak) if eye and beak and not hidden_eye else None
    if up is not None:
        facts["eye_height"] = round(up, 2)
        if up < FLAT:
            problem(f"its body is drawn lower and longer than Dakku's ducks (the eye {up:.2f} body widths over the water, "
                    f"usually {EYE_HEIGHT}), so it looks short next to them: ask ChatGPT to redraw it with the "
                    "reference ducks' rounder body")
    if not eye and not hidden_eye:
        problem("couldn't find its eye (a small dark dot on the white face)")
    elif not beak:
        problem("couldn't find its beak (a peach patch in front of the eye)")
    else:
        before = hsv_median(img, beak)
        facts["beak_was"] = describe(before)
        if off(before):
            before, after = match_beak(img, beak)
            facts["beak_now"] = describe(after)
            notes.append(f"beak {describe(before)} → Dakku's peach {describe(after)}")
        ratio = math.sqrt(len(beak)) / body
        facts["beak_ratio"] = round(ratio, 3)
        if not 0.115 <= ratio <= 0.16:
            problem(f"its size may be off (beak-to-body {ratio:.3f}, usually 0.12–0.15): long hair or a cape "
                         "can make a body measure wide. Look at the review picture; set \"scale\" in art/ducks.json if needed")
    tone = outline_tone(img)
    if tone:
        facts["outline"] = hex_of(tone)
        if max(tone) < 30:
            notes.append(f"its outline is nearly black ({hex_of(tone)}); Dakku's is soft charcoal ({hex_of(OUTLINE)})")
    if body < 200:
        problem(f"it's small ({body:.0f}px across the body): ask ChatGPT for a bigger picture")
    return img, facts


def from_chatgpt(path):
    """The duck in a picture straight from ChatGPT: the background made transparent, and the duck
    cut out on its own. Returns (picture, notes)."""
    notes = []
    raw = Image.open(path)
    if "A" not in raw.getbands() or raw.convert("RGBA").getchannel("A").getextrema()[0] >= 250:
        notes.append("the background wasn't transparent, so it was taken out here")
    sheet = ia.with_alpha(raw)
    found = ia.pieces(sheet, 1)
    if not found:
        raise SystemExit(f"{path.name}: couldn't find a duck in it. Ask ChatGPT for one duck on a transparent background.")
    # anything else that big in the picture means more than one duck (or a stray object)
    second = ia.pieces(sheet, 2)
    if second and min(p.width * p.height for p in second) > 0.25 * found[0].width * found[0].height:
        notes.append("there's more than one big thing in the picture: only the biggest was kept")
    return found[0], notes


# ── the prompt ───────────────────────────────────────────────────────────────
FACES = {
    "calm": "one small solid dark dot eye, and nothing else on the face: no eyebrows, no mouth, no blush.",
    "angry": ("one small solid dark dot eye, and one angry eyebrow above it: a single straight, thin stroke in the "
              "same soft charcoal crayon as the outline, tilted down toward the beak, with a small gap of white "
              "between it and the eye. Nothing else on the face: no mouth, no frown lines."),
}


def prompt(duck):
    face = FACES.get(duck.get("face", "calm"), FACES["calm"])
    return f"""Draw one new duck for my study app Dakku. It must match the attached reference ducks exactly; only the outfit is new.

Copy these from the reference, exactly:
- The body: the same soft, round, blob-shaped white call duck, the same size and shape, sitting low as if floating, with the same small white wing on its side and a calm rounded bottom.
- The proportions: as round and tall as the plain white duck at the top left, with the head sitting just as high above the water. Never a lower, longer or flatter body.
- The lines: the same slightly wobbly, soft dark charcoal crayon outline (dark gray-brown, about {hex_of(OUTLINE)}), never hard black.
- The face: {face}
- The beak: the same small pale peach beak, color {beak_hex()}, not orange and not yellow.
- The pose: facing left, in the same gentle three-quarter view.
- No feet, legs, arms or hands at all. Anything the character carries sits on its back or rests against its wing.

The outfit: {duck['look'].rstrip('.')}.

Keep the outfit simple, in the same flat colors and soft crayon outline as the reference: no shading, gradients or shine. Hair and hats may stick up higher, but the duck's body stays the reference size.

The picture: one square image, 1024x1024, with only this one duck, centered, on a truly transparent background (real alpha: no white, no gray checkerboard). No water, ground, shadow, text, border or other ducks."""


# ── putting the ducks in Dakku ────────────────────────────────────────────────
def publish(say=print):
    """Every duck with a picture goes into Dakku: web/ducks/<id>.webp, the picture list Dakku loads
    (web/ducks/ducks.json) and the duck list the app starts with (web/kinds.js)."""
    ducks = load()
    manifest_path = ia.OUT / "ducks.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"kinds": {}, "eggs": [None, None, None], "cold": None}
    kinds, listed = {}, {}
    for did, d in ducks.items():
        path = PICTURES / f"{did}.png"
        if not ID_RE.match(did):
            say(f"  skipped {did!r}: an id is 2–24 lowercase letters or digits")
            continue
        if not path.exists():
            continue
        img = Image.open(path).convert("RGBA")
        body = (d.get("body") or ia.BODY_UNITS / ia.measure(img, ia.BODY_UNITS)["unit"]) / float(d.get("scale", 1))
        entry = ia.save(img, did, ia.BODY_UNITS, width=body)
        entry = ia.save_small(img, did, entry)
        entry["name"] = d["name"]
        kinds[did] = entry
        listed[did] = {"kanji": d["kanji"], "name": d["name"], "color": d.get("color", "#F4F1EA"), "blurb": d.get("blurb", "")}
    for gone in set(manifest.get("kinds", {})) - set(kinds):
        (ia.OUT / f"{gone}.webp").unlink(missing_ok=True)
        (ia.OUT / f"{gone}.small.webp").unlink(missing_ok=True)
    manifest["kinds"] = kinds
    ia.write_manifest(manifest)
    js = ("/* 鴨 Dakku: the ducks, from art/ducks.json. Written by scripts/duck.py: don't edit it by hand. */\n"
          f"window.DAKKU_DUCKS = {json.dumps(listed, ensure_ascii=False, indent=1)};\n")
    ia.write(KINDS_JS, lambda part: Path(part).write_text(js, encoding="utf-8"))
    say(f"  {len(kinds)} ducks in Dakku")
    return len(kinds)


def add(did, path, say=print):
    """ChatGPT's picture of a duck in the list becomes its finished picture, then goes into Dakku."""
    ducks = load()
    if did not in ducks:
        raise SystemExit(f"There's no duck called {did!r} in the list yet. Add it first: duck.py new {did} \"<its outfit>\"")
    piece, notes = from_chatgpt(path)
    img, facts = finish(piece, notes=notes, hidden_eye=ducks[did].get("eye") == "hidden")
    PICTURES.mkdir(parents=True, exist_ok=True)
    ia.write(PICTURES / f"{did}.png", lambda part: img.save(part, "PNG", optimize=True))
    ORIGINALS.mkdir(parents=True, exist_ok=True)
    if path.resolve().parent == INCOMING.resolve():
        shutil.move(str(path), ORIGINALS / f"{did}{path.suffix.lower()}")  # kept, out of the way
    ducks[did]["body"] = facts["body"]
    store(ducks)
    say(f"  {path.name} → {ducks[did]['name']} ({did})")
    for note in notes:
        say(f"     · {note}")
    publish(say=lambda line: None)
    shot = review([did], out=REVIEW / f"{did}.png")
    say(f"     · look at it: {shot.relative_to(ROOT)}")
    return notes


def incoming(say=print):
    """Pictures in art/incoming named after a duck in the list (goku.png) are added."""
    ducks = load()
    done = 0
    if not INCOMING.exists():
        return 0
    for path in sorted(INCOMING.iterdir()):
        stem = path.stem.lower().replace(" ", "").replace("_", "").replace("-", "")
        if path.suffix.lower() in ia.EXTS and stem in ducks:
            add(stem, path, say)
            done += 1
    return done


# ── looking at them ──────────────────────────────────────────────────────────
WATER = (164, 190, 223, 255)


def review(ids=None, out=None, comparison=("shiro", "super", "sonic")):
    """The ducks side by side at the size Dakku draws them, on the water line, with a close-up of each
    face; new ones next to a few of the first ducks to compare."""
    ducks = load()
    ids = list(ids) if ids else [d for d in ducks if (PICTURES / f"{d}.png").exists()]
    show = list(dict.fromkeys([*ids, *([c for c in comparison if c not in ids and (PICTURES / f"{c}.png").exists()] if len(ids) <= 3 else [])]))
    S = 2.0  # sheet pixels per Dakku unit
    cw, ch = int(130 * S), int(150 * S)
    cols = min(7, max(1, len(show)))
    rows = math.ceil(len(show) / cols)
    face_h = int(60 * S) if len(ids) <= 3 else 0
    sheet = Image.new("RGBA", (cols * cw, rows * (ch + face_h)), (34, 46, 70, 255))
    d = ImageDraw.Draw(sheet)
    for i, did in enumerate(show):
        img = Image.open(PICTURES / f"{did}.png").convert("RGBA")
        body = (ducks[did].get("body") or ia.BODY_UNITS / ia.measure(img, ia.BODY_UNITS)["unit"]) / float(ducks[did].get("scale", 1))
        m = ia.measure(img, ia.BODY_UNITS, width=body)
        scale = m["unit"] * S
        small = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
        cx, cy = (i % cols) * cw, (i // cols) * (ch + face_h)
        base_y = cy + int(ch * 0.88)
        d.rectangle([cx + 4, base_y, cx + cw - 4, cy + ch - 4], fill=WATER)
        sheet.alpha_composite(small, (round(cx + cw / 2 - m["baseX"] * scale), round(base_y - m["baseY"] * scale)))
        d.text((cx + 8, cy + 6), f"{ducks[did]['name']}{'' if did in ids else ' (for comparison)'}", fill=(225, 228, 238, 255))
        if face_h:
            eye = find_eye(img, body)
            if eye:
                # the face: the eye and the beak in front of it, made as big as fits under the duck
                fx, fy, fw, fh = eye["x"] - 0.22 * body, eye["y"] + 0.04 * body, 0.95 * body, 0.55 * body
                crop = img.crop((int(max(0, fx - fw / 2)), int(max(0, fy - fh / 2)), int(min(img.width, fx + fw / 2)), int(min(img.height, fy + fh / 2))))
                k = min((cw - 16) / crop.width, (face_h - 8) / crop.height)
                crop = crop.resize((max(1, round(crop.width * k)), max(1, round(crop.height * k))), Image.LANCZOS)
                sheet.alpha_composite(crop, (cx + (cw - crop.width) // 2, cy + ch + 4))
    out = out or (REVIEW / "all.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def reference():
    """art/reference.png: a few finished ducks side by side, at the same size, on a transparent
    background. Give it to ChatGPT with every prompt (it's in the "Dakku ducks" project)."""
    ducks = load()
    picks = [d for d in REFERENCE_DUCKS if (PICTURES / f"{d}.png").exists()]
    S = 3.2
    cw, ch = int(118 * S), int(128 * S)
    cols = 3
    rows = math.ceil(len(picks) / cols)
    sheet = Image.new("RGBA", (cols * cw, rows * ch), (0, 0, 0, 0))
    for i, did in enumerate(picks):
        img = Image.open(PICTURES / f"{did}.png").convert("RGBA")
        body = ducks[did].get("body") or ia.BODY_UNITS / ia.measure(img, ia.BODY_UNITS)["unit"]
        m = ia.measure(img, ia.BODY_UNITS, width=body)
        scale = m["unit"] * S
        small = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
        cx, cy = (i % cols) * cw, (i // cols) * ch
        sheet.alpha_composite(small, (round(cx + cw / 2 - m["baseX"] * scale), round(cy + ch * 0.95 - m["baseY"] * scale)))
    ia.write(REFERENCE, lambda part: sheet.save(part, "PNG", optimize=True))
    return REFERENCE


def check(say=print):
    """Every duck's picture against Dakku's style. Returns how many have something to look at."""
    ducks = load()
    flagged = 0
    for did, d in ducks.items():
        path = PICTURES / f"{did}.png"
        if not path.exists():
            say(f"  {did:10s} no picture yet ({'drawn from shapes' if did in BUILT_IN else 'not in Dakku until it has one'})")
            continue
        img = Image.open(path).convert("RGBA")
        notes = []
        _, facts = finish(img.copy(), body=d.get("body"), notes=notes, hidden_eye=d.get("eye") == "hidden")
        # a finished picture's beak is already Dakku's peach: one that still needed matching is a problem
        problems = facts["problems"] + [n for n in notes if n.startswith("beak ")]
        flagged += bool(problems)
        say(f"  {did:10s} {'ok' if not notes else '; '.join(notes)}{'' if problems or not notes else ' (just so you know)'}")
    return flagged


# ── the command line ─────────────────────────────────────────────────────────
def main(argv=None):
    ap = argparse.ArgumentParser(prog="duck.py", description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split("\n\n", 1)[1])
    sub = ap.add_subparsers(dest="cmd")
    n = sub.add_parser("new", help="add a duck to the list and print its ChatGPT prompt")
    n.add_argument("id", help="a short lowercase id, like goku (also the picture's file name)")
    n.add_argument("look", help="its outfit, for the prompt: hair, clothes, what it carries")
    n.add_argument("--name", help="its name in Dakku (default: the id, capitalised)")
    n.add_argument("--kanji", default="", help="one or two characters shown under it in the picker")
    n.add_argument("--angry", action="store_true", help="give it Dakku's angry eyebrow")
    n.add_argument("--color", default="", help="its color for the hatching confetti, like #F28C28")
    n.add_argument("--blurb", default="", help="a line about it, shown in the collection")
    p = sub.add_parser("prompt", help="print a duck's ChatGPT prompt again")
    p.add_argument("id")
    a = sub.add_parser("add", help="finish ChatGPT's picture of a duck and put it in Dakku")
    a.add_argument("id")
    a.add_argument("picture", nargs="?", help="the picture (default: art/incoming/<id>.png)")
    sub.add_parser("list", help="every duck")
    sub.add_parser("check", help="check every duck's picture")
    r = sub.add_parser("review", help="a picture of the ducks side by side")
    r.add_argument("ids", nargs="*")
    sub.add_parser("reference", help="remake art/reference.png")
    sub.add_parser("publish", help="put every duck into Dakku")
    rm = sub.add_parser("remove", help="take a duck out")
    rm.add_argument("id")
    args = ap.parse_args(argv)
    ducks = load()

    if args.cmd == "new":
        did = args.id.lower()
        if not ID_RE.match(did):
            raise SystemExit("An id is 2–24 lowercase letters or digits, starting with a letter: like goku or sailor2.")
        if did in OLD_NAMES:
            raise SystemExit(f"{did!r} was a tree in an old Dakku, so it's taken. Pick another id.")
        known = ducks.get(did, {})
        ducks[did] = {"name": args.name or known.get("name") or did.capitalize(), "kanji": args.kanji or known.get("kanji") or did[:1].upper(),
                      "color": args.color or known.get("color") or "#F4F1EA", "blurb": args.blurb or known.get("blurb", ""),
                      "face": "angry" if args.angry else known.get("face", "calm"), "look": args.look,
                      **({"body": known["body"]} if "body" in known else {})}
        store(ducks)
        text = prompt(ducks[did])
        PROMPTS.mkdir(parents=True, exist_ok=True)
        (PROMPTS / f"{did}.txt").write_text(text + "\n", encoding="utf-8")
        print(text)
        print(f"\n(Saved in art/prompts/{did}.txt.) In ChatGPT, start a new chat in the \"Dakku ducks\" project, pick Create image,\n"
              f"attach art/reference.png, paste that, and save the picture as\n  art/incoming/{did}.png\nthen run: python3 scripts/import_art.py")
    elif args.cmd == "prompt":
        if args.id not in ducks:
            raise SystemExit(f"No duck called {args.id!r}.")
        print(prompt(ducks[args.id]))
    elif args.cmd == "add":
        path = Path(args.picture) if args.picture else next((INCOMING / f"{args.id}{e}" for e in ia.EXTS if (INCOMING / f"{args.id}{e}").exists()), None)
        if not path or not path.exists():
            raise SystemExit(f"No picture: save ChatGPT's as art/incoming/{args.id}.png, or give its path.")
        add(args.id, path)
    elif args.cmd == "list":
        for did, d in ducks.items():
            has = (PICTURES / f"{did}.png").exists()
            print(f"  {d['kanji']:4s} {d['name']:12s} {did:10s} {'' if has else '(no picture yet)'}")
        print(f"{len(ducks)} ducks")
    elif args.cmd == "check":
        sys.exit(1 if check() else 0)
    elif args.cmd == "review":
        print(review(args.ids).relative_to(ROOT))
    elif args.cmd == "reference":
        print(reference().relative_to(ROOT))
    elif args.cmd == "publish":
        publish()
    elif args.cmd == "remove":
        if args.id in BUILT_IN:
            raise SystemExit("The first ten ducks are part of Dakku and stay.")
        if args.id not in ducks:
            raise SystemExit(f"No duck called {args.id!r}.")
        ducks.pop(args.id)
        store(ducks)
        (PICTURES / f"{args.id}.png").unlink(missing_ok=True)
        publish()
        print(f"{args.id} is out of Dakku. Any sessions with it show as a plain duck now.")
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
