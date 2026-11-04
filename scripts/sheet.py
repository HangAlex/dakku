#!/usr/bin/env python3
"""A candidate sheet: Shiro, Cloud, then each incoming duck at the size Dakku would draw it (its gate scale
applied), 9 per row, with a label and a short note under each. Usage: sheet.py out.png id[=scale[:note]] ..."""
import sys, json, glob
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, 'scripts')
import import_art as ia
root = Path('.')
out = sys.argv[1]
items = []
for a in sys.argv[2:]:
    did, _, rest = a.partition('=')
    sc, _, note = rest.partition(':')
    items.append((did, float(sc or 1), note))
def pick(did):
    for p in [root/f'art/incoming/{did}.png', root/f'art/ducks/{did}.png']:
        if p.exists(): return p
    g = glob.glob(f'web/ducks/{did}.png') + glob.glob(f'web/ducks/{did}.webp')
    return Path(g[0])
refs = [('shiro', 1.0, 'the plain duck'), ('cloud', 1.0, 'live')]
cells = refs + items
W, H, per = 360, 400, 9
rows = (len(cells) + per - 1) // per
sheet = Image.new('RGBA', (W*per, H*rows), (30, 32, 48, 255))
d = ImageDraw.Draw(sheet)
try: font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 18)
except Exception: font = ImageFont.load_default()
S = 0.95
for k, (did, sc, note) in enumerate(cells):
    p = pick(did)
    img = Image.open(p).convert('RGBA')
    m = ia.measure(img, ia.BODY_UNITS)
    scale = (W * 0.75 / ia.BODY_UNITS) * m['unit'] * sc   # m['unit'] = Dakku units per pixel
    small = img.resize((max(1, round(img.width*scale)), max(1, round(img.height*scale))), Image.LANCZOS)
    cx, cy = (k % per) * W, (k // per) * H
    x = round(cx + W/2 - m['baseX']*scale); y = round(cy + H*0.80 - m['baseY']*scale)
    sheet.alpha_composite(small, (x, y))
    d.text((cx+10, cy+H-44), did + (f'  ×{sc:.3f}' if sc != 1 else ''), fill=(235,235,235,255), font=font)
    if note: d.text((cx+10, cy+H-22), note[:40], fill=(255,210,120,255), font=font)
sheet.save(out); print('wrote', out, sheet.size)
