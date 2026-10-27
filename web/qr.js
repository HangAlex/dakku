/* A small QR code maker (byte mode, error correction M, versions 1–10), enough for a link.
   Follows ISO/IEC 18004; the structure mirrors Project Nayuki's reference encoder. */
'use strict';

const QR = (() => {
  // version → [EC codewords per block, [blocks, data codewords], [blocks, data codewords]?] at level M
  const BLOCKS = [null,
    [10, [1, 16]], [16, [1, 28]], [26, [1, 44]], [18, [2, 32]], [24, [2, 43]],
    [16, [4, 27]], [18, [4, 31]], [22, [2, 38], [2, 39]], [22, [3, 36], [2, 37]], [26, [4, 43], [1, 44]]];
  const ALIGN = [null, [], [6, 18], [6, 22], [6, 26], [6, 30], [6, 34], [6, 22, 38], [6, 24, 42], [6, 26, 46], [6, 28, 50]];

  function gfMul(x, y) {
    let z = 0;
    for (let i = 7; i >= 0; i--) {
      z = (z << 1) ^ ((z >>> 7) * 0x11D);
      z ^= ((y >>> i) & 1) * x;
    }
    return z;
  }

  function rsDivisor(degree) {
    const result = new Array(degree).fill(0);
    result[degree - 1] = 1;
    let root = 1;
    for (let i = 0; i < degree; i++) {
      for (let j = 0; j < result.length; j++) {
        result[j] = gfMul(result[j], root);
        if (j + 1 < result.length) result[j] ^= result[j + 1];
      }
      root = gfMul(root, 0x02);
    }
    return result;
  }

  function rsRemainder(data, divisor) {
    const result = divisor.map(() => 0);
    for (const b of data) {
      const factor = b ^ result.shift();
      result.push(0);
      divisor.forEach((coef, i) => { result[i] ^= gfMul(coef, factor); });
    }
    return result;
  }

  const dataCapacity = (v) => BLOCKS[v].slice(1).reduce((n, [count, len]) => n + count * len, 0);

  function codewords(bytes) {
    let version = 0;
    for (let v = 1; v <= 10; v++) {
      const countBits = v < 10 ? 8 : 16;
      if (4 + countBits + bytes.length * 8 <= dataCapacity(v) * 8) { version = v; break; }
    }
    if (!version) throw new Error('Too long for a QR code here');
    const bits = [];
    const put = (value, n) => { for (let i = n - 1; i >= 0; i--) bits.push((value >>> i) & 1); };
    put(0b0100, 4);
    put(bytes.length, version < 10 ? 8 : 16);
    for (const b of bytes) put(b, 8);
    const capacity = dataCapacity(version) * 8;
    put(0, Math.min(4, capacity - bits.length));
    put(0, (8 - bits.length % 8) % 8);
    for (let pad = 0xEC; bits.length < capacity; pad ^= 0xEC ^ 0x11) put(pad, 8);
    const data = [];
    for (let i = 0; i < bits.length; i += 8) data.push(bits.slice(i, i + 8).reduce((a, b) => (a << 1) | b, 0));

    const [ecLen, ...groups] = BLOCKS[version];
    const divisor = rsDivisor(ecLen);
    const blocks = [], ecc = [];
    let k = 0;
    for (const [count, len] of groups) {
      for (let b = 0; b < count; b++) {
        const block = data.slice(k, k + len);
        k += len;
        blocks.push(block);
        ecc.push(rsRemainder(block, divisor));
      }
    }
    const out = [];
    const longest = Math.max(...blocks.map((b) => b.length));
    for (let i = 0; i < longest; i++) for (const b of blocks) if (i < b.length) out.push(b[i]);
    for (let i = 0; i < ecLen; i++) for (const e of ecc) out.push(e[i]);
    return { version, codewords: out };
  }

  function formatBits(mask) {
    const data = (0 << 3) | mask; // level M is 00
    let rem = data;
    for (let i = 0; i < 10; i++) rem = (rem << 1) ^ ((rem >>> 9) * 0x537);
    return ((data << 10) | rem) ^ 0x5412;
  }

  function versionBits(version) {
    let rem = version;
    for (let i = 0; i < 12; i++) rem = (rem << 1) ^ ((rem >>> 11) * 0x1F25);
    return (version << 12) | rem;
  }

  const MASKS = [
    (x, y) => (x + y) % 2 === 0,
    (x, y) => y % 2 === 0,
    (x, y) => x % 3 === 0,
    (x, y) => (x + y) % 3 === 0,
    (x, y) => (Math.floor(x / 3) + Math.floor(y / 2)) % 2 === 0,
    (x, y) => (x * y) % 2 + (x * y) % 3 === 0,
    (x, y) => ((x * y) % 2 + (x * y) % 3) % 2 === 0,
    (x, y) => ((x + y) % 2 + (x * y) % 3) % 2 === 0,
  ];

  /** The module grid for `text`: an array of rows of booleans (true = dark). */
  function matrix(text) {
    const bytes = new TextEncoder().encode(text);
    const { version, codewords: cw } = codewords(bytes);
    const size = version * 4 + 17;
    const modules = Array.from({ length: size }, () => new Array(size).fill(false));
    const fixed = Array.from({ length: size }, () => new Array(size).fill(false));
    const set = (x, y, dark) => { modules[y][x] = dark; fixed[y][x] = true; };

    for (let i = 0; i < size; i++) { set(6, i, i % 2 === 0); set(i, 6, i % 2 === 0); }
    for (const [cx, cy] of [[3, 3], [size - 4, 3], [3, size - 4]]) {
      for (let dy = -4; dy <= 4; dy++) for (let dx = -4; dx <= 4; dx++) {
        const d = Math.max(Math.abs(dx), Math.abs(dy)), x = cx + dx, y = cy + dy;
        if (x >= 0 && x < size && y >= 0 && y < size) set(x, y, d !== 2 && d !== 4);
      }
    }
    const pos = ALIGN[version], last = pos.length - 1;
    pos.forEach((ay, i) => pos.forEach((ax, j) => {
      if ((i === 0 && j === 0) || (i === 0 && j === last) || (i === last && j === 0)) return;
      for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) set(ax + dx, ay + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1);
    }));
    const drawFormat = (mask) => {
      const bits = formatBits(mask), bit = (i) => ((bits >>> i) & 1) === 1;
      for (let i = 0; i <= 5; i++) set(8, i, bit(i));
      set(8, 7, bit(6)); set(8, 8, bit(7)); set(7, 8, bit(8));
      for (let i = 9; i < 15; i++) set(14 - i, 8, bit(i));
      for (let i = 0; i < 8; i++) set(size - 1 - i, 8, bit(i));
      for (let i = 8; i < 15; i++) set(8, size - 15 + i, bit(i));
      set(8, size - 8, true);
    };
    drawFormat(0); // reserve the area
    if (version >= 7) {
      const bits = versionBits(version);
      for (let i = 0; i < 18; i++) {
        const dark = ((bits >>> i) & 1) === 1, a = size - 11 + (i % 3), b = Math.floor(i / 3);
        set(a, b, dark); set(b, a, dark);
      }
    }

    let i = 0;
    for (let right = size - 1; right >= 1; right -= 2) {
      if (right === 6) right = 5;
      for (let vert = 0; vert < size; vert++) {
        for (let j = 0; j < 2; j++) {
          const x = right - j, upward = ((right + 1) & 2) === 0, y = upward ? size - 1 - vert : vert;
          if (!fixed[y][x] && i < cw.length * 8) {
            modules[y][x] = ((cw[i >>> 3] >>> (7 - (i & 7))) & 1) === 1;
            i++;
          }
        }
      }
    }

    const applyMask = (m) => {
      for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) if (!fixed[y][x] && MASKS[m](x, y)) modules[y][x] = !modules[y][x];
    };
    let best = 0, bestScore = Infinity;
    for (let m = 0; m < 8; m++) {
      applyMask(m);
      drawFormat(m);
      const score = penalty(modules);
      if (score < bestScore) { best = m; bestScore = score; }
      applyMask(m); // undo
    }
    applyMask(best);
    drawFormat(best);
    return modules;
  }

  function penalty(grid) {
    const size = grid.length;
    let score = 0, dark = 0;
    const lines = [];
    for (let y = 0; y < size; y++) lines.push(grid[y]);
    for (let x = 0; x < size; x++) lines.push(grid.map((row) => row[x]));
    const finderA = [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0], finderB = finderA.slice().reverse();
    for (const line of lines) {
      let run = 1;
      for (let i = 1; i <= size; i++) {
        if (i < size && line[i] === line[i - 1]) run++;
        else { if (run >= 5) score += run - 2; run = 1; }
      }
      for (let i = 0; i + 11 <= size; i++) {
        let a = true, b = true;
        for (let k = 0; k < 11 && (a || b); k++) {
          const v = line[i + k] ? 1 : 0;
          if (v !== finderA[k]) a = false;
          if (v !== finderB[k]) b = false;
        }
        if (a) score += 40;
        if (b) score += 40;
      }
    }
    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        if (grid[y][x]) dark++;
        if (x + 1 < size && y + 1 < size) {
          const c = grid[y][x];
          if (c === grid[y][x + 1] && c === grid[y + 1][x] && c === grid[y + 1][x + 1]) score += 3;
        }
      }
    }
    score += Math.floor(Math.abs(dark * 20 - size * size * 10) / (size * size)) * 10;
    return score;
  }

  /** An SVG drawing of the code with a four-module quiet zone. */
  function svg(text, { dark = '#1f1d1a', light = '#ffffff' } = {}) {
    const grid = matrix(text), size = grid.length, q = 4, n = size + q * 2;
    let d = '';
    grid.forEach((row, y) => row.forEach((on, x) => { if (on) d += `M${x + q} ${y + q}h1v1h-1z`; }));
    return `<svg viewBox="0 0 ${n} ${n}" shape-rendering="crispEdges" role="img" aria-label="QR code"><rect width="${n}" height="${n}" fill="${light}"/><path d="${d}" fill="${dark}"/></svg>`;
  }

  return { svg, matrix, _test: { rsDivisor, rsRemainder, formatBits, versionBits, codewords } };
})();
