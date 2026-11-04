"""colordepth.py <png> [...]: the mean saturation and value of a duck picture's colored pixels (not the white body,
not the charcoal line), next to the accepted ducks' middle: a pastel or grayed draft shows as low saturation."""
import colorsys, glob, os, statistics, sys
from PIL import Image
def depth(path):
    im = Image.open(path).convert('RGBA'); im.thumbnail((300, 300))
    S = []; V = []
    for r, g, b, a in im.getdata():
        if a < 200: continue
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s < 0.10 or v < 0.2: continue
        S.append(s); V.append(v)
    return (statistics.mean(S), statistics.mean(V)) if len(S) > 300 else (0, 0)
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
acc = [depth(p) for p in glob.glob(os.path.join(root, 'art/ducks/*.png'))]
acc = [a for a in acc if a[0]]
sm = statistics.median(a[0] for a in acc); s20 = sorted(a[0] for a in acc)[len(acc) // 5]
for p in sys.argv[1:]:
    s, v = depth(p)
    flag = 'PALE' if s < s20 else ('ok' if s >= sm - 0.03 else 'a little pale')
    print(f"{os.path.basename(p):22s} sat {s:.2f}  val {v:.2f}   accepted median {sm:.2f}, p20 {s20:.2f}   {flag}")
