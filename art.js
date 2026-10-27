/* 鴨 Dakku — the art: doodle call ducks, their eggs, and the pond they sit in.
   The style: flat white ducks facing left, with a soft, slightly wobbly
   dark outline, a black dot eye and a little peach beak, floating on periwinkle water with ripple dashes.
   The real ducks are painted with ChatGPT (art/chatgpt-prompts.md); scripts/import_art.py cuts them
   into web/ducks/ and lists them in ducks.json. Until a picture exists, it's drawn here. Every duck
   and egg lives in a 100 × 120 box with its base at (50, 112), so the same art can go into SVG on
   screen and onto a canvas for share images. */
'use strict';

const Art = (() => {
  const r1 = (n) => Math.round(n * 10) / 10;
  const clamp01 = (t) => Math.max(0, Math.min(1, t));
  const ell = (cx, cy, rx, ry) => (rx <= 0 || ry <= 0) ? '' :
    `M${r1(cx - rx)} ${r1(cy)}a${r1(rx)} ${r1(ry)} 0 1 0 ${r1(2 * rx)} 0a${r1(rx)} ${r1(ry)} 0 1 0 ${r1(-2 * rx)} 0Z`;
  const circ = (cx, cy, r) => ell(cx, cy, r, r);
  const poly = (pts) => 'M' + pts.map(([x, y]) => `${r1(x)} ${r1(y)}`).join('L') + 'Z';

  /* ── a seeded random generator, so drawings and ponds come out the same every time ── */
  function rng(seed) {
    let a = 0;
    for (const ch of String(seed)) a = (Math.imul(a ^ ch.charCodeAt(0), 2654435761) + 1013904223) >>> 0;
    return () => {
      a = (a + 0x6D2B79F5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  // a hand-drawn round shape: an ellipse whose edge wanders a little
  function blob(cx, cy, rx, ry, seed, wobble = 0.035, n = 16) {
    const rand = rng(seed);
    const pts = [];
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2, k = 1 + (rand() - 0.5) * 2 * wobble;
      pts.push([cx + Math.cos(a) * rx * k, cy + Math.sin(a) * ry * k]);
    }
    const mid = (p, q) => [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2];
    const m0 = mid(pts[0], pts[1]);
    let d = `M${r1(m0[0])} ${r1(m0[1])}`;
    for (let i = 1; i <= n; i++) {
      const p = pts[i % n], m = mid(p, pts[(i + 1) % n]);
      d += `Q${r1(p[0])} ${r1(p[1])} ${r1(m[0])} ${r1(m[1])}`;
    }
    return d + 'Z';
  }

  // A shape is {d, fill, stroke, sw}. An outlined group draws every outline first, then every fill
  // again on top, so overlapping parts merge into one silhouette with a single outer line.
  const INK = '#2E2C35';
  const SW = 3.1;
  const outlined = (parts, sw = SW) => [...parts.map((p) => ({ ...p, stroke: INK, sw })), ...parts.map((p) => ({ d: p.d, fill: p.fill }))];
  const line = (d, sw = 1.8, stroke = INK) => ({ d, stroke, sw });
  const pathSVG = (s) => `<path d="${s.d}" fill="${s.fill || 'none'}"${s.stroke ? ` stroke="${s.stroke}" stroke-width="${s.sw}" stroke-linecap="round" stroke-linejoin="round"` : ''}/>`;
  const pathsSVG = (shapes) => shapes.map((s) => (s.src ? `<image href="${s.src}" x="${s.x}" y="${s.y}" width="${s.w}" height="${s.h}" preserveAspectRatio="none"/>` : s.d ? pathSVG(s) : '')).join('');

  /* ── the ducks ───────────────────────────────────────────────────────────── */
  const KINDS = { // Dakku's own first ten, which are drawn from shapes until they have pictures
    shiro: { kanji: '白', name: 'Shiro', hours: 0, color: '#F4F1EA', blurb: 'A plain little call duck. Perfect as it is.' },
    sailor: { kanji: '水兵', name: 'Sailor', hours: 2, color: '#3A6BC0', blurb: 'Ready for the open sea, or at least the pond.' },
    neko: { kanji: '猫', name: 'Neko', hours: 5, color: '#9AA0AD', blurb: 'A cat-ear hoodie. Duck or cat? Yes.' },
    super: { kanji: '金', name: 'Super', hours: 10, color: '#F2B83A', blurb: 'Golden hair, orange gi, power level rising.' },
    ninja: { kanji: '忍', name: 'Ninja', hours: 20, color: '#4A5163', blurb: 'Silent, focused, nearly invisible.' },
    kitsune: { kanji: '狐', name: 'Kitsune', hours: 35, color: '#D9463B', blurb: 'A fox mask from the shrine festival.' },
    yukata: { kanji: '祭', name: 'Matsuri', hours: 50, color: '#4566B8', blurb: 'Dressed up for the summer festival.' },
    samurai: { kanji: '侍', name: 'Samurai', hours: 80, color: '#C0392B', blurb: 'A tiny warrior in a very big helmet.' },
    king: { kanji: '王', name: 'King', hours: 150, color: '#D9AE34', blurb: 'Rules the pond. Earned every minute.' },
    astro: { kanji: '宙', name: 'Astro', hours: 300, color: '#9CC2EE', blurb: 'Studied so much it reached space.' },
  };
  // and the rest of the ducks, painted ones from the duck list (art/ducks.json, published as web/kinds.js)
  for (const [id, info] of Object.entries(window.MORI_DUCKS || {})) KINDS[id] = { hours: 0, ...KINDS[id], ...info };
  const ORDER = Object.keys(KINDS);
  const OLD = { matsu: 'shiro', take: 'sailor', sakura: 'neko', momiji: 'super', icho: 'ninja', sugi: 'kitsune', ume: 'yukata' };
  const kindOf = (k) => (KINDS[k] ? k : OLD[k] || 'shiro');

  const CREAM = '#FFFFFF', BEAK = '#F4C98F';
  // A call duck floating on the water: a soft round body, a round head, a tiny beak. The shapes below
  // face right; duckInner() flips them so every duck faces left.
  const tail = (fill) => ({ d: 'M24 90Q14 86 13 77Q20 81 29 84Z', fill });
  const bodyPart = (fill, seed = 'body') => ({ d: blob(47, 94.5, 31.5, 17.5, seed, 0.05), fill });
  const headPart = (fill, seed = 'head') => ({ d: blob(62, 74.5, 16, 15.5, seed, 0.05), fill });
  const beak = () => [
    ...outlined([{ d: blob(79, 75, 6.6, 4.2, 'beak', 0.02), fill: BEAK }], 2.6),
    { d: circ(80.5, 73.6, 0.8), fill: INK },
  ];
  const face = ({ brows = false } = {}) => [
    { d: circ(67, 70.5, 2.7), fill: INK },              // a black dot eye
    ...(brows ? [line('M61 63L71.5 65.5', 2.2)] : []),
    ...beak(),
  ];
  const wing = (stroke = INK) => line('M34 94Q43 101 53 95', 1.8, stroke);
  const plain = (fill = CREAM, headFill = CREAM) => outlined([tail(fill), bodyPart(fill), headPart(headFill)]);

  const OUTFITS = {
    shiro: () => [...plain(), wing(), ...face()],
    sailor: () => [
      ...plain(), wing(),
      ...outlined([{ d: 'M49 85Q62 90 76 85L69 97Q61 93 55 97Z', fill: '#3A6BC0' }], 2.6),
      line('M53 92Q62 95.5 71 92', 1.4, '#FFFFFF'),
      ...outlined([{ d: blob(62.5, 90.5, 3.2, 2.6, 'bow'), fill: '#E0524B' }], 2.2),
      ...face(),
      ...outlined([{ d: blob(61, 59.5, 12.5, 5, 'cap'), fill: '#FFFFFF' }, { d: 'M50 61Q61 66 72 61L72 63Q61 68 50 63Z', fill: '#3A6BC0' }], 2.6),
    ],
    neko: () => [
      ...outlined([tail('#A9AEB9'), bodyPart('#A9AEB9'), { d: blob(61, 73, 19, 18.5, 'hood'), fill: '#A9AEB9' },
        { d: 'M47 61L49 46L58 56Z', fill: '#A9AEB9' }, { d: 'M64 55L72 44L76 59Z', fill: '#A9AEB9' }]),
      { d: 'M50 57L51 50L55.5 55Z', fill: '#F2B3C2' }, { d: 'M67 55L71 49L72.5 57Z', fill: '#F2B3C2' },
      ...outlined([{ d: blob(65, 77, 12, 10.5, 'face'), fill: CREAM }], 2.4),
      wing('#5E6472'), ...face(),
    ],
    super: () => [
      ...outlined([tail('#F2A04B'), bodyPart('#F2A04B'), headPart(CREAM)]),
      line('M20 101Q47 108 77 100', 3.2, '#2C3E7A'),
      ...outlined([{ d: 'M48 70L43 55L51 60L49 45L57 56L61 40L65 55L72 44L71 58L80 53L77 68L66 62L55 63Z', fill: '#F7CF55' }], 2.6),
      ...face({ brows: true }),
    ],
    ninja: () => [
      ...outlined([tail('#4E5568'), bodyPart('#4E5568'), { d: blob(62, 73.5, 18, 17.5, 'hood'), fill: '#4E5568' }]),
      ...outlined([{ d: blob(66, 76, 11.5, 9, 'opening'), fill: CREAM }], 2.4),
      line('M45 64Q62 57 80 64', 4, '#D6453D'), line('M45 65Q37 61 32 64', 3, '#D6453D'), line('M45 66Q39 70 36 75', 3, '#D6453D'),
      wing('#272B36'), ...face(),
    ],
    kitsune: () => [
      ...plain(), wing(),
      ...outlined([{ d: 'M51 63L50 47L59 57Z', fill: '#EE8A3E' }, { d: 'M64 57L72 45L75 62Z', fill: '#EE8A3E' }], 2.6),
      line('M49 87Q62 93.5 76 87', 5, '#D6453D'),
      ...face(),
      ...outlined([{ d: blob(50, 66, 7, 8.5, 'mask'), fill: '#FFFFFF' }], 2.2),
      line('M47 63L49.5 64.5', 1.6, '#D6453D'), line('M51.5 64.5L54 63', 1.6, '#D6453D'), line('M49 70Q50 71 51 70', 1.4, '#D6453D'),
    ],
    yukata: () => [
      ...outlined([tail('#4C6AB8'), bodyPart('#4C6AB8'), headPart(CREAM)]),
      line('M27 95Q30 92 33 95Q36 98 39 95', 1.4, '#FFFFFF'), line('M55 101Q58 98 61 101Q64 104 67 101', 1.4, '#FFFFFF'),
      line('M18 99Q47 106 78 98', 4.4, '#D9485E'),
      ...face(),
      ...outlined([{ d: blob(51, 63, 3.6, 3.4, 'f1'), fill: '#F6A5C0' }, { d: blob(55.5, 60, 3.2, 3, 'f2'), fill: '#F6A5C0' }, { d: blob(56, 65.5, 3, 2.8, 'f3'), fill: '#F6A5C0' }], 1.8),
      { d: circ(54, 62.8, 1.3), fill: '#FCE48A' },
    ],
    samurai: () => [
      ...outlined([tail('#344778'), bodyPart('#344778'), headPart(CREAM)]),
      wing('#1D2747'), ...face({ brows: true }),
      ...outlined([{ d: 'M45 71Q45 54 62 53Q79 54 80 71L74 68Q72 60 62 60Q52 60 50 68Z', fill: '#D2453D' }], 2.6),
      line('M55 55Q51 46 45 42', 3, '#E8BE4A'), line('M69 55Q73 46 79 42', 3, '#E8BE4A'),
    ],
    king: () => [
      ...outlined([{ d: blob(41, 93, 29, 16, 'cape'), fill: '#C2334A' }, tail(CREAM), bodyPart(CREAM), headPart(CREAM)]),
      wing(),
      ...outlined([{ d: blob(60, 88, 13, 3.4, 'fur'), fill: '#FFFFFF' }], 2.2),
      ...face(),
      ...outlined([{ d: 'M51 61L50 48L56 55L61.5 45L67 55L73 48L72 61Q61.5 64 51 61Z', fill: '#EAC14A' }], 2.6),
      { d: circ(61.5, 55, 1.6), fill: '#D2453D' },
    ],
    astro: () => [
      ...plain('#EEF1F6', CREAM), wing(),
      ...outlined([{ d: blob(44, 96, 6, 4.5, 'panel'), fill: '#5E8FD0' }], 2),
      ...face(),
      { d: blob(62, 73, 21.5, 21, 'glass', 0.02), fill: 'rgba(200,225,255,.22)', stroke: '#8FB6E8', sw: 2.6 },
      line('M49 62Q53 56 59 55', 2.2, 'rgba(255,255,255,.85)'),
    ],
  };
  const drawn = new Map(); // each placeholder is the same every time: draw it once
  const outfit = (kind) => { if (!drawn.has(kind)) drawn.set(kind, (OUTFITS[kind] || OUTFITS.shiro)()); return drawn.get(kind); }; // newer ducks only come painted

  // A cold egg: what's left when you give up. It stays in the pond, on a lily pad.
  const coldEgg = () => [
    ...outlined([{ d: blob(50, 108, 25, 6.5, 'pad'), fill: '#9CC48C' }], 2.6),
    { d: 'M50 108L70 102L74 106Z', fill: '#9DB8DD' },
    ...outlined([{ d: blob(50, 90, 13.5, 17.5, 'cold'), fill: '#C9D3DF' }]),
    line('M41 87L45 91L49 85L53 92L57 87L60 90', 1.8),
    line('M60 70L66 76M66 70L60 76M63 68.5V77.5', 1.6, '#FFFFFF'),
  ];

  /* ── the egg on the Hatch screen: it wobbles, cracks, and a duck peeks out ── */
  function egg(progress) {
    const p = clamp01(progress);
    const out = [
      ...outlined([{ d: blob(50, 105, 31, 9, 'nest'), fill: '#C49B69' }], 2.8),
      { d: blob(50, 103, 24, 5, 'nest-in'), fill: '#8C6844' },
      ...outlined([{ d: blob(50, 85, 16.5, 21.5, 'egg', 0.02), fill: '#FFFDF5' }]),
      { d: ell(44, 75, 4, 6), fill: '#FFFFFF' },
    ];
    if (p >= 0.5) out.push(line('M38 86L43 90L47 84L52 91L56 86L60 89', 1.8));
    if (p >= 0.8) {
      out.push({ d: poly([[36, 80], [41, 75], [46, 81], [50, 73], [55, 80], [60, 74], [64, 80], [60, 84], [55, 79], [50, 84], [45, 79], [40, 84]]), fill: INK });
      out.push({ d: circ(45.5, 78.5, 1.6), fill: '#FFFFFF' }, { d: circ(54.5, 78.5, 1.6), fill: '#FFFFFF' });
    }
    out.push({ d: 'M20 104Q50 119 80 104', stroke: INK, sw: 9 }, { d: 'M20 104Q50 119 80 104', stroke: '#C49B69', sw: 6 },  // the nest's front rim
      line('M27 107Q33 110 39 108.5', 1.6, '#8C6844'), line('M44 111Q50 113 56 111', 1.6, '#8C6844'), line('M61 108.5Q67 110 73 107', 1.6, '#8C6844'),
      line('M19 103Q13 100 10 97', 2.2, '#A27C52'), line('M81 103Q87 100 90 97', 2.2, '#A27C52'));
    return out;
  }

  /* ── pictures painted with ChatGPT, when they exist ─────────────────────── */
  const sprites = { kinds: {}, eggs: [], cold: null, ponds: {}, ripples: [], decor: {} };
  let loading = null;
  function loadSprites() {
    loading ||= fetch('ducks/ducks.json', { cache: 'no-cache' })
      .then((res) => (res.ok ? res.json() : null))
      .then(async (list) => {
        if (!list) return false;
        const take = async (entry) => {
          if (!entry) return null;
          const img = new Image();
          img.src = entry.src;
          await img.decode();
          return { ...entry, img };
        };
        for (const [k, entry] of Object.entries(list.kinds || {})) if (KINDS[k]) sprites.kinds[k] = await take(entry).catch(() => null);
        sprites.eggs = await Promise.all((list.eggs || []).map((e) => take(e).catch(() => null)));
        sprites.cold = await take(list.cold).catch(() => null);
        // ponds come in themes, each a wide and maybe a tall picture (the very first ponds were just the classic one).
        // Only their water maps are read now: a pond on screen just needs its picture's address, and a share
        // picture decodes it when it's drawn (see ready), so twenty big ponds don't sit decoded in a phone's memory.
        const ponds = list.ponds || {};
        for (const [theme, shapes] of Object.entries(ponds.wide || ponds.tall ? { classic: ponds } : ponds)) {
          sprites.ponds[theme] = {};
          for (const [shape, entry] of Object.entries(shapes || {})) { try { sprites.ponds[theme][shape] = waterMap({ ...entry, img: null }); } catch { /* no map */ } }
        }
        sprites.ripples = (await Promise.all((list.ripples || []).map((e) => take(e).catch(() => null)))).filter(Boolean);
        for (const [id, entry] of Object.entries(list.decor || {})) if (DECOR[id]) sprites.decor[id] = await take(entry).catch(() => null);
        return true;
      })
      .catch(() => false);
    return loading;
  }
  // Decodes the pictures a scene needs for drawing on a canvas (a share picture), once each.
  const decoded = new Map();
  async function ready(scene) {
    const load = (src) => {
      if (!decoded.has(src)) { const img = new Image(); img.src = src; decoded.set(src, img.decode().then(() => img)); }
      return decoded.get(src);
    };
    await Promise.all([...scene.ground, ...(scene.decor || [])].filter((s) => s.src && !s.img).map(async (s) => { s.img = await load(s.src).catch(() => null); }));
    return scene;
  }
  // A painted pond comes with a coarse map of its open water, made by import_art.py: for each cell,
  // how far it is to the shore or a lily pad (in steps of 2 pond units), and for each column, how
  // high the picture reaches, so a duck's head never sticks out past the far bank.
  function waterMap(pic) {
    const dist = Uint8Array.from(atob(pic.dist), (ch) => ch.charCodeAt(0));
    const cell = POND_W / pic.cols, rooms = [];
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (let r = 0; r < pic.rows; r++) {
      for (let c = 0; c < pic.cols; c++) {
        const v = dist[r * pic.cols + c];
        if (!v) continue;
        rooms.push(v * 2);
        x0 = Math.min(x0, c * cell); x1 = Math.max(x1, (c + 1) * cell);
        y0 = Math.min(y0, r * cell); y1 = Math.max(y1, (r + 1) * cell);
      }
    }
    if (!rooms.length) return null;
    return { ...pic, dist, cell, box: [x0, y0, x1, y1], rooms: rooms.sort((a, b) => a - b) };
  }
  // a picture placed in the 100 × 120 box: `unit` is box units per picture pixel
  const placed = (s) => ({ x: 50 - s.baseX * s.unit, y: 112 - s.baseY * s.unit, w: s.w * s.unit, h: s.h * s.unit });
  const imageSVG = (s) => { const p = placed(s); return `<image href="${s.src}" x="${r1(p.x)}" y="${r1(p.y)}" width="${r1(p.w)}" height="${r1(p.h)}"/>`; };
  const spriteFor = (kind, cold) => (cold ? sprites.cold : sprites.kinds[kindOf(kind)]);

  /** The inside of a 100 × 120 box: a duck (or a cold egg), as SVG markup. */
  function duckInner(kind, cold = false) {
    const s = spriteFor(kind, cold);
    if (s) return imageSVG(s);
    if (cold) return pathsSVG(coldEgg());
    return `<g transform="matrix(-1 0 0 1 100 0)">${pathsSVG(outfit(kindOf(kind)))}</g>`; // face left
  }
  // On its own (the picker, the log, the collection, a hatching), a duck gets a frame without the
  // headroom the pond needs, so it shows bigger. 84 × 100 keeps the 5:6 shape of those spots. Every
  // duck is drawn the same size in it: hair, a ponytail or a sword that reaches further shows past
  // the frame instead of being cut off (so leave a little room around it).
  function duckSVG(kind, { cold = false, cls = '' } = {}) {
    return `<svg class="${cls}" viewBox="8 14 84 100" style="overflow:visible" aria-hidden="true">${duckInner(kind, cold)}</svg>`;
  }
  /** The egg in its nest at `progress` (0 to 1): whole, then a crack, then a peek. */
  function eggInner(progress) {
    const stage = progress >= 0.8 ? 2 : progress >= 0.5 ? 1 : 0;
    const s = sprites.eggs[stage];
    return s ? imageSVG(s) : pathsSVG(egg(progress));
  }

  /* ── the pond: open water, with the ducks spread out across it ──────────── */
  const WATER = { top: '#9DB8DD', light: '#D4E1F2', streak: '#B9CCE8', ripple: '#3D5A80', pad: '#9CC48C', lotus: '#F2A5C0', petal: '#F7C6D4', petalEdge: '#E29AB1' };
  // Each duck floats: its picture is cut off along a wavy waterline, so it sits in the water rather
  // than on top of it, with a pale line where it meets the water. Under it go the ripples it makes:
  // rings painted with ChatGPT (centered at (50, 111), the duck hiding their back half), or until
  // then, little dark dashes either side, as in the reference.
  const CUT = 'M-60 -80H160V108.9H90Q84 109.7 77 108.9Q67 107.7 57 108.8Q47 109.9 37 108.9Q27 107.9 17 109.3H-60Z';
  const CONTACT = [line('M25 109.2Q36 107.5 47 108.9Q58 110.2 69 108.7Q76 107.9 82 108.8', 2.4, WATER.light)];
  const DASHES = [line('M5 112.5Q11 111 17 112.5', 2.6, WATER.ripple), line('M84 112Q90 110.5 96 112', 2.6, WATER.ripple), line('M62 116.5Q67 115.5 72 116.5', 2.2, WATER.ripple)];
  const ringAt = (s) => ({ x: 50 - s.cx * s.unit, y: 111 - s.cy * s.unit, w: s.w * s.unit, h: s.h * s.unit });
  // which ripples a duck gets, from its random number: one of the painted rings, maybe mirrored
  const ringFor = (r) => {
    const n = sprites.ripples.length, i = Math.floor(r * n * 2);
    return n ? { n: i % n, flip: i >= n } : { n: 0, flip: false };
  };
  const ringInner = (n) => {
    const s = sprites.ripples[n];
    if (!s) return pathsSVG(DASHES);
    const p = ringAt(s);
    return `<image href="${s.src}" x="${r1(p.x)}" y="${r1(p.y)}" width="${r1(p.w)}" height="${r1(p.h)}"/>`;
  };
  const roundRect = (w, h, r) => `M${r} 0H${r1(w - r)}A${r} ${r} 0 0 1 ${r1(w)} ${r}V${r1(h - r)}A${r} ${r} 0 0 1 ${r1(w - r)} ${r1(h)}H${r}A${r} ${r} 0 0 1 0 ${r1(h - r)}V${r}A${r} ${r} 0 0 1 ${r} 0Z`;
  // a petal lying on the water: an ellipse turned by `a`
  const petal = (x, y, r, a) => {
    const c = Math.cos(a) * r, s = Math.sin(a) * r, deg = r1((a * 180) / Math.PI);
    const arc = `A${r1(r)} ${r1(r * 0.55)} ${deg} 1 0`;
    return `M${r1(x - c)} ${r1(y - s)}${arc} ${r1(x + c)} ${r1(y + s)}${arc} ${r1(x - c)} ${r1(y - s)}Z`;
  };

  const POND_W = 1000;
  // Decorations, painted with ChatGPT, that go on a painted pond's water: how wide each is at the front
  // of the pond (in pond units), where it likes to be (the back of the pond, near the shore, or out on
  // open water), and whether it stands up out of the water, lies flat on it, or swims under it.
  const DECOR = {
    torii: { w: 230, at: 'back', lie: 'stand' },
    lantern: { w: 92, at: 'shore', lie: 'stand' },
    koi: { w: 150, at: 'open', lie: 'under' },
    lanterns: { w: 170, at: 'open', lie: 'flat' },
    lotus: { w: 130, at: 'shore', lie: 'flat' },
  };
  const FAR = 0.78;              // a duck at the back of the pond, next to one at the front
  const KMIN = 0.42, KMAX = 2.3; // how big a duck can be drawn: one 100-unit box is 100·k pond units
  // How far apart ducks like to be (× k): side by side, a duck is 66 wide; one behind another needs
  // about a duck's height, or the front one hides it.
  const SX = 72, SY = 80;
  const PER_DUCK = 6300;         // water each duck needs, × k²

  /**
   * items: [{kind, cold}] in hatching order. Returns a scene: the water and what floats on it
   * (`ground`), then the ducks from back to front (`drawn`), each on its own patch of water and
   * drawn as big as fits. With a pond painted with ChatGPT, that's the picture; until then, the
   * pond is drawn here, in a shape that suits how many ducks there are.
   */
  function pond(items, { seed = 'mori', max = 400, minAspect = 0.42, maxAspect = 1, shape = 'wide', theme = 'classic', decor = [] } = {}) {
    const shown = items.slice(-max);
    const set = (sprites.ponds[theme]?.wide || sprites.ponds[theme]?.tall ? sprites.ponds[theme] : sprites.ponds.classic) || {};
    const pic = set[shape] || set.wide || set.tall;
    const scene = pic ? paintedPond(shown, pic, seed, decor) : drawnPond(shown, seed, minAspect, maxAspect);
    for (const d of scene.drawn) d.idx += items.length - shown.length;
    return { ...scene, shownCount: shown.length };
  }
  // the biggest k in [KMIN, KMAX] for which `fits(k)`
  function biggest(fits) {
    let lo = KMIN, hi = KMAX;
    if (fits(hi)) return hi;
    for (let i = 0; i < 24; i++) { const mid = (lo + hi) / 2; if (fits(mid)) lo = mid; else hi = mid; }
    return lo;
  }

  // Spread the ducks out: each takes the best of a few random spots from `pick`, the one furthest
  // from the ducks already there (and from the shore), so they fill the pond evenly without lining up.
  function spread(N, k, pick, random) {
    const spots = [];
    const tries = N > 150 ? 8 : N > 60 ? 14 : 24;
    for (let i = 0; i < N; i++) {
      let best = null, bestScore = -Infinity;
      for (let t = 0; t < tries; t++) {
        const c = pick(random);
        if (!c) continue;
        let score = 0.55 + 1.5 * c.edge; // the shore pushes gently, so a few big ducks don't all crowd the middle
        for (const s of spots) {
          const q = (c.p + s.p) / 2, dx = (c.x - s.x) / (SX * k * q), dy = (c.y - s.y) / (SY * k * q);
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < score && (score = dist) <= bestScore) break;
        }
        if (score > bestScore) { bestScore = score; best = c; }
      }
      spots.push(best || pick(random, true));
    }
    return spots;
  }
  function placeDucks(shown, spots, k, random) {
    // Only some ducks bob in a crowded pond, to keep phones smooth. A bobbing duck's ripples swell
    // as it dips, and every so often a ring spreads out from it (`w`: how often).
    const N = shown.length, lively = N <= 30 ? 1 : (N > 120 ? 16 : 24) / N;
    return shown.map((item, idx) => {
      const { x, y, p } = spots[idx];
      const kk = k * p * (0.96 + random() * 0.08), ring = random();
      const bob = !item.cold && random() < lively ? { t: r1(3.4 + random() * 1.8), d: r1(-random() * 5), w: r1(8 + random() * 6), wd: r1(-random() * 14) } : null;
      return { type: 'duck', item, idx, k: kk, x: x - 50 * kk, y: y - 112 * kk, ring, bob };
    }).sort((a, b) => (a.y + 112 * a.k) - (b.y + 112 * b.k));
  }

  /* the pond painted with ChatGPT: the decorations, then the ducks around them, go on its open water */
  function paintedPond(shown, pic, seed, decor = []) {
    const N = shown.length, W = POND_W, H = Math.round((W * pic.h) / pic.w);
    const { cell, cols, rows, dist, rooms, box: [bx0, by0, bx1, by1] } = pic;
    const room = (x, y) => {
      const c = Math.floor(x / cell), r = Math.floor(y / cell);
      return c < 0 || r < 0 || c >= cols || r >= rows ? 0 : dist[r * cols + c] * 2;
    };
    const top = (x) => pic.top[Math.max(0, Math.min(cols - 1, Math.floor(x / cell)))];
    const depth = (y) => FAR + (1 - FAR) * clamp01((y - by0) / Math.max(1, by1 - by0));
    // roughly the water a duck's base can go on: a little in from the shore
    const usable = (k) => {
      let lo = 0, hi = rooms.length;
      while (lo < hi) { const mid = (lo + hi) >> 1; if (rooms[mid] < 18 * k) lo = mid + 1; else hi = mid; }
      return (rooms.length - lo) * cell * cell;
    };
    const placed = placeDecor(decor, { room, top, depth, box: pic.box, height: H, seed });
    const taken = placed.reduce((n, o) => n + Math.PI * o.rx * o.ry, 0);
    const k = N ? biggest((k) => N * PER_DUCK * k * k <= usable(k) - taken) : 1;
    // a duck's base stays out of each decoration's patch of water (with room for its own body)
    const clearOf = (x, y, kp) => placed.every((o) => ((x - o.cx) / (o.rx + 34 * kp)) ** 2 + ((y - o.cy) / (o.ry + 12 * kp)) ** 2 > 1);
    const pick = (random, anywhere = false) => {
      for (let a = 0; a < (anywhere ? 400 : 40); a++) {
        const x = bx0 + random() * (bx1 - bx0), y = by0 + random() * (by1 - by0), p = depth(y), kp = k * p;
        // room for its beak and tail either side, and a little water in front of it
        const side = Math.min(room(x - 26 * kp, y), room(x + 32 * kp, y)) - 8 * kp, front = room(x, y + 6 * kp) - 4 * kp;
        if (anywhere ? room(x, y) <= 0 : side < 0 || front < 0 || y - 80 * kp < top(x) + 6 || !clearOf(x, y, kp)) continue; // (its head would poke out past the far bank)
        return { x, y, p, edge: Math.max(0, Math.min(side / (SX * kp), (2 * front) / (SY * kp))) };
      }
      return anywhere ? { x: (bx0 + bx1) / 2, y: (by0 + by1) / 2, p: 1, edge: 0 } : null;
    };
    const random = rng(seed);
    const drawn = placeDucks(shown, spread(N, k, pick, random), k, random);
    return { width: W, height: H, k, ground: [{ img: pic.img, src: pic.src, x: 0, y: 0, w: W, h: H }], drawn, decor: placed };
  }

  // Finds each decoration a spot: the best of many random ones that's all on open water, clear of the
  // others, and where it likes to be. The same pond and decorations always give the same spots.
  function placeDecor(ids, { room, top, depth, box: [bx0, by0, bx1, by1], height, seed }) {
    const random = rng(`${seed}:decor`), out = [];
    for (const id of ids) {
      const s = sprites.decor[id], def = DECOR[id];
      if (!s || !def) continue;
      let best = null, bestScore = -Infinity;
      for (let t = 0; t < 220; t++) {
        const cx = bx0 + random() * (bx1 - bx0), cy = by0 + random() * (by1 - by0), p = depth(cy);
        const w = def.w * p, h = (w * s.h) / s.w;
        // its patch of water: what it covers lying flat, or where it stands in the water
        const rx = w / 2, ry = def.lie === 'stand' ? w * 0.13 : h / 2;
        const rim = [0, 1, 2, 3, 4, 5, 6, 7].map((i) => [cx + Math.cos(i * Math.PI / 4) * rx, cy + Math.sin(i * Math.PI / 4) * ry]);
        if (room(cx, cy) < ry || rim.some(([x, y]) => room(x, y) < 4)) continue;
        const y = def.lie === 'stand' ? cy + ry * 0.4 - h : cy - h / 2; // the picture's top
        if (y < 2 || (def.lie === 'stand' && y < Math.max(top(cx - w / 2), top(cx), top(cx + w / 2)) - 4)) continue; // it would stick out past the far bank
        const apart = out.reduce((m, o) => Math.min(m, Math.hypot((cx - o.cx) / (rx + o.rx), (cy - o.cy) / (ry + o.ry))), 9);
        if (apart < 1.15) continue;
        const where = def.at === 'back' ? -(cy - by0) / (by1 - by0) : def.at === 'shore' ? -room(cx, cy) / 120 : Math.min(1, room(cx, cy) / 200);
        const score = where + 0.25 * Math.min(apart, 3) + random() * 0.35;
        if (score > bestScore) { bestScore = score; best = { id, src: s.src, img: s.img, lie: def.lie, cx, cy, rx, ry, x: cx - w / 2, y, w, h, base: cy + ry * (def.lie === 'stand' ? 0.4 : 0), r: random() }; }
      }
      if (best) out.push(best);
    }
    return out.filter((o) => o.y + o.h <= height + 40).sort((a, b) => a.base - b.base);
  }

  /* until then, a pond drawn here: flat water with ripples, lily pads and a few petals */
  function drawnPond(shown, seed, minAspect, maxAspect) {
    const N = shown.length, W = POND_W;
    let H = W * Math.max(minAspect, Math.min(maxAspect, 0.42 + 0.1 * Math.log2(Math.max(1, N) / 4)));
    const room = (k, h) => (W - 92 * k) * (h - (96 * FAR + 14) * k);
    const k = N ? biggest((k) => N * PER_DUCK * k * k <= room(k, H)) : KMAX;
    while (N * PER_DUCK * k * k > room(k, H)) H += 20; // so many ducks that even small ones need a taller pond
    H = Math.round(H);
    // where a duck's base can go: far enough in that its head, tail and ripples stay on the water
    const x0 = 46 * k, x1 = W - 46 * k, y0 = 96 * FAR * k + 4, y1 = H - 12 * k;
    const depth = (y) => FAR + (1 - FAR) * clamp01((y - y0) / Math.max(1, y1 - y0));
    const pick = (random) => {
      const x = x0 + random() * (x1 - x0), y = y0 + random() * (y1 - y0), p = depth(y);
      return { x, y, p, edge: Math.min(Math.min(x - x0, x1 - x) / (SX * k * p), Math.min(y - y0, y1 - y) / (SY * k * p)) };
    };
    const random = rng(seed);
    const spots = spread(N, k, pick, random);
    const drawn = placeDucks(shown, spots, k, random);
    if (N) {
      // Fit the pond to the ducks, top to bottom, with the same amount of water above and below them.
      const reach = (item) => { const s = spriteFor(item.kind, item.cold); return s ? s.baseY * s.unit : item.cold ? 50 : 80; };
      const top = Math.min(...drawn.map((d) => d.y + (112 - reach(d.item)) * d.k));
      const bottom = Math.max(...drawn.map((d) => d.y + 118 * d.k));
      const fitted = Math.round(Math.min(H, Math.max(W * minAspect, bottom - top + 2 * (14 + 10 * k))));
      const shift = (fitted - (bottom - top)) / 2 - top;
      for (const d of drawn) d.y += shift;
      for (const s of spots) s.y += shift;
      H = fitted;
    }

    // the water, and the lily pads, petals and ripples between the ducks
    const kd = Math.max(0.8, Math.min(1.6, k)); // decorations don't shrink as far as the ducks
    const boxes = spots.map((s) => [s.x - 46 * k * s.p, s.y - 92 * k * s.p, s.x + 46 * k * s.p, s.y + 8 * k * s.p]);
    const clear = (x, y, rx, ry) => x - rx > 10 && x + rx < W - 10 && y - ry > 10 && y + ry < H - 10 &&
      boxes.every(([a, b, c, d]) => x + rx < a || x - rx > c || y + ry < b || y - ry > d);
    const ground = [{ d: roundRect(W, H, 44), fill: WATER.top }];
    const dashes = Math.min(160, Math.round((W * H) / (7000 * k * k)));
    for (let i = 0; i < dashes; i++) {
      const x = random() * W, y = random() * H, p = depth(y), pale = random() < 0.12;
      const len = (pale ? 26 + random() * 22 : 12 + random() * 12) * k * p;
      if (!clear(x, y, len / 2 + 4, 4)) continue;
      ground.push(line(`M${r1(x - len / 2)} ${r1(y)}Q${r1(x)} ${r1(y - len * 0.16)} ${r1(x + len / 2)} ${r1(y)}`,
        r1(Math.max(1.6, (pale ? 2 : 2.4) * k * p)), pale ? WATER.streak : WATER.ripple));
    }
    const pads = Math.round(Math.max(2, Math.min(8, 1.5 + (W * H) / 160000)));
    for (let i = 0, made = 0; i < pads * 4 && made < pads; i++) {
      const x = random() * W, y = random() * H, p = depth(y);
      const r = (17 + random() * 13) * kd * p, ow = r1(2.2 * kd * p);
      if (!clear(x, y, r + 6, r * 0.5 + 6)) continue;
      made++;
      const a = random() * Math.PI * 2, at = (da) => [x + Math.cos(a + da) * r * 1.08, y + Math.sin(a + da) * r * 0.54];
      ground.push(...outlined([{ d: blob(x, y, r, r * 0.5, `pad${seed}${i}`), fill: WATER.pad }], ow),
        { d: poly([[x, y], at(-0.2), at(0.2)]), fill: WATER.top });
      boxes.push([x - r, y - r * 0.5, x + r, y + r * 0.5]);
      if (random() < 0.35) ground.push(...outlined([{ d: blob(x - r * 0.2, y - r * 0.26, r * 0.34, r * 0.24, `lotus${seed}${i}`), fill: WATER.lotus }], r1(ow * 0.8)));
    }
    for (let i = 0, n = 1 + Math.floor(random() * 4); i < n; i++) {
      const x = random() * W, y = random() * H, r = (6 + random() * 3) * kd * depth(y);
      if (clear(x, y, r + 2, r + 2)) ground.push({ d: petal(x, y, r, random() * Math.PI), fill: WATER.petal, stroke: WATER.petalEdge, sw: r1(Math.max(1, 1.2 * kd)) });
    }
    return { width: W, height: H, k, ground, drawn };
  }

  // The themes that have a painted pond, for picking one.
  const pondThemes = () => Object.keys(sprites.ponds).filter((t) => sprites.ponds[t].wide || sprites.ponds[t].tall);

  // In a group pond, a small round badge above each duck's head says whose it is: their color
  // and their mark (a letter, or an emoji). Badges go on top of everything, in depth order.
  function badgeAt(d) {
    const s = spriteFor(d.item.kind, d.item.cold);
    const reach = s ? s.baseY * s.unit : d.item.cold ? 50 : 80;
    return { x: d.x + 42 * d.k, y: d.y + (112 - reach - 12) * d.k, r: Math.max(11 * d.k, 10) };
  }

  // a decoration: koi drift about under the water, floating things bob, and what stands in the water
  // gets a pale line where it meets it
  function decorSVG(o) {
    const img = `<image href="${o.src}" x="${r1(o.x)}" y="${r1(o.y)}" width="${r1(o.w)}" height="${r1(o.h)}"/>`;
    const t = r1(4 + o.r * 2), dl = r1(-o.r * 6);
    if (o.lie === 'under') return `<g class="koi" style="--t:${r1(16 + o.r * 8)}s;--d:${r1(-o.r * 20)}s" opacity=".82">${img}</g>`;
    if (o.lie === 'flat') return `<g class="bob" style="--t:${t}s;--d:${dl}s">${img}</g>`;
    const y = r1(o.base), sw = r1(Math.max(2, o.w * 0.018));
    return `${img}<path d="M${r1(o.cx - o.rx * 0.95)} ${y}Q${r1(o.cx - o.rx * 0.45)} ${r1(o.base - o.ry * 0.25)} ${r1(o.cx)} ${y}T${r1(o.cx + o.rx * 0.95)} ${y}" fill="none" stroke="${WATER.light}" stroke-width="${sw}" stroke-linecap="round" opacity=".8"/>`;
  }

  let svgCount = 0;
  function pondSVG(scene, { cls = '', label = '', people = null } = {}) {
    const prefix = `mori-d${++svgCount}`;
    const defs = new Map([['line', pathsSVG(CONTACT)]]); // each kind of duck, and each ripple, is drawn once and placed many times
    const parts = [pathsSVG(scene.ground)];
    const decor = scene.decor || [];
    for (const o of decor) if (o.lie === 'under') parts.push(decorSVG(o));
    // the ducks and the decorations on the water, from the back of the pond to the front
    const queue = decor.filter((o) => o.lie !== 'under');
    for (const d of scene.drawn) {
      while (queue.length && queue[0].base <= d.y + 112 * d.k) parts.push(decorSVG(queue.shift()));
      const key = d.item.cold ? 'cold' : kindOf(d.item.kind);
      if (!defs.has(key)) defs.set(key, duckInner(d.item.kind, d.item.cold));
      const k = r1(d.k * 1000) / 1000, b = d.bob;
      let inner = `<use href="#${prefix}-cold"/>`; // a cold egg just sits on its lily pad
      if (!d.item.cold) {
        const { n, flip } = ringFor(d.ring);
        if (!defs.has(`ring${n}`)) defs.set(`ring${n}`, ringInner(n));
        const ring = (attrs) => `<use href="#${prefix}-ring${n}"${attrs}/>`;
        const rings = b ? ring(` class="wave" style="--w:${b.w}s;--wd:${b.wd}s"`) + ring(` class="swell" style="--t:${b.t}s;--d:${b.d}s"`) : ring('');
        inner = (flip ? `<g transform="matrix(-1 0 0 1 100 0)">${rings}</g>` : rings) +
          `<g clip-path="url(#${prefix}-cut)"><use href="#${prefix}-${key}"${b ? ` class="bob" style="--t:${b.t}s;--d:${b.d}s"` : ''}/></g><use href="#${prefix}-line"/>`;
      }
      parts.push(`<g transform="matrix(${k} 0 0 ${k} ${r1(d.x)} ${r1(d.y)})">${inner}</g>`);
    }
    for (const o of queue) parts.push(decorSVG(o));
    for (const d of people ? scene.drawn : []) {
      const who = people[d.item.person];
      if (!who) continue;
      const { x, y, r } = badgeAt(d), mark = String(who.mark || '?').replace(/[&<>"']/g, '');
      parts.push(`<g class="duck-badge${d.bob ? ' bob' : ''}"${d.bob ? ` style="--t:${d.bob.t}s;--d:${d.bob.d}s"` : ''}><circle cx="${r1(x)}" cy="${r1(y)}" r="${r1(r)}" fill="${who.color}" stroke="${INK}" stroke-width="${r1(r * 0.2)}"/>` +
        `<text x="${r1(x)}" y="${r1(y)}" font-size="${r1(r * 1.15)}" text-anchor="middle" dominant-baseline="central" fill="#fff" font-weight="700">${mark}</text></g>`);
    }
    const defsSVG = `<clipPath id="${prefix}-cut"><path d="${CUT}"/></clipPath>` + [...defs].map(([key, inner]) => `<g id="${prefix}-${key}">${inner}</g>`).join('');
    return `<svg class="${cls}" viewBox="0 0 ${scene.width} ${scene.height}" role="img" aria-label="${label}"><defs>${defsSVG}</defs>${parts.join('')}</svg>`;
  }

  /* ── canvas versions, for share images ───────────────────────────────────── */
  function drawShapes(ctx, shapes) {
    for (const s of shapes) {
      if (s.img) { ctx.drawImage(s.img, s.x, s.y, s.w, s.h); continue; }
      if (!s.d) continue;
      const path = new Path2D(s.d);
      if (s.fill) { ctx.fillStyle = s.fill; ctx.fill(path); }
      if (s.stroke) {
        ctx.strokeStyle = s.stroke;
        ctx.lineWidth = s.sw;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.stroke(path);
      }
    }
  }
  function drawInBox(ctx, kind, cold, water = false, ring = 0) {
    if (water && !cold) {
      const { n, flip } = ringFor(ring), r = sprites.ripples[n];
      ctx.save();
      if (flip) ctx.transform(-1, 0, 0, 1, 100, 0);
      if (r) { const p = ringAt(r); ctx.drawImage(r.img, p.x, p.y, p.w, p.h); } else drawShapes(ctx, DASHES);
      ctx.restore();
    }
    const s = spriteFor(kind, cold);
    ctx.save();
    if (water && !cold) ctx.clip(new Path2D(CUT));
    if (s) { const p = placed(s); ctx.drawImage(s.img, p.x, p.y, p.w, p.h); }
    else if (cold) drawShapes(ctx, coldEgg());
    else { ctx.transform(-1, 0, 0, 1, 100, 0); drawShapes(ctx, outfit(kindOf(kind))); } // face left
    ctx.restore();
    if (water && !cold) drawShapes(ctx, CONTACT);
  }
  /** Draws a pond scene `width` pixels wide with its top left at (x, y); returns its height. */
  function drawPond(ctx, scene, x, y, width, people = null) {
    const k = width / scene.width;
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(k, k);
    drawShapes(ctx, scene.ground);
    const decor = scene.decor || [], queue = decor.filter((o) => o.lie !== 'under');
    const drawDecor = (o) => {
      if (!o.img) return;
      ctx.globalAlpha = o.lie === 'under' ? 0.82 : 1;
      ctx.drawImage(o.img, o.x, o.y, o.w, o.h);
      ctx.globalAlpha = 1;
    };
    for (const o of decor) if (o.lie === 'under') drawDecor(o);
    for (const d of scene.drawn) {
      while (queue.length && queue[0].base <= d.y + 112 * d.k) drawDecor(queue.shift());
      ctx.save();
      ctx.transform(d.k, 0, 0, d.k, d.x, d.y);
      drawInBox(ctx, d.item.kind, d.item.cold, true, d.ring);
      ctx.restore();
    }
    queue.forEach(drawDecor);
    for (const d of people ? scene.drawn : []) {
      const who = people[d.item.person];
      if (!who) continue;
      const { x: bx, y: by, r } = badgeAt(d);
      ctx.beginPath();
      ctx.arc(bx, by, r, 0, Math.PI * 2);
      ctx.fillStyle = who.color;
      ctx.fill();
      ctx.lineWidth = r * 0.2;
      ctx.strokeStyle = INK;
      ctx.stroke();
      ctx.fillStyle = '#fff';
      ctx.font = `700 ${r * 1.15}px "Zen Kaku Gothic New", system-ui, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(who.mark || '?'), bx, by + r * 0.04);
    }
    ctx.restore();
    return scene.height * k;
  }
  function drawDuck(ctx, kind, x, y, size, cold = false, water = false) {
    const k = size / 100;
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(k, k);
    drawInBox(ctx, kind, cold, water);
    ctx.restore();
  }

  return { KINDS, ORDER, kindOf, duckSVG, duckInner, eggInner, pond, pondSVG, pondThemes, drawShapes, drawPond, drawDuck, loadSprites, ready, sprites, rng, WATER, INK };
})();
