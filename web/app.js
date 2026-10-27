/* 鴨 Dakku — the app.
   Everything you log lands on your PC at home. This page keeps a copy so it opens instantly
   and keeps working without a connection; changes wait in an outbox and sync when it's back.
   The running timer lives on the PC too, so an egg started on one device hatches on all of them.
   Friends you invite get their own ponds here, and anyone in a group with you can join a session
   you're in the middle of: each of you hatches your own duck, for the time you each studied.
   (Inside, a duck's kind is still called `species`, and a cold egg `withered`, from when Dakku grew trees.) */
'use strict';

(() => {
  /* ───────────── helpers ───────────── */
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const MIN = 60_000, HOUR = 60 * MIN, DAY = 24 * HOUR;
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const uid = () => {
    const bytes = new Uint8Array(9);
    crypto.getRandomValues(bytes);
    return btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_');
  };
  const store = {
    get(key, fallback) { try { const v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); } catch { return fallback; } },
    set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* full or blocked */ } },
    del(key) { try { localStorage.removeItem(key); } catch { /* blocked */ } },
  };
  const K = { cache: 'mori:cache', outbox: 'mori:outbox', theme: 'mori:theme', seen: 'mori:seen', mine: 'mori:mine', away: 'mori:away', timer: 'mori:timer', ui: 'mori:ui', join: 'mori:join', cheers: 'mori:cheers', beforeEvent: 'mori:before-event' };

  /* ───────────── constants ───────────── */
  const SPECIES = Art.ORDER;
  // tag colors: [light, dark, kanji, name] in an order checked for color-blind safety
  const PALETTE = [
    ['#D9482B', '#E2603F', '朱', 'Vermilion'], ['#12A37A', '#1C9C73', '若竹', 'Bamboo'], ['#E9A100', '#B88200', '山吹', 'Gold'],
    ['#D9568F', '#D9558C', '牡丹', 'Peony'], ['#2B6CC4', '#4A8BE0', '瑠璃', 'Lapis'], ['#2E8B3A', '#3A9A45', '常磐', 'Evergreen'],
    ['#6C55C8', '#9080E6', '菫', 'Violet'], ['#C9283E', '#E25563', '紅', 'Crimson'],
  ];
  const THEMES = [ // dark, and Sakura, the one light one
    ['ai', '藍', 'Ai', '#0F1727', '#57C7CF'], ['sumi', '墨', 'Sumi', '#151413', '#D9573F'], ['yozakura', '夜桜', 'Yozakura', '#1A1220', '#F29BB8'], ['sakura', '桜', 'Sakura', '#F2DCE5', '#D93D80'],
    ['halloween', '南瓜', 'Halloween', '#16101E', '#FF8A3D'], ['thanksgiving', '感謝', 'Thanksgiving', '#1A1410', '#E3A13B'], ['christmas', '聖夜', 'Christmas', '#0E1A16', '#EC5A5E'],
  ];
  // the events: each one is a theme and a pond together (and what drifts down the screen), any time of year
  const EVENTS = [['halloween', '🎃', 'Bats and jack-o\u2019-lanterns'], ['thanksgiving', '🍂', 'Falling leaves and a harvest pond'], ['christmas', '🎄', 'Snow and a Christmas pond']];
  // things to put on the pond: [id, kanji, name]
  const DECOR = [['torii', '鳥居', 'Torii gate'], ['lantern', '灯籠', 'Stone lantern'], ['koi', '鯉', 'Koi'], ['lanterns', '灯', 'Floating lanterns'], ['lotus', '蓮', 'Lotus']];
  const RANKS = [
    [0, '卵', 'Tamago', 'Egg'], [5, '雛', 'Hina', 'Chick'], [15, '子鴨', 'Kogamo', 'Duckling'], [40, '鴨', 'Kamo', 'Duck'],
    [80, '群', 'Mure', 'Flock'], [150, '池主', 'Ike-nushi', 'Lord of the pond'], [300, '湖主', 'Ko-nushi', 'Lord of the lake'], [600, '鴨仙', 'Kamosen', 'Duck sage'],
  ];
  const WD_KANJI = ['月', '火', '水', '木', '金', '土', '日'];
  const WD_JP = ['月曜日', '火曜日', '水曜日', '木曜日', '金曜日', '土曜日', '日曜日'];
  // the pond for each month, when it follows the seasons (summer is the classic pond)
  const SEASONS = ['winter', 'winter', 'spring', 'spring', 'spring', 'classic', 'classic', 'classic', 'autumn', 'autumn', 'autumn', 'winter'];
  const PONDS = { classic: ['夏', 'Classic'], spring: ['春', 'Spring'], autumn: ['秋', 'Autumn'], winter: ['冬', 'Winter'], night: ['夜', 'Night'], garden: ['庭', 'Garden'], sakura: ['桜', 'Sakura'],
    halloween: ['南瓜', 'Halloween'], thanksgiving: ['感謝', 'Thanksgiving'], christmas: ['聖夜', 'Christmas'], seasonal: ['季', 'Seasonal'] };
  // when the seasonal pond turns into an event's: [month, from day, to day, pond]
  const EVENT_DAYS = [[10, 20, 31, 'halloween'], [11, 20, 30, 'thanksgiving'], [12, 10, 26, 'christmas']];
  const DIAL_MAX = 180;
  const POMO = { focus: 25, brk: 5, rounds: 4 }; // minutes of focus, minutes of break, rounds
  const POMO_LIMITS = { focus: [5, 120, 5], brk: [1, 60, 1], rounds: [1, 12, 1] }; // lowest, highest, step
  const UNDO_MS = 10_000; // a session can be called off this soon after it starts, as if it never began
  // cheers to send someone studying with one tap (or they write their own)
  const CHEERS = ["You've got this! 🔥", 'Keep going! 💪', 'Proud of you 💗', 'Almost there! ✨', 'Go go go! 🦆', '頑張って！'];
  const SURPRISE_SVG = '<svg viewBox="0 0 100 120" aria-hidden="true"><text x="50" y="82" text-anchor="middle" font-size="58" fill="currentColor" opacity=".55" font-family="serif">?</text></svg>';
  const AWAY_GRACE = 15_000;

  /* ───────────── state ───────────── */
  const S = {
    me: null, settings: null, server: null, vapidKey: '', anki: null,
    sessions: new Map(), cursor: 0,
    timer: null, offset: 0,
    outbox: store.get(K.outbox, []),
    reachable: true, syncing: false, live: false, lastSync: 0,
    view: 'plant', range: 'week', rangeOffset: 0, barsN: 14, logDays: 21, logTag: '',
    pick: { minutes: 25, mode: 'timer', tag: '', species: 'matsu', pomo: { focus: 25, brk: 5, rounds: 4 } },
    devices: null, passcode: null, pushSub: null, swReg: null,
    dragging: false, starting: false, ended: null,
    together: null, groupData: {}, groupId: null, groupRange: 'month', boardRange: 'week', admin: null, joinPick: null,
  };

  /* ───────────── time, in your home time zone ───────────── */
  const fmtCache = new Map();
  const formatter = (key, make) => { if (!fmtCache.has(key)) fmtCache.set(key, make()); return fmtCache.get(key); };
  const deviceZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  const zone = () => S.settings?.timeZone || deviceZone();
  function parts(ms, tz = zone()) {
    const f = formatter('p' + tz, () => new Intl.DateTimeFormat('en-US', { timeZone: tz, hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }));
    const o = {};
    for (const p of f.formatToParts(ms)) o[p.type] = p.value;
    return o;
  }
  const dayKey = (ms) => { const p = parts(ms); return `${p.year}-${p.month}-${p.day}`; };
  const hourOf = (ms) => +parts(ms).hour % 24;
  const keyUTC = (k) => Date.UTC(+k.slice(0, 4), +k.slice(5, 7) - 1, +k.slice(8, 10));
  const utcKey = (u) => new Date(u).toISOString().slice(0, 10);
  const addDays = (k, n) => utcKey(keyUTC(k) + n * DAY);
  const weekday = (k) => (new Date(keyUTC(k)).getUTCDay() + 6) % 7; // Mon 0 … Sun 6
  const isWeekday = (k) => weekday(k) < 5;
  const todayKey = () => dayKey(Date.now());
  function zonedMs(key, hhmm, tz = zone()) {
    const [h, m] = hhmm.split(':').map(Number);
    const want = Date.UTC(+key.slice(0, 4), +key.slice(5, 7) - 1, +key.slice(8, 10), h, m);
    let ms = want;
    for (let i = 0; i < 3; i++) {
      const p = parts(ms, tz);
      ms += want - Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour % 24, +p.minute);
    }
    return ms;
  }
  const fmtDate = (k, opts) => formatter('d' + JSON.stringify(opts), () => new Intl.DateTimeFormat(undefined, { ...opts, timeZone: 'UTC' })).format(keyUTC(k));
  const fmtTime = (ms) => formatter('t' + zone(), () => new Intl.DateTimeFormat(undefined, { timeZone: zone(), hour: 'numeric', minute: '2-digit' })).format(ms);
  const fmtMin = (m) => (m < 60 ? `${m} min` : `${Math.floor(m / 60)}h${m % 60 ? ` ${m % 60}m` : ''}`);
  const fmtHours = (m) => { const h = m / 60; return h >= 100 ? Math.round(h).toLocaleString() : (Math.round(h * 10) / 10).toString(); };
  const plural = (n, word, many = word + 's') => `${n.toLocaleString()} ${n === 1 ? word : many}`;
  function fmtClock(ms, round = Math.ceil) {
    const s = Math.max(0, round(ms / 1000));
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), ss = s % 60;
    const two = (n) => String(n).padStart(2, '0');
    return h ? `${h}:${two(m)}:${two(ss)}` : `${two(m)}:${two(ss)}`;
  }
  function ago(ms) {
    const d = Date.now() - ms;
    if (d < 90_000) return 'just now';
    if (d < HOUR) return `${Math.round(d / MIN)} min ago`;
    if (d < DAY) return `${Math.round(d / HOUR)} h ago`;
    return `${Math.round(d / DAY)} d ago`;
  }
  const serverNow = () => Date.now() + S.offset;

  /* ───────────── derived numbers ───────────── */
  let D = null;
  const invalidate = () => { D = null; };
  function derive() {
    if (D) return D;
    const goal = S.settings.goal;
    const list = [...S.sessions.values()].filter((s) => !s.deleted).sort((a, b) => a.start - b.start);
    const byDay = new Map(), byTag = new Map(), bySpecies = new Map();
    let total = 0, trees = 0, withered = 0, longest = 0, run = 0, bestRun = 0, early = false, night = false;
    for (const s of list) {
      s._day = dayKey(s.start);
      if (s.status === 'withered') { withered++; run = 0; continue; }
      trees++;
      run++;
      bestRun = Math.max(bestRun, run);
      total += s.minutes;
      longest = Math.max(longest, s.minutes);
      byDay.set(s._day, (byDay.get(s._day) || 0) + s.minutes);
      const tag = s.tag || 'Untagged';
      byTag.set(tag, (byTag.get(tag) || 0) + s.minutes);
      const kind = Art.kindOf(s.species);
      bySpecies.set(kind, (bySpecies.get(kind) || 0) + 1);
      const h = hourOf(s.start);
      if (h >= 4 && h < 7 && s.minutes >= 10) early = true;
      if ((h >= 23 || h < 4) && s.minutes >= 10) night = true;
    }
    const today = todayKey();
    const { current, best, freezes, frozen } = streaks(byDay, goal, today);
    D = { list, byDay, byTag, bySpecies, total, trees, withered, longest, bestRun, early, night, today, goal, streak: current, best, freezes, frozen };
    return D;
  }
  // The weekday rule, with streak freezes: every 7 days in a row earns one (you can hold 2), and a
  // missed weekday uses one up instead of breaking the streak. The same rules as the PC's (logic.py).
  const FREEZE_EVERY = 7, FREEZE_MAX = 2;
  function streaks(byDay, goal, today) {
    const out = { current: 0, best: 0, freezes: 0, frozen: new Set() };
    if (!byDay.size) return out;
    let first = today;
    for (const k of byDay.keys()) if (k < first) first = k;
    let run = 0, freezes = 0;
    for (let k = first; k <= today; k = addDays(k, 1)) {
      if ((byDay.get(k) || 0) >= goal) {
        out.best = Math.max(out.best, ++run);
        if (run % FREEZE_EVERY === 0) freezes = Math.min(FREEZE_MAX, freezes + 1);
      } else if (k !== today && isWeekday(k)) {
        if (freezes) { freezes--; out.frozen.add(k); } else run = 0;
      }
    }
    return { ...out, current: run, freezes };
  }
  const FREEZE_TIP = `Streak freezes: you earn one for every ${FREEZE_EVERY} days in a row (up to ${FREEZE_MAX}), and each covers one missed weekday.`;
  const unlocked = () => SPECIES; // every duck is yours from the start
  const rankFor = (minutes) => {
    let i = 0;
    while (i + 1 < RANKS.length && minutes >= RANKS[i + 1][0] * 60) i++;
    return { i, rank: RANKS[i], next: RANKS[i + 1] || null };
  };
  const tagColor = (name) => {
    const tag = S.settings?.tags.find((t) => t.name.toLowerCase() === String(name || '').toLowerCase());
    const color = tag ? tag.color : 'var(--ink-3)';
    if (tag) { const hit = PALETTE.find((p) => p[0].toLowerCase() === color.toLowerCase()); if (hit) return lightTheme() ? hit[0] : hit[1]; } // the dark themes' step
    return color;
  };
  const lightTheme = () => document.documentElement.dataset.theme === 'sakura';
  const speciesName = (sp) => { const k = Art.KINDS[Art.kindOf(sp)]; return `${k.kanji} ${k.name}`; };
  const myId = () => S.me?.person?.id || 'me';
  const personOf = (id) => S.together?.people?.find((p) => p.id === id) || (id === myId() ? S.me?.person : null) || { id, name: 'Someone', color: '#5F6880', mark: '?' };
  const nameOf = (id) => (id === myId() ? 'You' : personOf(id).name);
  const inGroups = () => !!S.together?.groups?.length;
  const peopleMap = (list) => Object.fromEntries((list || S.together?.people || []).map((p) => [p.id, p]));
  const badgeHTML = (p, cls = '') => `<span class="pbadge ${cls}" style="--c:${esc(p.color)}" title="${esc(p.name)}">${esc(p.mark || '?')}</span>`;
  // which pond picture to use: "seasonal" follows the month (and the events, around their days); a theme
  // without a picture yet falls back to the classic pond
  function themeFor(pref) {
    let t = pref || 'classic';
    if (pref === 'seasonal') {
      const month = +todayKey().slice(5, 7), day = +todayKey().slice(8, 10);
      const event = EVENT_DAYS.find(([m, a, b, pond]) => m === month && day >= a && day <= b && Art.pondThemes().includes(pond));
      t = event ? event[3] : SEASONS[month - 1];
    }
    return Art.pondThemes().includes(t) ? t : 'classic';
  }
  // the pond for a scene: its picture, and your decorations on it
  const pondOpts = (pref) => ({ theme: themeFor(pref), decor: S.settings?.decor || [] });
  const isMine = (id) => store.get(K.mine, []).includes(id);
  const markMine = (id) => store.set(K.mine, [id, ...store.get(K.mine, []).filter((x) => x !== id)].slice(0, 30));
  const seen = (id) => store.get(K.seen, []).includes(id);
  const markSeen = (id) => store.set(K.seen, [id, ...store.get(K.seen, []).filter((x) => x !== id)].slice(0, 60));

  /* ───────────── talking to the PC ───────────── */
  class Offline extends Error {}
  async function api(method, path, body, { timeout = 12_000 } = {}) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeout);
    let res;
    try {
      res = await fetch(path, {
        method, credentials: 'same-origin', cache: 'no-store', signal: ctrl.signal,
        headers: { 'X-Mori': '1', ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}) },
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch {
      setReachable(false);
      throw new Offline('offline');
    } finally {
      clearTimeout(timer);
    }
    setReachable(true);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(data.error || `Something went wrong (${res.status}).`);
      err.status = res.status;
      err.data = data;
      if (res.status === 401 && data.needsLogin) signedOut();
      throw err;
    }
    return data;
  }
  function setReachable(ok) {
    if (S.reachable === ok) return;
    S.reachable = ok;
    paintSync();
    if (ok) { flush(); connectLive(); }
  }

  function saveCache() {
    if (!S.settings) return;
    store.set(K.cache, {
      v: 1, me: S.me, settings: S.settings, server: S.server, vapidKey: S.vapidKey, anki: S.anki, cursor: S.cursor, together: S.together,
      timer: S.timer && !S.timer.local ? S.timer : null, offset: S.offset,
      sessions: [...S.sessions.values()].map(({ _day, ...s }) => s),
    });
    if (S.timer?.local) store.set(K.timer, S.timer); else store.del(K.timer);
  }
  function loadCache(c) {
    S.me = c.me; S.settings = c.settings; S.server = c.server; S.vapidKey = c.vapidKey || ''; S.anki = c.anki; S.together = c.together || null;
    markDemo();
    S.cursor = c.cursor || 0; S.offset = c.offset || 0;
    S.sessions = new Map((c.sessions || []).map((s) => [s.id, s]));
    S.timer = store.get(K.timer, null) || c.timer || null;
    for (const op of S.outbox) applyOp(op);
    adoptSettings();
  }

  function adoptSettings() {
    const s = S.settings;
    S.pick = { minutes: s.minutes, mode: s.mode, tag: s.tag, species: s.species, pomo: { ...POMO, ...s.pomo } };
    applyTheme();
    invalidate();
  }

  function applyBootstrap(data) {
    S.me = data.me; S.server = data.server; S.vapidKey = data.vapidKey; S.anki = data.anki; S.together = data.together || null;
    markDemo();
    S.sessions = new Map(data.sessions.map((s) => [s.id, s]));
    S.cursor = data.cursor;
    for (const op of S.outbox) applyOp(op);
    S.settings = mergePendingSettings(data.settings);
    adoptSettings();
    applyTimer(data.timer, data.now);
    S.lastSync = Date.now();
    saveCache();
  }
  function mergePendingSettings(settings) {
    for (const op of S.outbox) if (op.op === 'settings') settings = { ...settings, ...op.patch };
    return settings;
  }

  function applyPull(res) {
    for (const s of res.sessions || []) {
      if (s.deleted) S.sessions.delete(s.id);
      else S.sessions.set(s.id, s);
    }
    S.cursor = Math.max(S.cursor, res.cursor || 0);
    for (const op of S.outbox) applyOp(op);
    if (res.settings) {
      const before = JSON.stringify(S.settings);
      S.settings = mergePendingSettings(res.settings);
      if (JSON.stringify(S.settings) !== before && !S.dragging) {
        const was = JSON.parse(before);
        const pickChanged = ['minutes', 'mode', 'tag', 'species'].some((k) => S.settings[k] !== was[k]) || JSON.stringify(S.settings.pomo) !== JSON.stringify(was.pomo);
        if (pickChanged && !S.timer) S.pick = { minutes: S.settings.minutes, mode: S.settings.mode, tag: S.settings.tag, species: S.settings.species, pomo: { ...POMO, ...S.settings.pomo } };
        applyTheme();
      }
    }
    if ('timer' in res) applyTimer(res.timer, res.now);
    S.lastSync = Date.now();
    invalidate();
    saveCache();
    checkEnded();
    render();
  }

  function applyOp(op) {
    if (op.op === 'upsert') {
      const old = S.sessions.get(op.session.id);
      if (old && old.updated > op.session.updated) return;
      S.sessions.set(op.session.id, { tag: '', species: 'matsu', status: 'done', source: 'mori', manual: false, note: '', ...old, ...op.session, deleted: false });
    } else if (op.op === 'delete') {
      S.sessions.delete(op.id);
    } else if (op.op === 'settings' && S.settings) {
      S.settings = { ...S.settings, ...op.patch };
    }
    invalidate();
  }

  function enqueue(op) {
    if (op.op === 'settings') {
      // (not into one that's on its way to the PC: what's added to it now would never be sent)
      const prev = S.outbox.find((o) => o.op === 'settings' && !o.sending);
      if (prev) { Object.assign(prev.patch, op.patch); op = null; }
    }
    if (op) S.outbox.push(op);
    store.set(K.outbox, S.outbox);
    if (op) applyOp(op);
    saveCache();
    paintSync();
    flushSoon();
  }

  let flushTimer = 0;
  const flushSoon = (ms = 400) => { clearTimeout(flushTimer); flushTimer = setTimeout(flush, ms); };
  let flushing = null;
  function flush() {
    if (!S.settings) return Promise.resolve();
    if (flushing) return flushing;
    flushing = (async () => {
      S.syncing = true;
      paintSync();
      try {
        await reconcileTimer();
        while (S.outbox.length) {
          // settings changed while the last ones were on their way, or before a failed send: one patch, latest last
          const pending = S.outbox.filter((o) => o.op === 'settings');
          if (pending.length > 1) {
            Object.assign(pending[0].patch, ...pending.slice(1).map((o) => o.patch));
            S.outbox = S.outbox.filter((o) => o.op !== 'settings' || o === pending[0]);
          }
          const batch = S.outbox.slice(0, 400);
          const settingsOp = batch.find((o) => o.op === 'settings');
          if (settingsOp) settingsOp.sending = true;
          const ops = batch.filter((o) => o.op === 'upsert' || o.op === 'delete');
          const drops = batch.filter((o) => o.op === 'drop');
          for (const d of drops) await api('POST', '/api/timer', { action: 'drop', id: d.id }).catch((e) => { if (e instanceof Offline) throw e; });
          let res;
          try {
            res = await api('POST', '/api/sync', { ops, since: S.cursor, ...(settingsOp ? { settings: settingsOp.patch } : {}) });
          } catch (err) {
            if (err instanceof Offline || !err.status || err.status >= 500 || err.status === 401) throw err;
            res = await sendOneByOne(ops, settingsOp); // something in the batch was refused: keep the rest
          }
          S.outbox = S.outbox.filter((o) => !batch.includes(o));
          store.set(K.outbox, S.outbox);
          applyPull(res);
        }
        if (Date.now() - S.lastSync > 2000) applyPull(await api('GET', `/api/sync?since=${S.cursor}`));
      } catch (err) {
        if (!(err instanceof Offline) && err.status !== 401) console.warn('sync', err);
      } finally {
        S.syncing = false;
        flushing = null;
        paintSync();
      }
    })();
    return flushing;
  }
  async function sendOneByOne(ops, settingsOp) {
    let res = null;
    for (const op of ops) {
      try { res = await api('POST', '/api/sync', { ops: [op], since: S.cursor }); }
      catch (err) { if (err instanceof Offline || err.status >= 500) throw err; toast(`A change couldn't be saved: ${err.message}`); }
    }
    if (settingsOp) res = await api('POST', '/api/sync', { ops: [], since: S.cursor, settings: settingsOp.patch }).catch(() => res);
    return res || api('GET', `/api/sync?since=${S.cursor}`);
  }

  async function pull() {
    try { applyPull(await api('GET', `/api/sync?since=${S.cursor}`)); } catch { /* offline: try later */ }
  }

  // live updates from the PC
  let es = null, esRetry = 0;
  function connectLive() {
    if (es || !('EventSource' in window) || !S.settings || document.hidden) return;
    es = new EventSource('/api/events');
    es.addEventListener('change', (e) => {
      try {
        const d = JSON.parse(e.data);
        if (d.timer !== undefined) applyTimer(d.timer, d.timer?.now);
        if (d.rev > S.cursor) pull(); else paintTimer();
        if (d.together) refreshTogether();
      } catch { /* ignore a bad event */ }
    });
    es.onopen = () => { S.live = true; esRetry = 0; setReachable(true); paintSync(); };
    es.onerror = () => {
      S.live = false;
      paintSync();
      if (es && es.readyState === EventSource.CLOSED) {
        es = null;
        setTimeout(connectLive, Math.min(30_000, 2000 * 2 ** esRetry++));
      }
    };
  }
  function disconnectLive() { if (es) { es.close(); es = null; S.live = false; } }

  // your groups, the people in them, and who's studying right now
  let togetherTimer = 0;
  function refreshTogether(wait = 500) {
    clearTimeout(togetherTimer);
    togetherTimer = setTimeout(async () => {
      try {
        S.together = await api('GET', '/api/together');
        saveCache();
        if (S.view === 'together') renderTogether();
        else {
          S.groupData = {}; // a duck may have hatched: the group ponds are fetched fresh next time
          if (S.view === 'plant') { renderPlantSide(); renderPlantControls(); }
        }
      } catch { /* offline: try later */ }
    }, wait);
  }

  /* ───────────── the timer ───────────── */
  const elapsedOf = (t, now = serverNow()) => t.acc + (t.runFrom != null ? Math.max(0, now - t.runFrom) : 0);
  const timed = (t) => t.mode === 'timer' || t.mode === 'pomo'; // it runs out by itself
  const remainingOf = (t, now) => (timed(t) ? Math.max(0, t.planned - elapsedOf(t, now)) : null);
  const growthOf = (t, now) => (t.mode === 'pomo' ? pomoFocus(t, elapsedOf(t, now)) / (t.pomo.focus * t.pomo.rounds)
    : t.mode === 'timer' ? elapsedOf(t, now) / t.planned : Math.min(1, elapsedOf(t, now) / (Math.max(5, S.settings.minutes) * MIN)));
  // for someone who joined: how long until the session they joined ends (null when it's open-ended)
  const hostLeft = (t, now = serverNow()) => (t.hostTimer && timed(t.hostTimer) ? Math.max(0, t.hostTimer.planned - elapsedOf(t.hostTimer, now)) : null);
  // A pomodoro: rounds of focus with a break after each but the last. Only the focus counts toward the duck.
  // (On a running timer the lengths are in ms; in the settings and the pick, in minutes.)
  function pomoFocus(t, el) {
    const p = t.pomo, cycle = p.focus + p.brk, e = Math.max(0, el);
    const whole = Math.floor(e / cycle);
    return Math.min(p.rounds * p.focus, whole * p.focus + Math.min(e - whole * cycle, p.focus));
  }
  function pomoPhase(t, el) {
    const p = t.pomo, cycle = p.focus + p.brk, e = clamp(el, 0, t.planned);
    const i = Math.floor(e / cycle), rest = e - i * cycle;
    if (i >= p.rounds) return { round: p.rounds, phase: 'focus', left: 0, part: p.focus };
    return rest < p.focus ? { round: i + 1, phase: 'focus', left: p.focus - rest, part: p.focus } : { round: i + 1, phase: 'break', left: cycle - rest, part: p.brk };
  }
  const pomoRounds = (t, el) => (el < t.pomo.focus ? 0 : Math.min(t.pomo.rounds, Math.floor((el - t.pomo.focus) / (t.pomo.focus + t.pomo.brk)) + 1));
  const pomoMs = (p) => ({ focus: p.focus * MIN, brk: p.brk * MIN, rounds: p.rounds });
  const pomoPlanned = (p) => p.rounds * p.focus * MIN + (p.rounds - 1) * p.brk * MIN;
  const pomoMinutes = (p) => ({ focus: Math.round(p.focus / MIN), brk: Math.round(p.brk / MIN), rounds: p.rounds });
  // how long a timer's person has studied (ms): a pomodoro's breaks don't count
  // on a pomodoro's break (yours, or the one you joined), leaving Dakku is fine, even in deep focus
  const onBreak = (t) => { const h = t.mode === 'pomo' ? t : t.mode === 'room' && t.hostTimer?.mode === 'pomo' ? t.hostTimer : null; return !!h && pomoPhase(h, elapsedOf(h)).phase === 'break'; };
  const studiedOf = (t, now) => (t.mode === 'pomo' ? pomoFocus(t, elapsedOf(t, now)) : elapsedOf(t, now));
  // a session just started can still be called off, for its first ten seconds
  const undoLeft = (t, now = serverNow()) => (t && !t.pending && isMine(t.id) ? Math.max(0, UNDO_MS - (now - t.startedAt)) : 0);

  function applyTimer(t, now) {
    if (now) S.offset = now - Date.now();
    if (t) cheersIn(t);
    const prev = S.timer;
    if (prev?.local) {
      // this device is carrying a timer on by itself; the PC's view doesn't replace it
      if (t && t.id === prev.id && !prev.detached) { S.timer = { ...t }; saveCache(); }
      paintTimer();
      return;
    }
    if (prev?.pending && !t) return; // our start is still on its way
    S.timer = t ? { ...t } : null;
    if (prev && (!t || t.id !== prev.id)) timerGone(prev);
    if (t && !prev && S.view === 'plant') renderPlantControls();
    paintTimer();
  }

  function timerGone(prev) {
    S.ended = { id: prev.id, at: Date.now(), timer: prev, mine: isMine(prev.id) };
    checkEnded();
  }
  function checkEnded() {
    const e = S.ended;
    if (!e) return;
    const s = S.sessions.get(e.id);
    if (s) {
      S.ended = null;
      const watching = e.mine || (S.view === 'plant' && !document.hidden);
      if (!seen(s.id) && watching && s.status === 'done' && Date.now() - (s.start + s.minutes * MIN) < 6 * HOUR) celebrate(s);
      else markSeen(s.id);
    } else if (Date.now() - e.at > 20_000) S.ended = null;
  }

  async function startTimer() {
    if (S.timer || S.starting) return;
    unlockAudio();
    const avail = unlocked();
    const species = S.settings.randomSpecies ? avail[Math.floor(Math.random() * avail.length)] : (avail.includes(S.pick.species) ? S.pick.species : 'matsu');
    const now = serverNow();
    const pomo = S.pick.mode === 'pomo' ? { ...S.pick.pomo } : null;
    const t = {
      id: uid(), mode: S.pick.mode, planned: S.pick.mode === 'timer' ? S.pick.minutes * MIN : pomo ? pomoPlanned(pomo) : null,
      startedAt: now, acc: 0, runFrom: now, tag: S.pick.tag, species, deep: !!S.settings.deepFocus,
      source: 'mori', device: S.me?.device?.name || 'This device', updated: now, pending: true, open: S.settings.openSessions !== false,
      ...(pomo ? { pomo: pomoMs(pomo) } : {}),
    };
    markMine(t.id);
    S.starting = true;
    S.timer = t;
    renderPlantControls();
    paintTimer();
    wakeLock(true);
    try {
      const res = await api('POST', '/api/timer', { action: 'start', id: t.id, mode: t.mode, minutes: S.pick.minutes, tag: t.tag, species, deep: t.deep, source: 'mori', open: t.open, pomo });
      S.timer = null;
      applyTimer(res.timer, res.timer?.now);
      if (res.session) { S.sessions.set(res.session.id, res.session); invalidate(); celebrate(res.session); }
    } catch (err) {
      if (err instanceof Offline) {
        S.timer = { ...t, pending: false, local: true };
        toast("Your PC can't be reached. This egg hatches here and syncs later.");
      } else if (err.status === 409 && err.data?.timer) {
        S.timer = null;
        applyTimer(err.data.timer, err.data.timer.now);
        toast(`An egg is already hatching on ${err.data.timer.device}.`);
      } else {
        S.timer = null;
        toast(err.message);
      }
    } finally {
      S.starting = false;
      saveCache();
      renderPlantControls();
      paintTimer();
    }
  }

  function localAction(t, action, now) {
    if (action === 'pause' && t.runFrom != null) { t.acc += now - t.runFrom; t.runFrom = null; }
    if (action === 'resume' && t.runFrom == null) t.runFrom = now;
    t.updated = now;
  }

  async function timerAction(action, extra = {}) {
    const t = S.timer;
    if (!t || t.pending) return;
    const now = serverNow();
    if (t.local) return finishLocalAction(t, action, now, extra);
    const before = { ...t };
    const guest = t.mode === 'room';
    if (action === 'pause' || action === 'resume') { localAction(t, action, now); paintTimer(); }
    try {
      const res = await api('POST', '/api/timer', { action, id: t.id, ...extra });
      if (action === 'finish' || action === 'cancel') {
        if (res.session) {
          S.sessions.set(res.session.id, res.session);
          invalidate();
          markSeen(res.session.id);
          if (res.session.status === 'withered') showWithered(res.session); else celebrate(res.session);
        } else if (!res.session) toast(extra.undo ? 'Called off: no egg, nothing logged.' : action === 'cancel' ? 'Under a minute, so nothing was logged.' : 'Under a minute: nothing to log.');
        S.timer = null;
        S.ended = null;
      }
      applyTimer(res.timer, res.timer?.now ?? null);
      pull();
    } catch (err) {
      if (err instanceof Offline && guest) {
        // a session you joined lives on the PC: it keeps counting your time there
        S.timer = before;
        paintTimer();
        toast("Can't reach the session right now. Your time keeps counting there.");
        return;
      }
      if (err instanceof Offline) {
        // carry on here; tell the PC to forget its copy once it can hear us again
        S.timer = { ...before, local: true, detached: true };
        enqueue({ op: 'drop', id: t.id });
        return finishLocalAction(S.timer, action, now, extra);
      }
      if (err.status === 409) { S.timer = null; applyTimer(err.data?.timer ?? null); pull(); return; }
      toast(err.message);
      S.timer = before;
      paintTimer();
    }
  }

  function finishLocalAction(t, action, now, extra) {
    if (action === 'pause' || action === 'resume') {
      localAction(t, action, now);
      saveCache();
      paintTimer();
      return;
    }
    const elapsed = studiedOf(t, now);
    let minutes = Math.round(elapsed / MIN);
    if (t.mode === 'timer') minutes = Math.min(minutes, Math.round(t.planned / MIN));
    if (t.mode === 'pomo') minutes = Math.min(minutes, Math.round((t.pomo.focus * t.pomo.rounds) / MIN));
    const status = action === 'cancel' ? 'withered' : 'done';
    if (status === 'withered') minutes = Math.floor(elapsed / MIN);
    S.timer = null;
    saveCache();
    if (extra.undo) { toast('Called off: no egg, nothing logged.'); render(); return; }
    if (minutes < 1) { toast('Under a minute: nothing to log.'); render(); return; }
    // the PC may log this timer by itself when it runs out; make sure this device's ending wins
    const serverEnd = t.startedAt + (t.planned ?? 240 * MIN) + 1000;
    const session = {
      id: t.id, start: t.startedAt, minutes, tag: t.tag, species: t.species, status, source: t.source || 'mori', manual: false,
      rounds: t.mode === 'pomo' ? pomoRounds(t, elapsedOf(t, now)) : 0,
      note: extra.reason === 'left' ? 'Left Dakku during deep focus' : '', updated: Math.max(now, t.detached ? serverEnd : now),
    };
    enqueue({ op: 'upsert', session });
    const already = seen(t.id);
    markSeen(t.id);
    if (status === 'withered') showWithered(S.sessions.get(t.id));
    else if (!already) celebrate(S.sessions.get(t.id));
    render();
  }

  // once the PC is reachable again: hand a timer this device carried on back to it
  async function reconcileTimer() {
    const t = S.timer;
    if (!t?.local) return;
    const { timer: server, ...res } = await api('GET', `/api/sync?since=${S.cursor}`);
    applyPull(res);
    if (!S.timer?.local) return;
    if (S.sessions.has(t.id) && !S.outbox.some((o) => o.op === 'upsert' && o.session.id === t.id)) {
      if (!server || server.id !== t.id) return; // the PC already logged it; this device logs its own ending later
    }
    if (server && server.id !== t.id) return; // another egg is hatching on the PC; this one finishes here
    if (server && server.id === t.id) await api('POST', '/api/timer', { action: 'drop', id: t.id });
    S.outbox = S.outbox.filter((o) => !(o.op === 'drop' && o.id === t.id));
    store.set(K.outbox, S.outbox);
    const now = serverNow();
    try {
      const out = await api('POST', '/api/timer', {
        action: 'start', id: t.id, mode: t.mode, minutes: t.planned ? Math.round(t.planned / MIN) : S.settings.minutes, tag: t.tag,
        species: t.species, deep: t.deep, source: t.source, startedAt: t.startedAt, elapsed: elapsedOf(t, now), running: t.runFrom != null,
        pomo: t.pomo ? pomoMinutes(t.pomo) : undefined,
      });
      S.timer = null;
      if (out.session) { S.sessions.set(out.session.id, out.session); invalidate(); }
      applyTimer(out.timer, out.timer?.now);
      saveCache();
    } catch (err) {
      if (err instanceof Offline) throw err;
      // the PC wouldn't take it: keep it here
    }
  }

  // called every quarter second while a timer shows
  const phases = new Map(); // where each pomodoro on this screen was last time, to ring when it moves on
  function tickTimer() {
    const t = S.timer;
    if (!t) return;
    const pomo = t.mode === 'pomo' ? t : t.mode === 'room' && t.hostTimer?.mode === 'pomo' ? t.hostTimer : null;
    if (pomo && pomo.runFrom != null && remainingOf(pomo) > 0) {
      const ph = pomoPhase(pomo, elapsedOf(pomo)), key = `${ph.round}:${ph.phase}`, was = phases.get(t.id);
      phases.set(t.id, key);
      if (was && was !== key) {
        if (!document.hidden) chime();
        toast(ph.phase === 'break' ? `Break time: ${fmtMin(Math.round(pomo.pomo.brk / MIN))}. Round ${ph.round} of ${pomo.pomo.rounds} done.` : `Back to focus: round ${ph.round} of ${pomo.pomo.rounds}.`, 4000);
      }
    }
    if (timed(t) && t.runFrom != null && remainingOf(t) <= 0) {
      if (!rung.has(t.id)) {
        rung.add(t.id);
        if (!document.hidden) chime();
        if (t.local) { finishLocalAction(t, 'finish', serverNow(), {}); return; }
        // the PC finishes timers by itself within a second; celebrate as soon as we hear
        const minutes = Math.round((t.mode === 'pomo' ? t.pomo.focus * t.pomo.rounds : t.planned) / MIN);
        const optimistic = { id: t.id, start: t.startedAt, minutes, tag: t.tag, species: t.species, status: 'done', rounds: t.mode === 'pomo' ? t.pomo.rounds : 0 };
        if (!seen(t.id)) { markSeen(t.id); celebrate(optimistic); }
        setTimeout(() => { if (S.timer && S.timer.id === t.id) timerAction('finish'); }, 3500);
      }
    }
    if (t.mode === 'stopwatch' && elapsedOf(t) >= 240 * MIN && t.local && !rung.has(t.id)) { rung.add(t.id); finishLocalAction(t, 'finish', serverNow(), {}); }
  }
  const rung = new Set(); // timers that reached zero on this screen

  /* ───────────── sound, screen, leaving the app ───────────── */
  let actx = null;
  function unlockAudio() {
    try {
      actx ||= new (window.AudioContext || window.webkitAudioContext)();
      if (actx.state === 'suspended') actx.resume();
    } catch { actx = null; }
  }
  function chime() {
    if (!S.settings?.sound || !actx) return;
    try {
      const strike = (at, base, gain) => {
        const out = actx.createGain();
        out.gain.value = gain;
        out.connect(actx.destination);
        for (const [ratio, level, decay] of [[1, 0.55, 3.6], [2.76, 0.2, 2.2], [5.4, 0.09, 1.3], [8.93, 0.04, 0.8]]) {
          const osc = actx.createOscillator(), env = actx.createGain();
          osc.type = 'sine';
          osc.frequency.value = base * ratio;
          env.gain.setValueAtTime(0.0001, at);
          env.gain.exponentialRampToValueAtTime(level, at + 0.012);
          env.gain.exponentialRampToValueAtTime(0.0001, at + decay);
          osc.connect(env);
          env.connect(out);
          osc.start(at);
          osc.stop(at + decay + 0.05);
        }
      };
      const t0 = actx.currentTime + 0.03;
      strike(t0, 523.25, 0.5);  // a small temple bell (rin), struck twice
      strike(t0 + 1.1, 659.25, 0.35);
    } catch { /* no sound then */ }
  }

  let lock = null;
  async function wakeLock(on) {
    if (!('wakeLock' in navigator)) return;
    if (on && !lock && S.settings?.keepAwake && !document.hidden && S.timer && S.view === 'plant') {
      try {
        lock = await navigator.wakeLock.request('screen');
        lock.addEventListener('release', () => { lock = null; });
      } catch { lock = null; }
    } else if (!on && lock) {
      lock.release().catch(() => {});
      lock = null;
    }
  }

  function noteAway() {
    const t = S.timer;
    if (t && t.deep && t.runFrom != null && isMine(t.id) && !onBreak(t) && !store.get(K.away, null)) store.set(K.away, { id: t.id, at: Date.now() });
  }
  function checkAway() {
    const away = store.get(K.away, null);
    store.del(K.away);
    if (!away || Date.now() - away.at < AWAY_GRACE) return;
    const t = S.timer;
    if (t && t.id === away.id && t.runFrom != null) {
      timerAction('cancel', { reason: 'left' });
      return;
    }
    const s = S.sessions.get(away.id);
    if (s && s.status === 'done' && away.at < s.start + s.minutes * MIN - 5000) {
      // it hatched while you were elsewhere, so the egg goes cold after all
      enqueue({ op: 'upsert', session: { id: s.id, status: 'withered', note: 'Left Dakku during deep focus', updated: serverNow() } });
      $('#done').hidden = true;
      showWithered(S.sessions.get(s.id));
      render();
    }
  }

  /* ───────────── navigation ───────────── */
  const VIEWS = ['plant', 'forest', 'together', 'stats', 'log', 'settings'];
  // the addresses: #hatch and #pond (the views inside are still called plant and forest; old links work too)
  const ROUTES = { hatch: 'plant', pond: 'forest' };
  function paintTabs() {
    $('#tabbar a[data-tab="together"]').hidden = !inGroups() && S.me?.role !== 'owner';
  }
  function route() {
    const name = location.hash.replace('#', '').split('?')[0];
    const view = VIEWS.includes(ROUTES[name] || name) ? ROUTES[name] || name : 'plant';
    if (view !== S.view || !$(`#view-${view}`).dataset.shown) {
      S.view = view;
      for (const v of VIEWS) {
        $(`#view-${v}`).hidden = v !== view;
        $(`#view-${v}`).dataset.shown = v === view ? '1' : '';
      }
      $$('#tabbar a').forEach((a) => { if (a.dataset.tab === view) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
      window.scrollTo(0, 0);
      hidePop();
    }
    render();
    wakeLock(view === 'plant' && !!S.timer);
  }

  function render() {
    if (!S.settings) return;
    if (D && D.today !== todayKey()) invalidate();
    paintSync();
    paintTabs();
    if (S.view === 'plant') renderPlant();
    else if (S.view === 'forest') renderForest();
    else if (S.view === 'together') renderTogether();
    else if (S.view === 'stats') renderStats();
    else if (S.view === 'log') renderLog();
    else if (S.view === 'settings') renderSettings();
    paintTitle();
  }

  // the demo Dakku, full of made-up ducks: say so, and hide what it doesn't have (see app.css);
  // and for a friend, hide what's only for the person whose Dakku this is
  function markDemo() {
    document.documentElement.classList.toggle('demo', !!S.me?.demo);
    document.documentElement.classList.toggle('friend', S.me?.role === 'friend');
  }

  function paintSync() {
    const el = $('#sync');
    if (!el) return;
    const pending = S.outbox.length;
    let state = 'synced', label = S.me?.demo ? 'Demo' : 'Synced';
    if (!S.reachable) { state = 'offline'; label = pending ? `Offline · ${pending} waiting` : 'Offline'; }
    else if (S.syncing) { state = 'syncing'; label = 'Syncing…'; }
    else if (pending) { state = 'pending'; label = `${pending} to sync`; }
    el.dataset.state = state;
    $('#sync-label').textContent = label;
    el.title = S.lastSync ? `Last synced ${ago(S.lastSync)}` : 'Sync now';
    const detail = $('#sync-detail');
    if (detail) detail.textContent = S.lastSync ? `Last synced ${ago(S.lastSync)}${S.live ? ' · live' : ''}` : '';
  }

  function paintTitle() {
    const t = S.timer;
    if (t) {
      const ph = t.mode === 'pomo' ? pomoPhase(t, elapsedOf(t)) : null;
      const left = ph ? fmtClock(ph.left) : t.mode === 'timer' ? fmtClock(remainingOf(t)) : fmtClock(elapsedOf(t), Math.floor);
      document.title = `${t.runFrom == null ? '⏸ ' : ph?.phase === 'break' ? '☕ ' : ''}${left} · 鴨 Dakku${S.me?.demo ? ' demo' : ''}`;
    } else document.title = S.me?.demo ? '鴨 Dakku demo' : '鴨 Dakku';
  }

  /* ───────────── 孵 Hatch (the "plant" view) ───────────── */
  function renderPlant() {
    renderToday();
    renderPlantControls();
    paintTimer();
    renderPlantSide();
  }

  function renderToday() {
    const d = derive();
    const mins = d.byDay.get(d.today) || 0;
    const pct = clamp(mins / d.goal, 0, 1) * 100;
    const wd = weekday(d.today);
    let right;
    if (mins >= d.goal) right = '<span class="jp" style="color:var(--accent)">達成</span> Goal reached';
    else if (wd >= 5) right = 'Weekend · streak safe';
    else if (d.streak > 0) right = `${d.goal - mins} min keeps your streak`;
    else right = `${d.goal - mins} min to start a streak`;
    $('#today').innerHTML = `
      <div class="today-row">
        <div class="today-date"><span class="jp">${WD_JP[wd]}</span>${esc(fmtDate(d.today, { weekday: 'short', month: 'short', day: 'numeric' }))}</div>
        <div class="streak" title="Best: ${d.best} days${d.freezes ? `. ${FREEZE_TIP}` : ''}"><span class="ren">連</span><b>${d.streak}</b> day streak${d.freezes ? `<span class="frz" aria-label="${d.freezes} streak ${d.freezes === 1 ? 'freeze' : 'freezes'}">❄${d.freezes > 1 ? d.freezes : ''}</span>` : ''}</div>
      </div>
      <div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="${d.goal}" aria-valuenow="${mins}"><i style="width:${pct}%"></i></div>
      <div class="progress-text"><span>${mins} of ${d.goal} min today</span><span>${right}</span></div>`;
  }

  function renderPlantControls() {
    const t = S.timer;
    $('#idle-controls').hidden = !!t;
    $('#run-controls').hidden = !t;
    if (!t) {
      $$('#mode-seg button').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.mode === S.pick.mode)));
      const presets = S.settings.presets;
      $('#presets').innerHTML = S.pick.mode === 'timer'
        ? presets.map((m) => `<button type="button" data-min="${m}" aria-pressed="${m === S.pick.minutes}">${m}</button>`).join('')
        : '';
      $('#presets').hidden = S.pick.mode !== 'timer';
      $('#pomo-pick').hidden = S.pick.mode !== 'pomo';
      if (S.pick.mode === 'pomo') {
        const p = S.pick.pomo;
        $('#pomo-pick').innerHTML = [['focus', 'Focus', 'min'], ['brk', 'Break', 'min'], ['rounds', 'Rounds', '']].map(([k, label, unit]) => `
          <div class="stepper"><span class="lbl">${label}</span>
            <button type="button" data-pomo="${k}" data-step="-1" aria-label="Less ${label.toLowerCase()}"${p[k] <= POMO_LIMITS[k][0] ? ' disabled' : ''}>−</button>
            <b>${p[k]}${unit ? `<small> ${unit}</small>` : ''}</b>
            <button type="button" data-pomo="${k}" data-step="1" aria-label="More ${label.toLowerCase()}"${p[k] >= POMO_LIMITS[k][1] ? ' disabled' : ''}>+</button></div>`).join('');
      }
      const tags = S.settings.tags;
      $('#tag-chips').innerHTML = [{ name: '' }, ...tags].map((tag) => `
        <button type="button" class="chip" data-tag="${esc(tag.name)}" style="--c:${tag.name ? tagColor(tag.name) : 'var(--ink-3)'}" aria-pressed="${tag.name === S.pick.tag}">
          <span class="dot"></span>${tag.name ? esc(tag.name) : 'No tag'}</button>`).join('') +
        '<button type="button" class="chip add" data-tag-add>+ Tag</button>';
      const avail = unlocked();
      const random = S.settings.randomSpecies;
      // four ducks: the ones you hatched lately (and one you just chose), then the way to all of them
      let row = recentDucks().slice(0, 4);
      if (!random && SPECIES.includes(S.pick.species) && !row.includes(S.pick.species)) row = [S.pick.species, ...row.slice(0, 3)];
      if (random) row = ['random', ...row.slice(0, 3)];
      $('#species-row').innerHTML = row.map((sp) => {
        if (sp === 'random') return `<button type="button" class="sp" data-sp="random" aria-pressed="true" title="A surprise duck each time">${SURPRISE_SVG}<span class="n">運</span></button>`;
        const open = avail.includes(sp);
        const info = Art.KINDS[sp];
        return `<button type="button" class="sp${open ? '' : ' locked'}" data-sp="${sp}" aria-pressed="${!random && open && sp === S.pick.species}" ${open ? '' : 'disabled'}
          title="${esc(info.name)}">${open ? '' : '<span class="lock">🔒︎</span>'}
          ${Art.duckSVG(sp)}<span class="n">${esc(info.kanji)}</span></button>`;
      }).join('') + `<button type="button" class="sp all" data-sp-all title="Every duck"><span class="all-n">${SPECIES.length}</span><span class="n">All</span></button>`;
      $('#plant-btn').disabled = S.starting;
      $('#open-row').hidden = !inGroups();
      $('#open-sessions').checked = S.settings.openSessions !== false;
    } else {
      const here = isMine(t.id), guest = t.mode === 'room';
      const where = t.local ? 'on this device (offline)' : here ? 'here' : `on ${t.device}`; // where the egg is warming
      $('#run-meta').innerHTML = `
        ${t.tag ? `<span class="chip" style="--c:${tagColor(t.tag)}"><span class="dot"></span>${esc(t.tag)}</span>` : ''}
        <span class="chip">${S.settings.randomSpecies && isMine(t.id) && !guest ? '? Surprise duck' : esc(speciesName(t.species))}</span>
        <span class="chip">${guest ? `With ${esc(nameOf(t.host))}` : `Hatching ${esc(where)}`}</span>
        ${t.deep ? '<span class="chip"><span class="jp">集中</span>&nbsp;Deep focus</span>' : ''}`;
      $('#finish-btn').textContent = guest ? 'Leave' : t.mode === 'stopwatch' ? 'Done' : 'Finish';
      if (t.mode === 'pomo') $('#run-meta').insertAdjacentHTML('beforeend', `<span class="chip">🍅 ${t.pomo.rounds} × ${fmtMin(Math.round(t.pomo.focus / MIN))}</span>`);
      renderParty(t);
    }
  }

  // everyone studying in this session: their badge, their duck, and how long they've been here
  function renderParty(t) {
    const party = (t.party || []).filter((g) => g.person !== myId());
    const host = $('#party');
    host.hidden = !party.length && !(t.open && inGroups() && t.mode !== 'room');
    host.innerHTML = party.length
      ? `<span class="muted small">${t.mode === 'room' ? 'Studying with' : 'With you'}</span>${party.map((g) => `<span class="party-who">${badgeHTML(personOf(g.person))}<b>${esc(nameOf(g.person))}</b><span class="muted small">${g.host ? 'host' : `since ${esc(fmtTime(g.since))}`}</span></span>`).join('')}`
      : '<span class="muted small">Your friends can join this session.</span>';
  }

  const DIAL_R = 134;
  const polar = (frac, r = DIAL_R) => { const a = frac * 2 * Math.PI - Math.PI / 2; return [150 + r * Math.cos(a), 150 + r * Math.sin(a)]; };
  function arcPath(frac) {
    frac = clamp(frac, 0, 1);
    if (frac <= 0.0005) return '';
    if (frac >= 0.9995) return `M150 ${150 - DIAL_R}A${DIAL_R} ${DIAL_R} 0 1 1 149.98 ${150 - DIAL_R}`;
    const [x, y] = polar(frac);
    return `M150 ${150 - DIAL_R}A${DIAL_R} ${DIAL_R} 0 ${frac > 0.5 ? 1 : 0} 1 ${x.toFixed(2)} ${y.toFixed(2)}`;
  }
  function drawTicks() {
    let out = '';
    for (let i = 0; i < 36; i++) {
      const major = i % 3 === 0;
      const [x1, y1] = polar(i / 36, major ? 119 : 121), [x2, y2] = polar(i / 36, 125);
      out += `<line class="dial-tick${major ? ' major' : ''}" x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}"/>`;
    }
    $('#dial-ticks').innerHTML = out;
  }

  let lastGrowKey = '';
  function paintTimer() {
    if (!S.timer && lock) wakeLock(false); // the duck hatched: let the screen sleep again
    if (S.view !== 'plant' || !S.settings) { paintTitle(); return; }
    const t = S.timer, dial = $('#dial');
    const now = serverNow();
    let frac, clock, sub, growth;
    dial.classList.toggle('running', !!t && t.runFrom != null);
    dial.classList.toggle('paused', !!t && t.runFrom == null);
    $('#clock').classList.toggle('paused', !!t && t.runFrom == null);
    let sleeping = false; // a pomodoro's break: the egg naps
    if (!t) {
      const m = S.pick.minutes, p = S.pick.pomo;
      frac = S.pick.mode === 'timer' ? Math.min(m, DIAL_MAX) / DIAL_MAX : 0;
      clock = S.pick.mode === 'timer' ? fmtClock(m * MIN) : S.pick.mode === 'pomo' ? fmtClock(p.focus * MIN) : '00:00';
      sub = S.pick.mode === 'timer' ? 'Drag the ring to choose your time'
        : S.pick.mode === 'pomo' ? `${p.rounds} × ${fmtMin(p.focus)}${p.rounds > 1 ? `, ${fmtMin(p.brk)} breaks` : ''} · done at ${fmtTime(Date.now() + pomoPlanned(p))}`
        : 'Counts up until you say done';
      growth = 0;
      const [kx, ky] = polar(frac || 0.0001);
      $('#dial-knob').setAttribute('cx', kx.toFixed(2));
      $('#dial-knob').setAttribute('cy', ky.toFixed(2));
      $('#dial-knob').style.display = S.pick.mode === 'timer' ? '' : 'none';
      dial.setAttribute('aria-valuenow', String(m));
      dial.setAttribute('aria-valuetext', `${m} minutes`);
    } else if (t.mode === 'room' && t.hostTimer?.mode === 'pomo') {
      // you joined someone's pomodoro: you focus and take breaks together
      const h = t.hostTimer, ph = pomoPhase(h, elapsedOf(h, now));
      const yours = Math.max(0, pomoFocus(h, elapsedOf(h, now)) - pomoFocus(h, t.hostAt ?? 0));
      sleeping = ph.phase === 'break' && h.runFrom != null;
      frac = 1 - ph.left / ph.part;
      clock = fmtClock(ph.left);
      sub = t.runFrom == null || h.runFrom == null ? 'Paused' : sleeping ? `Break · back to focus at ${fmtTime(Date.now() + ph.left)}`
        : `Round ${ph.round} of ${h.pomo.rounds} · you've studied ${fmtMin(Math.floor(yours / MIN))} with ${nameOf(t.host)}`;
      growth = pomoFocus(h, elapsedOf(h, now)) / (h.pomo.focus * h.pomo.rounds);
      $('#pause-btn').textContent = t.runFrom == null ? 'Resume' : 'Pause';
    } else if (t.mode === 'room') {
      // you joined someone: your duck hatches when their session ends
      const el = elapsedOf(t, now), left = hostLeft(t, now);
      if (left != null) {
        frac = 1 - left / t.hostTimer.planned;
        clock = fmtClock(left);
        sub = t.runFrom == null ? 'Paused · your time is on hold' : `You've studied ${fmtMin(Math.floor(el / MIN))} · hatches with ${nameOf(t.host)}`;
        growth = el / Math.max(1, el + left);
      } else {
        frac = (el % HOUR) / HOUR;
        clock = fmtClock(el, Math.floor);
        sub = t.runFrom == null ? 'Paused' : `With ${nameOf(t.host)} · hatches when they finish`;
        growth = Math.min(1, el / (Math.max(5, S.settings.minutes) * MIN));
      }
      $('#pause-btn').textContent = t.runFrom == null ? 'Resume' : 'Pause';
    } else {
      const el = elapsedOf(t, now);
      if (t.mode === 'pomo') {
        const ph = pomoPhase(t, el);
        sleeping = ph.phase === 'break' && t.runFrom != null;
        frac = 1 - ph.left / ph.part;
        clock = fmtClock(ph.left);
        sub = t.runFrom == null ? 'Paused' : remainingOf(t, now) <= 0 ? 'Hatching!'
          : sleeping ? `Break · round ${ph.round + 1} starts at ${fmtTime(Date.now() + ph.left)}` : `Focus · round ${ph.round} of ${t.pomo.rounds}`;
      } else if (t.mode === 'timer') {
        frac = el / t.planned;
        clock = fmtClock(t.planned - el);
        const end = Date.now() + (t.planned - el);
        sub = t.runFrom == null ? 'Paused' : frac >= 1 ? 'Hatching!' : `Hatches at ${fmtTime(end)}`;
      } else {
        frac = (el % HOUR) / HOUR;
        clock = fmtClock(el, Math.floor);
        sub = t.runFrom == null ? 'Paused' : `Started ${fmtTime(t.startedAt)}`;
      }
      growth = growthOf(t, now);
      $('#pause-btn').textContent = t.runFrom == null ? 'Resume' : 'Pause';
    }
    growth = growth ?? 0;
    $('#dial-arc').setAttribute('d', arcPath(frac));
    $('#clock').textContent = clock;
    $('#clock-sub').textContent = sub;
    const g = Math.round(clamp(growth, 0, 1) * 400) / 400;
    const stage = !t ? 'idle' : t.runFrom == null || sleeping ? 'still' : g >= 0.8 ? 'w3' : g >= 0.5 ? 'w2' : 'w1';
    const key = `${g >= 0.8 ? 2 : g >= 0.5 ? 1 : 0}|${stage}|${sleeping}|${Art.sprites.eggs.length}`;
    if (key !== lastGrowKey) {
      lastGrowKey = key;
      // the egg wobbles more as it gets close; at 50% it cracks, at 80% a duck peeks out. On a break it naps.
      $('#grow').innerHTML = `<svg viewBox="0 0 300 300" aria-hidden="true">
        <g class="wobble ${stage}"><g transform="translate(50 -24) scale(2)">${Art.eggInner(t ? g : 0)}</g></g></svg>
        ${sleeping ? '<div class="zzz" aria-hidden="true"><i>z</i><i>z</i><i>Z</i></div>' : ''}`;
    }
    dial.classList.toggle('break', sleeping);
    // the first ten seconds: call it off, or let it begin
    const undo = undoLeft(t, now);
    $('#undo-btn').hidden = !undo;
    if (undo) $('#undo-btn').textContent = `Cancel · ${Math.ceil(undo / 1000)}`;
    $('#finish-btn').hidden = !!undo;
    $('#giveup-btn').hidden = !!undo;
    paintTitle();
  }

  function renderPlantSide() {
    const d = derive();
    const todays = d.list.filter((s) => s._day === d.today);
    const items = todays.map((s) => ({ kind: s.species, cold: s.status === 'withered' }));
    const scene = Art.pond(items, { seed: 'today' + d.today, max: 40, ...pondOpts(S.settings.pondTheme) });
    $('#today-trees').innerHTML = Art.pondSVG(scene, { cls: 'mini-pond', label: `${todays.length} ducks today` }) +
      (todays.length ? `<p class="forest-note">${plural(todays.filter((s) => s.status !== 'withered').length, 'duck')} · ${fmtMin(d.byDay.get(d.today) || 0)}</p>` : '<p class="forest-note">Hatch your first duck of the day.</p>');
    const recent = d.list.slice(-5).reverse();
    $('#recent').innerHTML = recent.length ? recent.map(sessionRow).join('') : '<p class="empty">Your sessions will show up here.</p>';
    // friends studying right now, whose sessions you can join
    const rooms = (S.together?.rooms || []).filter((r) => r.host !== myId());
    $('#live-card').hidden = !rooms.length;
    $('#live-rooms').innerHTML = rooms.map(roomRow).join('');
    const welcome = $('#welcome');
    const ui = store.get(K.ui, {});
    if (S.me?.trusted && !ui.welcomed) {
      welcome.hidden = false;
      welcome.innerHTML = `<h2><span class="jp">ようこそ</span> Welcome to Dakku</h2>
        <p>Every focus session hatches a duck. Take your pond everywhere: add your phone or computer and log from anywhere.</p>
        <button class="btn small primary" type="button" data-act="pair">Add a device</button> <button class="link" type="button" data-act="welcomed">Hide</button>`;
    } else welcome.hidden = true;
  }

  function roomRow(r) {
    const others = r.party.filter((g) => !g.host);
    const busy = S.timer && !r.mine;
    const clock = r.mode === 'pomo'
      ? `🍅 ${r.phase === 'break' ? 'On a break' : 'Focusing'} · round ${r.round} of ${r.pomo?.rounds}`
      : r.mode === 'timer'
        ? (r.running && r.endsAt ? `<span data-ends="${r.endsAt}">${fmtClock(Math.max(0, r.endsAt - serverNow()))}</span> left` : `${fmtClock(r.remaining)} left`)
        : `${fmtMin(Math.floor(r.elapsed / MIN))} in, open-ended`;
    return `<div class="room${r.mine ? ' mine' : ''}">
      ${badgeHTML(personOf(r.host), 'big')}
      <div class="what"><span><b>${esc(nameOf(r.host))}</b>${r.tag ? ` · ${esc(r.tag)}` : ''}</span>
        <span class="muted small">${clock}${r.running ? '' : ' · paused'}${others.length ? ` · with ${others.map((g) => esc(nameOf(g.person))).join(', ')}` : ''}</span></div>
      <span class="room-acts">${r.host !== myId() ? `<button class="btn small" type="button" data-cheer="${esc(r.host)}" title="Send ${esc(nameOf(r.host))} a cheer">Cheer</button>` : ''}
        ${r.mine ? '<span class="chip">You\'re in</span>' : `<button class="btn small primary" type="button" data-join="${esc(r.id)}"${busy ? ' disabled title="Finish your own session first"' : ''}>Join</button>`}</span>
    </div>`;
  }

  /* ───────────── cheers: a message for someone studying ───────────── */
  let cheerTo = null;
  function openCheer(pid) {
    cheerTo = pid;
    $('#cheer-title').textContent = `Cheer ${nameOf(pid)} on`;
    $('#cheer-picks').innerHTML = CHEERS.map((text) => `<button type="button" class="chip" data-cheer-text="${esc(text)}">${esc(text)}</button>`).join('');
    $('#cheer-text').value = '';
    $('#cheer-dialog').showModal();
  }

  async function sendCheer(text) {
    text = text.trim();
    if (!text || !cheerTo) return;
    $('#cheer-send').disabled = true;
    try {
      await api('POST', '/api/cheer', { to: cheerTo, text });
      $('#cheer-dialog').close();
      toast(`Cheer sent to ${nameOf(cheerTo)}`);
    } catch (err) {
      toast(err instanceof Offline ? "Can't reach your PC right now." : err.message);
    } finally {
      $('#cheer-send').disabled = false;
    }
  }

  // cheers for you, as your timer arrives: each pops up once, over the egg (or as a toast elsewhere)
  const cheersSeen = new Set(store.get(K.cheers, []));
  const cheeredBy = new Map(); // session → who cheered, for when its duck hatches
  function cheersIn(t) {
    let fresh = false;
    if (t.cheers?.length) cheeredBy.set(t.id, t.cheers.map((c) => c.name));
    for (const c of t.cheers || []) {
      if (cheersSeen.has(c.id)) continue;
      cheersSeen.add(c.id);
      fresh = true;
      if (serverNow() - c.at < 5 * MIN) popCheer(c); // an older one was seen on another device
    }
    if (fresh) store.set(K.cheers, [...cheersSeen].slice(-80));
  }

  function popCheer(c) {
    if (S.view !== 'plant' || document.hidden) { toast(`${c.name}: ${c.text}`, 6000); return; }
    const el = document.createElement('div');
    el.className = 'cheer-pop';
    el.innerHTML = `<b>${esc(c.name)}</b> ${esc(c.text)}`;
    $('#cheer-pops').appendChild(el);
    setTimeout(() => el.remove(), 8000);
  }

  function sessionRow(s) {
    const end = s.start + s.minutes * MIN;
    const src = { genkan: 'homepage', manual: 'by hand', import: 'imported', sync: 'synced' }[s.source] || (s.manual ? 'by hand' : '');
    const bits = [`${fmtTime(s.start)}–${fmtTime(end)}`];
    if (s.status === 'withered') bits.push('cold egg');
    if (s.rounds) bits.push(`🍅 ×${s.rounds}`);
    if (src) bits.push(src);
    if (s.note) bits.push(s.note);
    return `<button type="button" class="srow${s.status === 'withered' ? ' withered' : ''}" data-edit="${esc(s.id)}">
      ${Art.duckSVG(s.species, { cold: s.status === 'withered' })}
      <span class="what"><b>${s.tag ? `<span class="tagdot" style="background:${tagColor(s.tag)}"></span>${esc(s.tag)}` : 'Focus'}</b><span>${esc(bits.join(' · '))}</span></span>
      <span class="mins">${fmtMin(s.minutes)}</span></button>`;
  }

  // the dial: drag around the ring to pick a time
  function setupDial() {
    const dial = $('#dial');
    drawTicks();
    const pointMinutes = (x, y) => {
      const r = dial.getBoundingClientRect();
      const dx = x - (r.left + r.width / 2), dy = y - (r.top + r.height / 2);
      let frac = (Math.atan2(dy, dx) + Math.PI / 2) / (2 * Math.PI);
      if (frac < 0) frac += 1;
      let m = Math.round((frac * DIAL_MAX) / 5) * 5;
      const prev = S.pick.minutes;
      if (m === 0 || m === DIAL_MAX) m = prev > DIAL_MAX / 2 ? DIAL_MAX : 5;
      if (prev >= 150 && m <= 30) m = DIAL_MAX; // no wrapping past the top
      if (prev <= 30 && m >= 150) m = 5;
      return clamp(m, 5, DIAL_MAX);
    };
    const onRing = (x, y) => {
      const r = dial.getBoundingClientRect();
      const d = Math.hypot(x - (r.left + r.width / 2), y - (r.top + r.height / 2)) / (r.width / 300);
      return d > 70 && d < 165;
    };
    const canDrag = () => !S.timer && S.pick.mode === 'timer';
    const begin = () => { S.dragging = true; dial.classList.add('dragging'); };
    const move = (x, y) => {
      const m = pointMinutes(x, y);
      if (m !== S.pick.minutes) { S.pick.minutes = m; paintTimer(); markPresets(); }
    };
    const end = () => {
      if (!S.dragging) return;
      S.dragging = false;
      dial.classList.remove('dragging');
      savePick();
    };
    dial.addEventListener('touchstart', (e) => {
      if (!canDrag() || e.touches.length !== 1) return;
      const p = e.touches[0];
      if (!onRing(p.clientX, p.clientY)) return;
      e.preventDefault();
      begin();
      move(p.clientX, p.clientY);
    }, { passive: false });
    dial.addEventListener('touchmove', (e) => { if (S.dragging) { e.preventDefault(); move(e.touches[0].clientX, e.touches[0].clientY); } }, { passive: false });
    dial.addEventListener('touchend', end);
    dial.addEventListener('touchcancel', end);
    dial.addEventListener('mousedown', (e) => {
      if (!canDrag() || !onRing(e.clientX, e.clientY)) return;
      e.preventDefault();
      begin();
      move(e.clientX, e.clientY);
      const mm = (ev) => move(ev.clientX, ev.clientY);
      window.addEventListener('mousemove', mm);
      window.addEventListener('mouseup', () => { window.removeEventListener('mousemove', mm); end(); }, { once: true });
    });
    dial.addEventListener('keydown', (e) => {
      if (!canDrag()) return;
      const step = { ArrowUp: 5, ArrowRight: 5, ArrowDown: -5, ArrowLeft: -5, PageUp: 15, PageDown: -15 }[e.key];
      if (!step) return;
      e.preventDefault();
      S.pick.minutes = clamp(Math.round((S.pick.minutes + step) / 5) * 5, 5, DIAL_MAX);
      paintTimer();
      markPresets();
      savePickSoon();
    });
  }
  const markPresets = () => $$('#presets button').forEach((b) => b.setAttribute('aria-pressed', String(+b.dataset.min === S.pick.minutes)));
  let pickTimer = 0;
  const savePickSoon = () => { clearTimeout(pickTimer); pickTimer = setTimeout(savePick, 700); };
  function savePick() {
    const patch = {};
    for (const k of ['minutes', 'mode', 'tag', 'species']) if (S.settings[k] !== S.pick[k]) patch[k] = S.pick[k];
    if (JSON.stringify({ ...POMO, ...S.settings.pomo }) !== JSON.stringify(S.pick.pomo)) patch.pomo = { ...S.pick.pomo };
    if (Object.keys(patch).length) saveSettings(patch, { quiet: true });
  }

  /* ───────────── 池 Pond (the "forest" view) ───────────── */
  function rangeBounds(range, offset) {
    const today = todayKey();
    if (range === 'day') {
      const k = addDays(today, offset);
      return { from: k, to: k, label: offset === 0 ? 'Today' : offset === -1 ? 'Yesterday' : fmtDate(k, { weekday: 'long', month: 'short', day: 'numeric', year: k.slice(0, 4) !== today.slice(0, 4) ? 'numeric' : undefined }) };
    }
    if (range === 'week') {
      const mon = addDays(today, -weekday(today) + 7 * offset), sun = addDays(mon, 6);
      const label = offset === 0 ? 'This week' : offset === -1 ? 'Last week' : `${fmtDate(mon, { month: 'short', day: 'numeric' })} – ${fmtDate(sun, { month: 'short', day: 'numeric' })}`;
      return { from: mon, to: sun, label, sub: `${fmtDate(mon, { month: 'short', day: 'numeric' })} – ${fmtDate(sun, { month: 'short', day: 'numeric' })}` };
    }
    if (range === 'month') {
      const y = +today.slice(0, 4), m = +today.slice(5, 7) - 1 + offset;
      const from = utcKey(Date.UTC(y, m, 1)), to = utcKey(Date.UTC(y, m + 1, 0));
      return { from, to, label: fmtDate(from, { month: 'long', year: 'numeric' }) };
    }
    const y = +today.slice(0, 4) + offset;
    return { from: `${y}-01-01`, to: `${y}-12-31`, label: String(y) };
  }
  const inRange = (b) => derive().list.filter((s) => s._day >= b.from && s._day <= b.to);

  let forestScene = null, forestItems = [];
  function renderForest() {
    $$('#range-seg button').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.range === S.range)));
    const b = rangeBounds(S.range, S.rangeOffset);
    $('#range-label').innerHTML = esc(b.label) + (b.sub && S.rangeOffset > -2 ? `<div class="muted small">${esc(b.sub)}</div>` : '');
    $('#range-next').disabled = S.rangeOffset >= 0;
    const list = inRange(b);
    forestItems = list;
    const stage = $('#forest-stage');
    if (!list.length) {
      forestScene = null;
      const empty = Art.pond([], { seed: b.from, shape: innerWidth < 600 ? 'tall' : 'wide', ...pondOpts(S.settings.pondTheme) });
      stage.style.maxWidth = '420px';
      stage.innerHTML = `<div class="empty-forest">${Art.pondSVG(empty, { label: 'An empty pond' })}<p>${S.rangeOffset === 0 ? 'No ducks yet. Finish a session and one hatches here.' : 'No ducks hatched then.'}</p></div>`;
    } else {
      // on a phone the pond can be taller than it is wide, which gives the ducks more room
      const phone = innerWidth < 600;
      forestScene = Art.pond(list.map((s) => ({ kind: s.species, cold: s.status === 'withered' })), { seed: S.range + b.from, max: 500, maxAspect: phone ? 1.2 : 0.8, shape: phone ? 'tall' : 'wide', ...pondOpts(S.settings.pondTheme) });
      // a pond of a few ducks shouldn't be blown up: keep the ones at the front at most 150px across
      stage.style.maxWidth = `${Math.round(Math.min(760, Math.max(380, (1.5 * forestScene.width) / forestScene.k)))}px`;
      const hidden = list.length - forestScene.shownCount;
      stage.innerHTML = Art.pondSVG(forestScene, { cls: 'pond-svg', label: `${list.length} ducks` }) +
        (hidden > 0 ? `<p class="forest-note">Showing your latest ${forestScene.shownCount.toLocaleString()} of ${list.length.toLocaleString()} ducks</p>` : '<p class="forest-note">Tap a duck to see its session</p>');
    }
    const grown = list.filter((s) => s.status !== 'withered');
    const minutes = grown.reduce((n, s) => n + s.minutes, 0);
    const byDay = new Map();
    for (const s of grown) byDay.set(s._day, (byDay.get(s._day) || 0) + s.minutes);
    const goalDays = [...byDay.values()].filter((m) => m >= S.settings.goal).length;
    let bestDay = 0;
    for (const m of byDay.values()) bestDay = Math.max(bestDay, m);
    const tiles = [
      [fmtHM(minutes), 'focused'],
      [grown.length.toLocaleString(), grown.length === 1 ? 'duck hatched' : 'ducks hatched'],
      [S.range === 'day' ? (minutes >= S.settings.goal ? '達成' : `${Math.max(0, S.settings.goal - minutes)}<small>min</small>`) : goalDays.toLocaleString(), S.range === 'day' ? (minutes >= S.settings.goal ? 'goal reached' : 'to your goal') : goalDays === 1 ? 'day at goal' : 'days at goal'],
      [S.range === 'day' ? (list.length - grown.length).toLocaleString() : fmtHM(bestDay), S.range === 'day' ? (list.length - grown.length === 1 ? 'cold egg' : 'cold eggs') : 'best day'],
    ];
    $('#forest-tiles').innerHTML = tiles.map(([v, k]) => `<div class="tile"><div class="v">${v}</div><div class="k">${k}</div></div>`).join('');
    const byTag = new Map();
    for (const s of grown) byTag.set(s.tag || 'Untagged', (byTag.get(s.tag || 'Untagged') || 0) + s.minutes);
    $('#forest-tags-card').hidden = !byTag.size;
    $('#forest-tags').innerHTML = hbars(byTag, minutes);
  }
  const fmtHM = (m) => (m < 60 ? `${m}<small>min</small>` : `${Math.floor(m / 60)}<small>h</small>${m % 60 ? ` ${m % 60}<small>m</small>` : ''}`);

  function hbars(map, total, limit = 7) {
    const rows = [...map.entries()].sort((a, b) => b[1] - a[1]);
    const shown = rows.slice(0, limit);
    const rest = rows.slice(limit).reduce((n, [, m]) => n + m, 0);
    if (rest) shown.push(['Other', rest]);
    const max = shown.length ? shown[0][1] : 1;
    return `<div class="hbars">${shown.map(([name, m]) => `
      <div class="hbar" style="--c:${name === 'Other' || name === 'Untagged' ? 'var(--ink-3)' : tagColor(name)}">
        <span class="name">${esc(name)}</span><span class="val">${fmtMin(m)} · ${Math.round((m / Math.max(1, total)) * 100)}%</span>
        <span class="track"><i style="width:${(m / max) * 100}%"></i></span></div>`).join('')}</div>`;
  }

  function forestHit(ev) {
    if (!forestScene) return;
    const svg = $('#forest-stage svg');
    if (!svg || !svg.contains(ev.target)) { hidePop(); return; }
    const pt = svg.createSVGPoint();
    pt.x = ev.clientX;
    pt.y = ev.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse());
    let best = null, bestD = Infinity;
    for (const d of forestScene.drawn) {
      if (d.type !== 'duck') continue;
      const bx = d.x + 50 * d.k, by = d.y + 112 * d.k;
      const dx = (p.x - bx) / (d.k * 40), dy = (p.y - (by - 45 * d.k)) / (d.k * 60);
      const dist = dx * dx + dy * dy;
      if (dist < bestD) { bestD = dist; best = d; }
    }
    if (!best || bestD > 1.4) { hidePop(); return; }
    const s = forestItems[best.idx];
    if (!s) return;
    const pop = $('#tree-pop');
    pop.innerHTML = `<b>${s.status === 'withered' ? 'A cold egg' : esc(speciesName(s.species))}</b><br>${fmtMin(s.minutes)}${s.tag ? ` · ${esc(s.tag)}` : ''}<br>${esc(fmtDate(s._day, { month: 'short', day: 'numeric' }))}, ${esc(fmtTime(s.start))}`;
    pop.hidden = false;
    pop.style.left = `${clamp(ev.clientX, 130, innerWidth - 130)}px`;
    pop.style.top = `${ev.clientY}px`;
  }
  const hidePop = () => { const p = $('#tree-pop'); if (p) p.hidden = true; };

  /* ───────────── 共 Together ───────────── */
  async function loadGroup(force = false) {
    const id = S.groupId;
    if (!id || (S.groupData[id] && !force)) return S.groupData[id];
    try { S.groupData[id] = await api('GET', `/api/groups/${id}`); } catch { /* offline: show what we had */ }
    return S.groupData[id];
  }

  let groupScene = null, groupItems = [];
  async function renderTogether() {
    const tg = S.together, groups = tg?.groups || [];
    const owner = S.me?.role === 'owner';
    $('#together-main').hidden = !groups.length;
    $('#together-empty').hidden = !!groups.length;
    $('#group-chips').innerHTML = groups.length > 1 ? groups.map((g) => `<button type="button" class="chip" data-group="${esc(g.id)}" aria-pressed="${g.id === S.groupId}">${esc(g.name)}</button>`).join('') : '';
    if (!groups.length) {
      $('#together-empty').innerHTML = `<div class="card empty-together">
        <span class="seal big" aria-hidden="true">共</span>
        <h2>Study with friends</h2>
        ${owner ? `<p>Make a group and invite someone. When you start a session they can join you halfway, with their own duck, and you each get your own time. Your ducks from those sessions gather in a pond of your own together.</p>
          <button class="btn primary" type="button" data-act="new-group">Make a group</button>`
        : '<p>You\'re not in a group right now. Ask whoever invited you for a new link.</p>'}</div>`;
      return;
    }
    if (!groups.some((g) => g.id === S.groupId)) S.groupId = groups[0].id;
    const rooms = tg.rooms || [];
    $('#rooms').innerHTML = rooms.length ? rooms.map(roomRow).join('')
      : `<p class="empty">Nobody's studying right now.${S.timer ? '' : ' Start a session on the <a href="#hatch">Hatch</a> tab and your friends can join you.'}</p>`;
    const cached = S.groupData[S.groupId];
    if (cached) renderGroup(cached); // what we had, until the fresh one arrives
    const data = await loadGroup(true);
    if (!data || data === cached || S.view !== 'together') return;
    renderGroup(data);
  }

  function inGroupRange(s, range) {
    const day = dayKey(s.start), today = todayKey();
    if (range === 'week') return day >= addDays(today, -weekday(today));
    if (range === 'month') return day.slice(0, 7) === today.slice(0, 7);
    return true;
  }

  function renderGroup(data) {
    const { group, people, board, stats } = data;
    const who = peopleMap(people);
    const owner = S.me?.role === 'owner';
    $$('#group-range button').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.grange === S.groupRange)));
    $$('#board-range button').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.brange === S.boardRange)));
    $('#group-pond-title').innerHTML = `<span class="jp">池</span> ${esc(group.name)}`;
    // the pond: every duck from the sessions you did together, each with its owner's badge
    const list = data.pond.filter((s) => inGroupRange(s, S.groupRange)).sort((a, b) => a.start - b.start);
    groupItems = list;
    const phone = innerWidth < 600;
    groupScene = Art.pond(list.map((s) => ({ kind: s.species, cold: s.status === 'withered', person: s.person })),
      { seed: group.id + S.groupRange, max: 400, maxAspect: phone ? 1.2 : 0.8, shape: phone ? 'tall' : 'wide', ...pondOpts(group.theme || S.settings.pondTheme) });
    const stage = $('#group-stage');
    stage.style.maxWidth = `${Math.round(Math.min(760, Math.max(380, (1.5 * groupScene.width) / groupScene.k)))}px`;
    stage.innerHTML = Art.pondSVG(groupScene, { cls: 'pond-svg', label: `${list.length} ducks hatched together`, people: who }) +
      `<p class="forest-note">${list.length ? 'Tap a duck to see whose it is' : 'Ducks from the sessions you do together gather here.'}</p>`;
    const counts = new Map();
    for (const s of list) if (s.status !== 'withered') counts.set(s.person, (counts.get(s.person) || 0) + 1);
    $('#group-legend').innerHTML = people.map((p) => `<span class="legend-who">${badgeHTML(p)}${esc(p.id === myId() ? 'You' : p.name)}<span class="muted">${plural(counts.get(p.id) || 0, 'duck')}</span></span>`).join('');
    const together = list.filter((s) => s.status !== 'withered');
    const rooms = new Set(list.map((s) => s.room || s.id));
    $('#group-tiles').innerHTML = [
      [fmtHM(together.reduce((n, s) => n + s.minutes, 0)), 'studied together'],
      [rooms.size.toLocaleString(), rooms.size === 1 ? 'session together' : 'sessions together'],
      [together.length ? fmtHM(Math.max(...together.map((s) => s.minutes))) : '–', 'longest'],
      [fmtHM(stats.minutes), 'together, ever'],
    ].map(([v, k]) => `<div class="tile"><div class="v">${v}</div><div class="k">${k}</div></div>`).join('');
    // the leaderboard
    const key = S.boardRange;
    const ranked = [...board].sort((a, b) => b[key] - a[key] || b.total - a.total);
    const top = Math.max(1, ...ranked.map((b) => b[key]));
    $('#board').innerHTML = `<div class="board">${ranked.map((b, i) => {
      const p = who[b.person] || personOf(b.person);
      return `<div class="board-row${b.person === myId() ? ' me' : ''}">
        <span class="place">${i + 1}</span>${badgeHTML(p)}
        <span class="nm">${esc(b.person === myId() ? 'You' : p.name)}${b.studying ? '<span class="now" title="Studying now"></span>' : ''}</span>
        <span class="val">${fmtHM(b[key])}</span>
        <span class="track"><i style="width:${(b[key] / top) * 100}%;background:${esc(p.color)}"></i></span>
        <span class="sub muted small">${plural(b.ducks, 'duck')} · ${b.streak}-day streak · ${fmtHM(b.together)} together</span>
      </div>`;
    }).join('')}</div>`;
    // what everyone studies
    $('#board-tags').innerHTML = ranked.map((b) => {
      const p = who[b.person] || personOf(b.person), total = b.tags.reduce((n, t) => n + t.minutes, 0);
      if (!total) return `<div class="tags-row">${badgeHTML(p)}<span class="nm">${esc(b.person === myId() ? 'You' : p.name)}</span><span class="muted small">Nothing yet</span></div>`;
      const fallback = ['#2B6CC4', '#12A37A', '#E9A100', '#D9568F', '#6C55C8', '#D9482B'];
      return `<div class="tags-row">${badgeHTML(p)}<span class="nm">${esc(b.person === myId() ? 'You' : p.name)}</span>
        <span class="stack">${b.tags.map((t, i) => `<i style="width:${(t.minutes / total) * 100}%;background:${esc(t.color || fallback[i % fallback.length])}" title="${esc(t.name)}: ${fmtMin(t.minutes)}"></i>`).join('')}</span>
        <span class="tag-names muted small">${b.tags.slice(0, 3).map((t) => `${esc(t.name)} ${Math.round((t.minutes / total) * 100)}%`).join(' · ')}</span></div>`;
    }).join('');
    // the people in it
    $('#group-tools').innerHTML = owner ? '<button class="link" type="button" data-act="invite">Invite someone</button>' : '';
    $('#group-people').innerHTML = people.map((p) => {
      const b = board.find((x) => x.person === p.id);
      const me = p.id === myId();
      return `<div class="person-row">${badgeHTML(p)}<span class="nm">${esc(me ? `${p.name} (you)` : p.name)}${b?.studying ? '<span class="now" title="Studying now"></span>' : ''}</span>
        <span class="muted small">${b ? `${fmtHM(b.week)} this week` : ''}</span>
        ${me && !owner ? `<button class="link" type="button" data-leave="${esc(group.id)}">Leave group</button>` : ''}
        ${owner && !me ? `<button class="link" type="button" data-unmember="${esc(p.id)}">Remove</button>` : ''}</div>`;
    }).join('');
  }

  function groupHit(ev) {
    if (!groupScene) return;
    const svg = $('#group-stage svg');
    if (!svg || !svg.contains(ev.target)) { hidePop(); return; }
    const pt = svg.createSVGPoint();
    pt.x = ev.clientX;
    pt.y = ev.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse());
    let best = null, bestD = Infinity;
    for (const d of groupScene.drawn) {
      const dx = (p.x - (d.x + 50 * d.k)) / (d.k * 40), dy = (p.y - (d.y + 67 * d.k)) / (d.k * 60);
      if (dx * dx + dy * dy < bestD) { bestD = dx * dx + dy * dy; best = d; }
    }
    if (!best || bestD > 1.4) { hidePop(); return; }
    const s = groupItems[best.idx];
    if (!s) return;
    const pop = $('#tree-pop');
    pop.innerHTML = `<b>${esc(nameOf(s.person))}</b> · ${s.status === 'withered' ? 'a cold egg' : esc(speciesName(s.species))}<br>${fmtMin(s.minutes)}${s.tag ? ` · ${esc(s.tag)}` : ''}<br>${esc(fmtDate(dayKey(s.start), { month: 'short', day: 'numeric' }))}, ${esc(fmtTime(s.start))}`;
    pop.hidden = false;
    pop.style.left = `${clamp(ev.clientX, 130, innerWidth - 130)}px`;
    pop.style.top = `${ev.clientY}px`;
  }

  // joining someone's session as it runs, with a duck of your own
  function openJoin(id) {
    const room = (S.together?.rooms || []).find((r) => r.id === id);
    if (!room) { toast('That session has already ended.'); refreshTogether(0); return; }
    if (S.timer) { toast('Finish your own session first.'); return; }
    S.joinPick = { species: S.settings.randomSpecies ? 'random' : S.pick.species, tag: S.pick.tag, room: id };
    $('#join-room-title').textContent = `Join ${nameOf(room.host)}`;
    const left = room.mode === 'timer' ? `${fmtClock(room.running && room.endsAt ? Math.max(0, room.endsAt - serverNow()) : room.remaining)} left` : 'open-ended';
    $('#join-room-sub').textContent = `${room.tag ? `${room.tag} · ` : ''}${left} · ${plural(room.party.length, 'person', 'people')} studying`;
    paintJoinPick();
    $('#join-dialog').showModal();
  }
  function paintJoinPick() {
    const j = S.joinPick;
    $('#join-species').innerHTML = SPECIES.map((sp) => `<button type="button" class="sp" data-jsp="${sp}" aria-pressed="${j.species === sp}" title="${esc(Art.KINDS[sp].name)}">${Art.duckSVG(sp)}<span class="n">${esc(Art.KINDS[sp].kanji)}</span></button>`).join('') +
      `<button type="button" class="sp" data-jsp="random" aria-pressed="${j.species === 'random'}" title="A surprise duck"><svg viewBox="0 0 100 120"><text x="50" y="82" text-anchor="middle" font-size="58" fill="currentColor" opacity=".55" font-family="serif">?</text></svg><span class="n">運</span></button>`;
    $('#join-tags').innerHTML = [{ name: '' }, ...S.settings.tags].map((tag) => `<button type="button" class="chip" data-jtag="${esc(tag.name)}" style="--c:${tag.name ? tagColor(tag.name) : 'var(--ink-3)'}" aria-pressed="${tag.name === j.tag}"><span class="dot"></span>${tag.name ? esc(tag.name) : 'No tag'}</button>`).join('');
  }
  async function joinRoom() {
    const j = S.joinPick;
    if (!j) return;
    $('#join-room-go').disabled = true;
    try {
      const species = j.species === 'random' ? SPECIES[Math.floor(Math.random() * SPECIES.length)] : j.species;
      const res = await api('POST', '/api/timer', { action: 'join', room: j.room, species, tag: j.tag });
      markMine(res.timer.id);
      $('#join-dialog').close();
      applyTimer(res.timer, res.timer.now);
      unlockAudio();
      location.hash = '#hatch';
      refreshTogether(0);
    } catch (err) {
      toast(err instanceof Offline ? "Your friend's PC can't be reached right now." : err.message);
      if (err.status === 404) { $('#join-dialog').close(); refreshTogether(0); }
    } finally {
      $('#join-room-go').disabled = false;
    }
  }

  // invites: a link (and QR code) that brings someone into a group, or onto a new device of theirs
  async function openInvite(body, title, sub) {
    try {
      const res = await api('POST', '/api/invites', body);
      if (!res.url) {
        await confirmBox('Open the friends\' door first', 'So friends can join without Tailscale, run this once on your PC:\n\nscripts/enable-friends.sh (in Dakku\'s folder)\n\nThen make the invite again.', 'OK', true);
        return;
      }
      $('#invite-title').textContent = title;
      $('#invite-sub').textContent = sub;
      $('#invite-url').textContent = res.url;
      $('#invite-qr').innerHTML = QR.svg(res.url);
      $('#invite-expiry').textContent = `${res.uses === 1 ? 'Works once' : `Works for ${res.uses} people`} · until ${fmtDate(dayKey(res.expires), { month: 'short', day: 'numeric' })}`;
      $('#invite-share').hidden = !navigator.share;
      $('#invite-copy').onclick = async () => { try { await navigator.clipboard.writeText(res.url); toast('Link copied.'); } catch { toast('Copy it from the box above.'); } };
      $('#invite-share').onclick = async () => { try { await navigator.share({ title: '鴨 Dakku', text: 'Study with me on Dakku', url: res.url }); } catch (err) { if (err.name !== 'AbortError') toast(err.message); } };
      $('#invite-dialog').showModal();
    } catch (err) { toast(err instanceof Offline ? "Your PC can't be reached." : err.message); }
  }
  async function newGroup() {
    const unnamed = !S.settings.name;
    if (unnamed) {  // friends see your name on your ducks and sessions
      const mine = await askText('First, your name', 'Friends see it on your ducks and your sessions.', 'Your name', '', 'Next');
      if (!mine) return;
      saveSettings({ name: mine.slice(0, 40) }, { quiet: true });
    }
    const name = await askText('Make a group', 'A group shares a pond, a leaderboard, and each other\'s live sessions. You can rename it later.', 'Group name', 'Study club', 'Make it');
    if (!name) return;
    try {
      if (unnamed) await flush();
      const group = await api('POST', '/api/groups', { name: name.trim() });
      S.groupId = group.id;
      await refreshTogetherNow();
      openInvite({ group: group.id }, `Invite someone to ${group.name}`, 'They open this on their phone or computer, pick a name, and they\'re in: no Tailscale or app needed.');
    } catch (err) { toast(err.message); }
  }
  async function refreshTogetherNow() {
    try { S.together = await api('GET', '/api/together'); saveCache(); } catch { /* offline */ }
    S.admin = null;
    render();
  }

  /* ───────────── 記録 Stats ───────────── */
  function renderStats() {
    const d = derive();
    renderProfile(d);
    renderWeek(d);
    $$('#bars-seg button').forEach((b) => b.setAttribute('aria-checked', String(+b.dataset.n === S.barsN)));
    renderBars(d);
    renderHeat(d);
    renderTagChart(d);
    renderHours(d);
    renderCollection(d);
    renderYear(d);
    renderBadges(d);
    renderAnki();
  }

  // this year so far: its numbers, and how much went to each month
  function yearData(d) {
    const year = d.today.slice(0, 4), months = Array(12).fill(0), days = new Set(), kinds = new Map(), tags = new Map();
    let minutes = 0, ducks = 0;
    const list = d.list.filter((s) => s._day.startsWith(year));
    for (const s of list) {
      if (s.status === 'withered') continue;
      minutes += s.minutes;
      ducks++;
      days.add(s._day);
      months[+s._day.slice(5, 7) - 1] += s.minutes;
      const k = Art.kindOf(s.species);
      kinds.set(k, (kinds.get(k) || 0) + 1);
      tags.set(s.tag || 'Untagged', (tags.get(s.tag || 'Untagged') || 0) + s.minutes);
    }
    const top = (m) => [...m.entries()].sort((a, b) => b[1] - a[1])[0] || null;
    const best = months.reduce((b, v, i) => (v > months[b] ? i : b), 0);
    const monthName = (i, month = 'long') => fmtDate(`${year}-${String(i + 1).padStart(2, '0')}-15`, { month });
    return { year, months, minutes, ducks, days: days.size, duck: top(kinds), tag: top(tags), best: months[best] ? best : -1, list, monthName };
  }
  function renderYear(d) {
    const y = yearData(d), host = $('#year');
    $('#year-title').textContent = `Your ${y.year}`;
    $('#year-share').hidden = !y.ducks;
    if (!y.ducks) { host.innerHTML = '<p class="empty">Your first duck this year starts it.</p>'; return; }
    const W = Math.max(280, host.clientWidth || 320), H = 116, padT = 10, padB = 20, band = W / 12, bw = Math.min(26, Math.max(4, band - 6));
    const top = Math.max(60, ...y.months), yy = (v) => padT + (H - padT - padB) * (1 - v / top), now = +d.today.slice(5, 7) - 1;
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Focus in each month of ${y.year}">`;
    y.months.forEach((v, i) => {
      const x = band * i + (band - bw) / 2, h = Math.max(0, yy(0) - yy(v)), r = Math.min(4, bw / 2, h);
      svg += `<rect class="hit" x="${band * i}" y="${padT}" width="${band}" height="${H - padT - padB}" data-tip="${i}" tabindex="-1"/>`;
      if (h > 0) svg += `<path class="bar${i === now ? ' today' : ''}" d="M${x} ${yy(0)}V${yy(v) + r}Q${x} ${yy(v)} ${x + r} ${yy(v)}H${x + bw - r}Q${x + bw} ${yy(v)} ${x + bw} ${yy(v) + r}V${yy(0)}Z"/>`;
      svg += `<text class="tick" x="${band * i + band / 2}" y="${H - 5}" text-anchor="middle">${esc(y.monthName(i, 'narrow'))}</text>`;
    });
    svg += `<line class="axis" x1="0" x2="${W}" y1="${yy(0)}" y2="${yy(0)}"/></svg>`;
    const duck = y.duck && Art.KINDS[y.duck[0]];
    host.innerHTML = `<div class="year-stats">
        <div class="stat"><div class="v">${fmtHours(y.minutes)}<small>h</small></div><div class="k">focused</div></div>
        <div class="stat"><div class="v">${y.ducks.toLocaleString()}</div><div class="k">${y.ducks === 1 ? 'duck' : 'ducks'}</div></div>
        <div class="stat"><div class="v">${y.days}</div><div class="k">${y.days === 1 ? 'day' : 'days'} studied</div></div>
        <div class="stat"><div class="v">${y.best >= 0 ? esc(y.monthName(y.best, 'short')) : '–'}</div><div class="k">best month</div></div>
      </div>
      <div class="chart">${svg}${table(['Month', 'Minutes'], y.months.map((v, i) => [y.monthName(i), String(v)]).filter((r, i) => i <= now))}</div>
      <p class="muted small year-note">${duck ? `Most hatched: ${esc(duck.kanji)} ${esc(duck.name)} ×${y.duck[1]}` : ''}${y.tag ? ` · Top tag: ${esc(y.tag[0])}` : ''}</p>`;
    wireTips(host, (el) => `<b>${fmtMin(y.months[+el.dataset.tip])}</b> · ${esc(y.monthName(+el.dataset.tip))} ${y.year}`);
  }

  function renderProfile(d) {
    const { rank, next } = rankFor(d.total);
    const name = S.settings.name ? `${esc(S.settings.name)}'s pond` : 'Your pond';
    const first = d.list.find((s) => s.status !== 'withered');
    const since = first ? `Hatching since ${fmtDate(first._day, { month: 'short', year: 'numeric' })}` : 'Hatch your first duck';
    const toNext = next ? next[0] * 60 - d.total : 0;
    $('#profile').innerHTML = `
      <div><div class="who">${name}</div><div class="rank">${rank[1]} ${rank[2]}<small>${rank[3]}</small></div></div>
      <div class="hanko${rank[1].length > 1 ? ' two' : ''}" aria-hidden="true">${rank[1]}</div>
      <div class="big">
        <div class="stat"><div class="v">${fmtHours(d.total)}<small>h</small></div><div class="k">focused</div></div>
        <div class="stat"><div class="v">${d.trees.toLocaleString()}</div><div class="k">${d.trees === 1 ? 'duck' : 'ducks'}</div></div>
        <div class="stat" title="${FREEZE_TIP}"><div class="v">${d.streak}</div><div class="k">day streak${d.freezes ? ` · ❄ ${d.freezes} ${d.freezes === 1 ? 'freeze' : 'freezes'}` : ''}</div></div>
        <div class="stat"><div class="v">${d.best}</div><div class="k">best streak</div></div>
      </div>
      <div class="next">${next ? `<div class="progress"><i style="width:${((d.total - rank[0] * 60) / ((next[0] - rank[0]) * 60)) * 100}%"></i></div>
        <span>${since} · ${fmtMin(toNext)} more to ${next[1]} ${next[2]}</span>` : `<span>${since} · the highest rank. 見事.</span>`}</div>`;
  }

  function renderWeek(d) {
    const mon = addDays(d.today, -weekday(d.today));
    let total = 0, html = '';
    for (let i = 0; i < 7; i++) {
      const k = addDays(mon, i), m = d.byDay.get(k) || 0;
      total += m;
      const frac = clamp(m / d.goal, 0, 1), met = m >= d.goal, future = k > d.today;
      const C = 2 * Math.PI * 19;
      html += `<div class="wday${met ? ' met' : ''}${k === d.today ? ' today' : ''}${future ? ' future' : ''}${i >= 5 ? ' weekend' : ''}" title="${esc(fmtDate(k, { weekday: 'long', month: 'short', day: 'numeric' }))}: ${m} min">
        <svg viewBox="0 0 46 46" role="img" aria-label="${WD_KANJI[i]}: ${m} of ${d.goal} minutes">
          <circle class="ring-track" cx="23" cy="23" r="19" stroke-width="4"/>
          ${met ? '<circle class="disc" cx="23" cy="23" r="15"/>' : ''}
          <circle class="ring" cx="23" cy="23" r="19" stroke-width="4" stroke-dasharray="${C.toFixed(2)}" stroke-dashoffset="${(C * (1 - frac)).toFixed(2)}" transform="rotate(-90 23 23)"/>
          <text class="kan" x="23" y="28" text-anchor="middle">${WD_KANJI[i]}</text></svg>
        <span class="m">${future ? '·' : m ? fmtMin(m) : '–'}</span></div>`;
    }
    $('#week').innerHTML = `<div class="week">${html}</div>`;
    $('#week-total').textContent = `${fmtMin(total)} this week`;
  }

  // a tooltip that follows the pointer inside a chart
  function wireTips(root, describe) {
    root._describe = describe;
    if (root._wired) return;
    root._wired = true;
    const tipEl = () => {
      let tip = root.querySelector(':scope > .chart-tip');
      if (!tip) {
        tip = document.createElement('div');
        tip.className = 'chart-tip';
        tip.hidden = true;
        root.appendChild(tip);
      }
      return tip;
    };
    const hide = () => { tipEl().hidden = true; };
    const show = (el, ev) => {
      const tip = tipEl();
      const text = root._describe(el);
      if (!text) return;
      tip.innerHTML = text;
      tip.hidden = false;
      const r = root.getBoundingClientRect(), er = el.getBoundingClientRect();
      const x = ev && ev.clientX ? ev.clientX : er.left + er.width / 2;
      tip.style.left = `${clamp(x - r.left, 60, r.width - 60)}px`;
      tip.style.top = `${er.top - r.top}px`;
    };
    root.addEventListener('pointermove', (ev) => { const el = ev.target.closest('[data-tip]'); if (el) show(el, ev); else hide(); });
    root.addEventListener('pointerdown', (ev) => { const el = ev.target.closest('[data-tip]'); if (el) show(el, ev); });
    root.addEventListener('pointerleave', hide);
    root.addEventListener('focusin', (ev) => { const el = ev.target.closest('[data-tip]'); if (el) show(el); });
    root.addEventListener('focusout', hide);
  }

  const niceStep = (max) => { for (const s of [5, 10, 15, 30, 60, 90, 120, 180, 240, 300, 600]) if (max / s <= 4) return s; return 600; };
  function table(head, rows) {
    return `<div class="chart-table-wrap"><table class="chart-table"><thead><tr>${head.map((h) => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }

  function renderBars(d) {
    const host = $('#bars');
    const n = S.barsN, W = Math.max(280, host.clientWidth || 320), H = 168, padL = 36, padB = 22, padT = 14;
    const days = [];
    for (let i = n - 1; i >= 0; i--) days.push(addDays(d.today, -i));
    const vals = days.map((k) => d.byDay.get(k) || 0);
    const top = Math.max(d.goal * 1.3, ...vals, 30);
    const step = niceStep(top);
    const maxY = Math.ceil(top / step) * step;
    const y = (v) => padT + (H - padT - padB) * (1 - v / maxY);
    const band = (W - padL) / n, bw = Math.min(24, Math.max(2, band - 2));
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Minutes of focus for each of the last ${n} days">`;
    for (let v = 0; v <= maxY; v += step) {
      const tick = v === 0 ? '0' : v < 60 ? `${v}m` : v % 60 ? `${Math.floor(v / 60)}h${v % 60}` : `${v / 60}h`;
      svg += `<line class="grid" x1="${padL}" x2="${W}" y1="${y(v)}" y2="${y(v)}"/><text class="tick" x="${padL - 6}" y="${y(v) + 4}" text-anchor="end">${tick}</text>`;
    }
    days.forEach((k, i) => {
      const v = vals[i], x = padL + band * i + (band - bw) / 2, h = Math.max(0, y(0) - y(v));
      const r = Math.min(4, bw / 2, h);
      const path = h > 0 ? `M${x} ${y(0)}V${y(v) + r}Q${x} ${y(v)} ${x + r} ${y(v)}H${x + bw - r}Q${x + bw} ${y(v)} ${x + bw} ${y(v) + r}V${y(0)}Z` : '';
      svg += `<rect class="hit" x="${padL + band * i}" y="${padT}" width="${band}" height="${H - padT - padB}" data-tip="${i}" tabindex="-1"/>`;
      if (path) svg += `<path class="bar${k === d.today ? ' today' : ''}${v < d.goal && v > 0 ? '' : ''}" d="${path}"/>`;
      const label = n <= 14 ? WD_KANJI[weekday(k)] : (weekday(k) === 0 && (n <= 30 || +k.slice(8) <= 7)) ? fmtDate(k, { month: 'numeric', day: 'numeric' }) : '';
      if (label) svg += `<text class="tick" x="${padL + band * i + band / 2}" y="${H - 6}" text-anchor="middle">${label}</text>`;
    });
    svg += `<line class="axis" x1="${padL}" x2="${W}" y1="${y(0)}" y2="${y(0)}"/>`;
    svg += `<line class="goal" x1="${padL}" x2="${W}" y1="${y(d.goal)}" y2="${y(d.goal)}"/><text class="goal-label" x="${W}" y="${y(d.goal) - 5}" text-anchor="end">goal ${d.goal}</text>`;
    svg += '</svg>';
    host.innerHTML = svg + table(['Day', 'Minutes'], days.map((k, i) => [fmtDate(k, { weekday: 'short', month: 'short', day: 'numeric' }), String(vals[i])]).reverse());
    wireTips(host, (el) => {
      const i = +el.dataset.tip, k = days[i];
      return `<b>${fmtMin(vals[i])}</b> · ${esc(fmtDate(k, { weekday: 'short', month: 'short', day: 'numeric' }))}${vals[i] >= d.goal ? ' · goal ✓' : ''}`;
    });
  }

  function renderHeat(d) {
    const host = $('#heat');
    const width = host.clientWidth || 320;
    const cell = 12, gap = 3, stepPx = cell + gap, padL = 18, padT = 16;
    const weeks = clamp(Math.floor((width - padL) / stepPx), 12, 53);
    const thisMon = addDays(d.today, -weekday(d.today));
    const start = addDays(thisMon, -7 * (weeks - 1));
    const level = (m) => (m <= 0 ? 0 : m < d.goal / 2 ? 1 : m < d.goal ? 2 : m < d.goal * 2 ? 3 : 4);
    const W = padL + weeks * stepPx, H = padT + 7 * stepPx;
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Focus each day for the last ${weeks} weeks">`;
    [0, 2, 4].forEach((r) => { svg += `<text class="tick" x="0" y="${padT + r * stepPx + 10}">${WD_KANJI[r]}</text>`; });
    let lastMonth = '', frosted = false;
    const rows = [];
    for (let w = 0; w < weeks; w++) {
      const mon = addDays(start, w * 7);
      const month = mon.slice(5, 7);
      if (month !== lastMonth && +mon.slice(8) <= 7) {
        svg += `<text class="month" x="${padL + w * stepPx}" y="10">${fmtDate(mon, { month: 'short' })}</text>`;
        lastMonth = month;
      }
      for (let r = 0; r < 7; r++) {
        const k = addDays(mon, r);
        if (k > d.today) continue;
        const m = d.byDay.get(k) || 0;
        if (m) rows.push([fmtDate(k, { weekday: 'short', month: 'short', day: 'numeric' }), String(m)]);
        svg += `<rect class="cell" x="${padL + w * stepPx}" y="${padT + r * stepPx}" width="${cell}" height="${cell}" fill="var(--g${level(m)})" data-tip="${k}"/>`;
        if (d.frozen.has(k)) { frosted = true; svg += `<text class="frost" x="${padL + w * stepPx + cell / 2}" y="${padT + r * stepPx + cell / 2}" text-anchor="middle" dominant-baseline="central">❄</text>`; }
      }
    }
    svg += '</svg>';
    host.innerHTML = svg + `<div class="heat-legend">Less ${[0, 1, 2, 3, 4].map((l) => `<i style="background:var(--g${l})"></i>`).join('')} More<span class="muted" style="margin-left:8px">dark = goal met${frosted ? ' · ❄ = a streak freeze' : ''}</span></div>` +
      table(['Day', 'Minutes'], rows.reverse());
    wireTips(host, (el) => {
      const k = el.dataset.tip, m = d.byDay.get(k) || 0;
      return `<b>${fmtMin(m)}</b> · ${esc(fmtDate(k, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }))}${d.frozen.has(k) ? '<br>❄ A streak freeze kept your streak' : ''}`;
    });
  }

  function renderTagChart(d) {
    $('#tags').innerHTML = d.byTag.size ? hbars(d.byTag, d.total) + table(['Tag', 'Minutes'], [...d.byTag.entries()].sort((a, b) => b[1] - a[1]).map(([t, m]) => [t, String(m)])) : '<p class="empty">Tag your sessions to see where your time goes.</p>';
  }

  function renderHours(d) {
    const host = $('#hours');
    const mins = new Array(24).fill(0);
    for (const s of d.list) {
      if (s.status === 'withered') continue;
      let t = s.start, left = s.minutes;
      while (left > 0) {
        const h = hourOf(t), into = new Date(t).getUTCMinutes();
        const take = Math.min(left, 60 - into);
        mins[h] += take;
        left -= take;
        t += take * MIN;
      }
    }
    const W = Math.max(260, host.clientWidth || 300), H = 130, padB = 20, padT = 16;
    const max = Math.max(...mins, 1);
    const band = W / 24, bw = Math.min(14, band - 2);
    const peak = mins.indexOf(Math.max(...mins));
    const hourLabel = (h) => (h === 0 ? '12a' : h < 12 ? `${h}a` : h === 12 ? '12p' : `${h - 12}p`);
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="When you focus during the day">`;
    mins.forEach((m, h) => {
      const bh = (m / max) * (H - padT - padB), x = h * band + (band - bw) / 2, y0 = H - padB;
      const r = Math.min(3, bw / 2, bh);
      svg += `<rect class="hit" x="${h * band}" y="${padT}" width="${band}" height="${H - padT - padB}" data-tip="${h}"/>`;
      if (bh > 0) svg += `<path class="bar${h === peak ? ' today' : ''}" d="M${x} ${y0}V${y0 - bh + r}Q${x} ${y0 - bh} ${x + r} ${y0 - bh}H${x + bw - r}Q${x + bw} ${y0 - bh} ${x + bw} ${y0 - bh + r}V${y0}Z"/>`;
      if (h % 6 === 0) svg += `<text class="tick" x="${h * band + band / 2}" y="${H - 5}" text-anchor="middle">${hourLabel(h)}</text>`;
    });
    if (mins[peak] > 0) svg += `<text class="peak" x="${clamp(peak * band + band / 2, 30, W - 30)}" y="${H - padB - (mins[peak] / max) * (H - padT - padB) - 4}" text-anchor="middle">peak ${hourLabel(peak)}</text>`;
    svg += `<line class="axis" x1="0" x2="${W}" y1="${H - padB}" y2="${H - padB}"/></svg>`;
    host.innerHTML = (d.trees ? svg : '<p class="empty">Your focus hours will show here.</p>') + table(['Hour', 'Minutes'], mins.map((m, h) => [hourLabel(h), String(m)]));
    wireTips(host, (el) => { const h = +el.dataset.tip; return `<b>${fmtMin(mins[h])}</b> · ${hourLabel(h)}–${hourLabel((h + 1) % 24)}`; });
  }

  // the three ducks you've hatched most; every duck is in the gallery
  function renderCollection(d) {
    const hatched = SPECIES.filter((sp) => d.bySpecies.get(sp));
    const top = [...hatched].sort((a, b) => d.bySpecies.get(b) - d.bySpecies.get(a)).slice(0, 3);
    $('#collection').innerHTML = top.length
      ? `<div class="podium">${top.map((sp, i) => {
        const info = Art.KINDS[sp];
        return `<button type="button" class="specimen" data-duck="${sp}" title="${esc(info.name)}"><span class="rank">${i + 1}</span>${Art.duckSVG(sp)}
          <span class="n">${esc(info.kanji)}</span><span class="e">${esc(info.name)}</span>
          <span class="c">${plural(d.bySpecies.get(sp), 'duck')}</span></button>`;
      }).join('')}</div>`
      : '<p class="empty">The ducks you hatch most will show here.</p>';
    $('#collection-note').textContent = `${hatched.length} of ${SPECIES.length} hatched`;
  }

  /* ───────────── every duck: to choose one, or to look through ───────────── */
  // the ducks you hatched lately, newest first, then the rest in the usual order
  function recentDucks() {
    const seen = new Set(), list = derive().list;
    for (let i = list.length - 1; i >= 0 && seen.size < 8; i--) {
      const k = Art.kindOf(list[i].species);
      if (SPECIES.includes(k)) seen.add(k);
    }
    for (const sp of SPECIES) seen.add(sp);
    return [...seen];
  }

  // mode 'pick': tapping a duck chooses it for the next egg. 'gallery': tapping one shows it big.
  function openDucks(mode, sp) {
    const d = derive(), random = S.settings.randomSpecies, pick = mode === 'pick';
    $('#ducks-title').textContent = pick ? 'Choose a duck' : 'Duck gallery';
    $('#ducks-note').textContent = pick ? '' : `${SPECIES.filter((k) => d.bySpecies.get(k)).length} of ${SPECIES.length} hatched`;
    $('#duck-grid').innerHTML = (pick ? `<button type="button" class="dtile" data-pick="random" aria-pressed="${random}">${SURPRISE_SVG}<span class="n">運</span><span class="e">Surprise</span><span class="c">a new one each time</span></button>` : '') +
      SPECIES.map((k) => {
        const info = Art.KINDS[k], n = d.bySpecies.get(k) || 0;
        return `<button type="button" class="dtile${!pick && !n ? ' unhatched' : ''}" data-${pick ? 'pick' : 'duck'}="${k}" aria-pressed="${pick && !random && k === S.pick.species}">${Art.duckSVG(k)}
          <span class="n">${esc(info.kanji)}</span><span class="e">${esc(info.name)}</span>${pick ? '' : `<span class="c">${n ? plural(n, 'duck') : 'not yet'}</span>`}</button>`;
      }).join('');
    $('#duck-grid').hidden = false;
    $('#duck-detail').hidden = true;
    const dlg = $('#ducks-dialog');
    if (!dlg.open) dlg.showModal();
    if (sp) showDuck(sp);
    else $('#ducks-dialog .sheet-body').scrollTop = 0;
  }

  // one duck, big, with what it's about; ‹ › go through them all
  function showDuck(sp) {
    const info = Art.KINDS[sp], n = derive().bySpecies.get(sp) || 0, i = SPECIES.indexOf(sp);
    const before = SPECIES[(i - 1 + SPECIES.length) % SPECIES.length], after = SPECIES[(i + 1) % SPECIES.length];
    $('#duck-detail').innerHTML = `
      <button class="link" type="button" data-back>← All ducks</button>
      <div class="duck-big">${Art.duckSVG(sp)}</div>
      <h3 class="duck-name"><span class="jp">${esc(info.kanji)}</span> ${esc(info.name)}</h3>
      <p class="duck-blurb">${esc(info.blurb || '')}</p>
      <p class="muted small">${n ? `You've hatched ${plural(n, 'duck')} like this.` : 'Not hatched yet.'}</p>
      <div class="duck-nav">
        <button class="icon-btn" type="button" data-duck="${before}" aria-label="The duck before">‹</button>
        <button class="btn primary" type="button" data-hatch-with="${sp}">Hatch with this duck</button>
        <button class="icon-btn" type="button" data-duck="${after}" aria-label="The next duck">›</button>
      </div>`;
    $('#duck-grid').hidden = true;
    $('#duck-detail').hidden = false;
    $('#ducks-dialog .sheet-body').scrollTop = 0;
  }

  function chooseDuck(sp) {
    if (sp === 'random') {
      if (!S.settings.randomSpecies) saveSettings({ randomSpecies: true }, { quiet: true });
    } else {
      S.pick.species = sp;
      if (S.settings.randomSpecies) saveSettings({ randomSpecies: false }, { quiet: true });
      savePick();
    }
    $('#ducks-dialog').close();
    renderPlantControls();
    paintTimer();
  }

  function badgeFacts(d) {
    let perfect = false;
    for (const k of d.byDay.keys()) {
      if (weekday(k) !== 0) continue;
      if ([0, 1, 2, 3, 4].every((i) => (d.byDay.get(addDays(k, i)) || 0) >= d.goal)) { perfect = true; break; }
    }
    // the busiest day (minutes and ducks), weekends with focus on both days, pomodoros, and sessions with friends
    const ducksByDay = new Map();
    let rounds = 0, bestRounds = 0, together = 0;
    for (const s of d.list) {
      if (s.status === 'withered') continue;
      ducksByDay.set(s._day, (ducksByDay.get(s._day) || 0) + 1);
      rounds += s.rounds || 0;
      bestRounds = Math.max(bestRounds, s.rounds || 0);
      if (s.room) together++;
    }
    const weekend = [...d.byDay.keys()].some((k) => weekday(k) === 5 && d.byDay.get(addDays(k, 1)) > 0);
    return {
      ...d, perfect, speciesGrown: d.bySpecies.size, ankiBest: ankiStreaks().best, weekend, rounds, bestRounds, together,
      bigDay: Math.max(0, ...d.byDay.values()), busyDay: Math.max(0, ...ducksByDay.values()),
      tagsUsed: [...d.byTag.keys()].filter((t) => t !== 'Untagged').length,
    };
  }
  const BADGES = [
    ['一', '一羽目', 'First duck', 'Hatch your first duck', (x) => x.trees >= 1],
    ['十', '十羽', 'Ten ducks', 'Hatch ten ducks', (x) => x.trees >= 10, (x) => [x.trees, 10]],
    ['百', '百羽', 'A hundred ducks', 'Hatch a hundred ducks', (x) => x.trees >= 100, (x) => [x.trees, 100]],
    ['三日', '三日坊主卒業', 'Past three days', 'A streak longer than three days', (x) => x.best >= 4, (x) => [x.best, 4]],
    ['週', '一週間', 'One week', 'A 7-day streak', (x) => x.best >= 7, (x) => [x.best, 7]],
    ['継続', '継続は力なり', 'Persistence is power', 'A 30-day streak', (x) => x.best >= 30, (x) => [x.best, 30]],
    ['皆勤', '皆勤', 'Perfect week', 'Your goal every weekday of a week', (x) => x.perfect],
    ['没頭', '没頭', 'Absorbed', 'One session of 90 minutes or more', (x) => x.longest >= 90],
    ['早起', '早起き', 'Early bird', 'Focus before 7 am', (x) => x.early],
    ['夜更', '夜更かし', 'Night owl', 'Focus after 11 pm', (x) => x.night],
    ['不屈', '不屈', 'Unbroken', '25 ducks in a row, no cold eggs', (x) => x.bestRun >= 25, (x) => [x.bestRun, 25]],
    ['千里', '千里の道', 'A thousand miles', '100 hours of focus', (x) => x.total >= 6000, (x) => [Math.floor(x.total / 60), 100]],
    ['全員', '全員集合', 'Everyone\'s here', `Hatch all ${Art.ORDER.length} kinds of duck`, (x) => x.speciesGrown >= Art.ORDER.length, (x) => [x.speciesGrown, Art.ORDER.length]],
    ['五十', '五十羽', 'Fifty ducks', 'Hatch 50 ducks', (x) => x.trees >= 50, (x) => [x.trees, 50]],
    ['五百', '五百羽', 'A flock of five hundred', 'Hatch 500 ducks', (x) => x.trees >= 500, (x) => [x.trees, 500]],
    ['十時', '十時間', 'Ten hours', '10 hours of focus', (x) => x.total >= 600, (x) => [Math.floor(x.total / 60), 10]],
    ['五百時', '五百時間', 'Five hundred hours', '500 hours of focus', (x) => x.total >= 30000, (x) => [Math.floor(x.total / 60), 500]],
    ['百日', '百日', 'A hundred days', 'A 100-day streak', (x) => x.best >= 100, (x) => [x.best, 100]],
    ['大日', '大一番', 'Big day', '4 hours of focus in one day', (x) => x.bigDay >= 240, (x) => [Math.floor(x.bigDay / 60), 4]],
    ['鉄人', '鉄人', 'Iron will', '6 hours of focus in one day', (x) => x.bigDay >= 360, (x) => [Math.floor(x.bigDay / 60), 6]],
    ['深海', '深海', 'Deep dive', 'One session of 3 hours or more', (x) => x.longest >= 180],
    ['賑', '賑やか', 'Busy pond', '5 ducks in one day', (x) => x.busyDay >= 5, (x) => [x.busyDay, 5]],
    ['週末', '週末戦士', 'Weekend warrior', 'Focus on both days of a weekend', (x) => x.weekend],
    ['多才', '多才', 'Many talents', 'Study 5 different tags', (x) => x.tagsUsed >= 5, (x) => [x.tagsUsed, 5]],
    ['茄', 'ポモドーロ', 'Pomodoro', 'Finish a 4-round pomodoro', (x) => x.bestRounds >= 4],
    ['畑', 'トマト畑', 'Tomato field', '50 pomodoro rounds', (x) => x.rounds >= 50, (x) => [x.rounds, 50]],
    ['仲間', '仲間', 'Study buddy', 'Study with a friend', (x) => x.together >= 1],
    ['絆', '絆', 'Bond', '10 sessions with friends', (x) => x.together >= 10, (x) => [x.together, 10]],
    ['共', '一緒に', 'Better together', '50 sessions with friends', (x) => x.together >= 50, (x) => [x.together, 50]],
    ['暗記', '暗記', 'Memorizer', 'Review Anki 7 days in a row', (x) => x.ankiBest >= 7, (x) => [x.ankiBest, 7], 'anki'],
  ];
  function renderBadges(d) {
    const x = badgeFacts(d);
    let earned = 0;
    // Anki's only for whoever runs this PC, and only once Anki is connected
    const shown = BADGES.filter((b) => b[6] !== 'anki' || (S.me?.role === 'owner' && S.anki?.data));
    $('#badges').innerHTML = `<div class="badges">${shown.map(([stamp, kanji, title, desc, test, prog]) => {
      const ok = test(x);
      if (ok) earned++;
      const p = !ok && prog ? prog(x) : null;
      return `<div class="badge${ok ? ' earned' : ''}"><span class="stamp" aria-hidden="true">${stamp}</span>
        <div><div class="t"><span class="jp">${kanji}</span><br>${title}</div><div class="d">${desc}${p ? ` · ${Math.min(p[0], p[1])}/${p[1]}` : ''}</div></div></div>`;
    }).join('')}</div>`;
    $('#badge-count').textContent = `${earned} of ${shown.length}`;
  }

  function ankiStreaks() {
    const data = S.anki?.data;
    if (!data?.byDay?.length) return { current: 0, best: 0, today: 0, map: new Map() };
    const map = new Map(data.byDay.map(([k, n]) => [k, n]));
    const today = todayKey();
    let current = 0;
    for (let k = map.has(today) ? today : addDays(today, -1); (map.get(k) || 0) > 0; k = addDays(k, -1)) current++;
    let best = 0, run = 0, prev = null;
    for (const k of [...map.keys()].sort()) {
      if ((map.get(k) || 0) <= 0) { run = 0; prev = k; continue; }
      run = prev && addDays(prev, 1) === k ? run + 1 : 1;
      best = Math.max(best, run);
      prev = k;
    }
    return { current, best: Math.max(best, current), today: map.get(today) || 0, map };
  }
  function renderAnki() {
    const card = $('#anki-card');
    const data = S.anki?.data;
    if (!data) {
      card.hidden = false;
      $('#anki').innerHTML = '<p class="empty">Anki numbers appear here once Anki (with AnkiConnect) is open on your PC.</p>';
      return;
    }
    const st = ankiStreaks();
    const decks = (data.decks || []).map((name) => [name, data.counts[name] || [0, 0, 0]]).filter(([, c]) => c[0] + c[1] + c[2] > 0);
    const shown = decks.sort((a, b) => (b[1][1] + b[1][2]) - (a[1][1] + a[1][2])).slice(0, 8);
    const age = data.at ? ago(data.at) : '';
    const days = [];
    for (let i = 13; i >= 0; i--) days.push(addDays(todayKey(), -i));
    const max = Math.max(1, ...days.map((k) => st.map.get(k) || 0));
    const spark = `<svg viewBox="0 0 140 30" style="width:140px;height:30px" role="img" aria-label="Reviews over the last two weeks">${days.map((k, i) => {
      const v = st.map.get(k) || 0, h = (v / max) * 26;
      return `<rect x="${i * 10 + 1}" y="${28 - h}" width="8" height="${Math.max(h, v ? 1 : 0)}" rx="2" fill="var(${k === todayKey() ? '--grow-strong' : '--grow'})"><title>${esc(fmtDate(k, { month: 'short', day: 'numeric' }))}: ${v}</title></rect>`;
    }).join('')}</svg>`;
    $('#anki').innerHTML = `<div class="anki">
      <div class="anki-top">
        <div class="stat"><div class="v" style="font:700 26px/1.1 var(--body)">${st.today.toLocaleString()}</div><div class="k muted small">reviewed today</div></div>
        <div class="stat"><div class="v" style="font:700 26px/1.1 var(--body)">${st.current}</div><div class="k muted small">day review streak</div></div>
        <div>${spark}<div class="muted small">last 14 days</div></div>
      </div>
      ${shown.length ? `<div class="anki-decks"><div class="anki-deck head"><span class="nm">Due now</span><span>New</span><span>Learn</span><span>Review</span></div>
        ${shown.map(([name, c]) => `<div class="anki-deck"><span class="nm" style="padding-left:${(name.split('::').length - 1) * 12}px">${esc(name.split('::').pop())}</span><span class="c-new">${c[0]}</span><span class="c-learn">${c[1]}</span><span class="c-rev">${c[2]}</span></div>`).join('')}</div>` : '<p class="muted small">Nothing due right now. 見事.</p>'}
      <p class="muted small">${S.anki.live ? `Live from Anki on your PC · updated ${age}` : `Anki is closed on your PC · numbers from ${age}`}</p></div>`;
  }

  /* ───────────── 履歴 Log ───────────── */
  function renderLog() {
    const d = derive();
    const tags = [...new Set(d.list.map((s) => s.tag).filter(Boolean))];
    $('#log-filter').innerHTML = ['', ...tags].map((t) => `<button type="button" class="chip" data-log-tag="${esc(t)}" style="--c:${t ? tagColor(t) : 'var(--ink-3)'}" aria-pressed="${t === S.logTag}">${t ? `<span class="dot"></span>${esc(t)}` : 'All'}</button>`).join('');
    const tzNote = $('#log-tz');
    tzNote.hidden = deviceZone() === zone();
    tzNote.textContent = `Times are shown in your home time zone (${zone().replace(/_/g, ' ')}).`;
    const list = d.list.filter((s) => !S.logTag || s.tag === S.logTag).reverse();
    const groups = new Map();
    for (const s of list) {
      if (!groups.has(s._day)) groups.set(s._day, []);
      groups.get(s._day).push(s);
    }
    const keys = [...groups.keys()];
    const shown = keys.slice(0, S.logDays);
    $('#log-list').innerHTML = shown.length ? shown.map((k) => {
      const items = groups.get(k);
      const total = d.byDay.get(k) || 0;
      return `<div class="day"><div class="day-head"><span class="d"><span class="jp">${WD_KANJI[weekday(k)]}</span>${esc(fmtDate(k, { weekday: 'short', month: 'short', day: 'numeric', year: k.slice(0, 4) !== d.today.slice(0, 4) ? 'numeric' : undefined }))}</span>
        <span class="t">${total >= d.goal ? '<span class="met">達成</span>' : ''}${fmtMin(total)}</span></div>${items.map(sessionRow).join('')}</div>`;
    }).join('') : `<p class="empty">${S.logTag ? 'No sessions with this tag yet.' : 'Nothing logged yet. Hatch a duck, or log time you studied without the timer.'}</p>`;
    $('#log-more').hidden = keys.length <= S.logDays;
  }

  function openSession(id) {
    const s = id ? S.sessions.get(id) : null;
    const dlg = $('#session-dialog');
    $('#session-title').textContent = s ? 'Edit session' : 'Log time';
    $('#f-delete').hidden = !s;
    $('#f-withered-row').hidden = !s;
    const now = Date.now();
    const minutes = s ? s.minutes : 25;
    const start = s ? s.start : now - minutes * MIN;
    const p = parts(start);
    $('#f-date').value = `${p.year}-${p.month}-${p.day}`;
    $('#f-date').max = todayKey();
    $('#f-time').value = `${p.hour === '24' ? '00' : p.hour}:${p.minute}`;
    $('#f-min').value = String(minutes);
    $('#f-tag').value = s ? s.tag : S.pick.tag;
    $('#f-note').value = s ? s.note : '';
    $('#f-withered').checked = s ? s.status === 'withered' : false;
    $('#tag-list').innerHTML = S.settings.tags.map((t) => `<option value="${esc(t.name)}">`).join('');
    const src = s ? ({ genkan: 'the homepage', manual: 'by hand', import: 'an import', sync: 'sync' }[s.source] || (s.manual ? 'by hand' : 'Dakku')) : '';
    $('#f-meta').textContent = s ? `${speciesName(s.species)} · logged from ${src}${zone() !== deviceZone() ? ` · times in ${zone()}` : ''}` : (zone() !== deviceZone() ? `Times are in your home time zone (${zone()}).` : '');
    dlg.dataset.id = s ? s.id : '';
    delete dlg.dataset.timeSet;
    dlg.showModal();
  }

  function saveSession(ev) {
    ev.preventDefault();
    const dlg = $('#session-dialog');
    const id = dlg.dataset.id;
    const minutes = Math.round(+$('#f-min').value);
    if (!(minutes >= 1 && minutes <= 1440)) { toast('Minutes should be between 1 and 1440.'); return; }
    const date = $('#f-date').value, time = $('#f-time').value || '00:00';
    if (!date) { toast('Pick a date.'); return; }
    const start = zonedMs(date, time);
    if (start > Date.now() + MIN) { toast("That's in the future."); return; }
    const tag = $('#f-tag').value.trim().slice(0, 40);
    const old = id ? S.sessions.get(id) : null;
    const session = { id: id || uid(), start, minutes, tag, note: $('#f-note').value.trim().slice(0, 300), updated: serverNow() };
    if (old) session.status = $('#f-withered').checked ? 'withered' : 'done';
    else {
      const avail = unlocked();
      Object.assign(session, { status: 'done', source: 'manual', manual: true, species: S.settings.randomSpecies || !avail.includes(S.pick.species) ? avail[Math.floor(Math.random() * avail.length)] : S.pick.species });
    }
    if (tag && !S.settings.tags.some((t) => t.name.toLowerCase() === tag.toLowerCase())) {
      saveSettings({ tags: [...S.settings.tags, { name: tag.slice(0, 24), color: PALETTE[S.settings.tags.length % PALETTE.length][0] }] }, { quiet: true });
    }
    enqueue({ op: 'upsert', session });
    dlg.close();
    toast(old ? 'Saved.' : `Logged ${fmtMin(minutes)}${tag ? ` of ${tag}` : ''}.`);
    render();
  }

  async function deleteSession() {
    const dlg = $('#session-dialog');
    const id = dlg.dataset.id;
    if (!id) return;
    dlg.close();
    if (!(await confirmBox('Delete this session?', 'Its duck leaves your pond, and its minutes no longer count.', 'Delete'))) return;
    enqueue({ op: 'delete', id, updated: serverNow() });
    toast('Deleted.');
    render();
  }

  /* ───────────── 設定 Settings ───────────── */
  function saveSettings(patch, { quiet = false } = {}) {
    S.settings = { ...S.settings, ...patch };
    invalidate();
    enqueue({ op: 'settings', patch });
    if ('theme' in patch) applyTheme();
    if (!quiet) render();
  }

  function renderSettings() {
    const s = S.settings;
    const active = document.activeElement;
    if (active !== $('#set-name')) $('#set-name').value = s.name;
    if (active !== $('#set-goal')) $('#set-goal').value = s.goal;
    $('#set-presets').innerHTML = s.presets.map((m) => `<span class="chip">${m} min<button type="button" class="x" data-preset-del="${m}" aria-label="Remove ${m} minutes">×</button></span>`).join('') +
      (s.presets.length < 6 ? '<button type="button" class="chip add" data-preset-add>+ Add</button>' : '');
    $('#set-sound').checked = s.sound;
    $('#set-awake').checked = s.keepAwake;
    $('#set-deep').checked = s.deepFocus;
    $('#set-random').checked = s.randomSpecies;
    const counts = derive().byTag;
    $('#set-tags').innerHTML = s.tags.length ? s.tags.map((t, i) => `
      <div class="tag-row" data-i="${i}">
        <button type="button" class="swatch" style="--c:${tagColor(t.name)}" data-tag-color="${i}" aria-label="Color for ${esc(t.name)}"></button>
        <input type="text" value="${esc(t.name)}" maxlength="24" data-tag-name="${i}" aria-label="Tag name">
        <span class="count">${counts.has(t.name) ? fmtMin(counts.get(t.name)) : ''}</span>
        <button type="button" class="link" data-tag-del="${i}" aria-label="Remove ${esc(t.name)}">Remove</button>
        <div class="palette" data-palette="${i}" hidden>${PALETTE.map(([light, dark, kanji, name]) => `<button type="button" style="--c:${dark}" data-pick-color="${light}" title="${kanji} ${name}" aria-label="${name}" aria-pressed="${t.color.toLowerCase() === light.toLowerCase()}"></button>`).join('')}</div>
      </div>`).join('') : '<p class="empty">No tags yet.</p>';
    const me = S.me?.person;
    $('#look-row').hidden = $('#set-colors').hidden = !me || (!inGroups() && S.me?.role !== 'friend');
    if (me) {
      $('#set-badge').textContent = me.mark || '?';
      $('#set-badge').style.setProperty('--c', me.color);
      if (document.activeElement !== $('#set-mark')) $('#set-mark').value = me.mark || '';
      $('#set-colors').innerHTML = PALETTE.map(([light, , kanji, name]) => `<button type="button" style="--c:${light}" data-pcolor="${light}" title="${kanji} ${name}" aria-label="${name}" aria-pressed="${me.color.toLowerCase() === light.toLowerCase()}"></button>`).join('');
    }
    const ponds = Art.pondThemes();
    const seasonal = ['spring', 'autumn', 'winter'].some((t) => ponds.includes(t));
    $('#set-ponds').innerHTML = [...ponds.sort((a, b) => Object.keys(PONDS).indexOf(a) - Object.keys(PONDS).indexOf(b)), ...(seasonal ? ['seasonal'] : [])].map((t) => {
      const pic = Art.sprites.ponds[t]?.wide || Art.sprites.ponds[t]?.tall || Art.sprites.ponds[themeFor('seasonal')]?.wide;
      const [kanji, name] = PONDS[t] || ['池', t];
      return `<button type="button" class="pond-pick" data-pond-pick="${t}" aria-pressed="${(s.pondTheme || 'classic') === t}">
        ${pic ? `<img src="${esc(pic.src)}" alt="" loading="lazy">` : ''}<span class="nm"><span class="jp">${kanji}</span>${name}</span></button>`;
    }).join('');
    $('#set-decor').innerHTML = DECOR.map(([id, kanji, name]) => {
      const pic = Art.sprites.decor[id];
      return `<button type="button" class="decor-pick" data-decor="${id}" aria-pressed="${(s.decor || []).includes(id)}"${pic ? '' : ' disabled title="Not painted yet"'}>
        ${pic ? `<img src="${esc(pic.src)}" alt="" loading="lazy">` : ''}<span class="nm"><span class="jp">${kanji}</span>${name}</span></button>`;
    }).join('');
    $('#set-events').innerHTML = EVENTS.map(([id, icon, about]) => {
      const pic = Art.sprites.ponds[id]?.wide || Art.sprites.ponds[id]?.tall, [kanji, name] = PONDS[id];
      return `<button type="button" class="event-pick" data-event="${id}" data-theme="${id}" aria-pressed="${s.theme === id && s.pondTheme === id}">
        ${pic ? `<img src="${esc(pic.src)}" alt="" loading="lazy">` : `<span class="ev-icon" aria-hidden="true">${icon}</span>`}
        <span class="nm"><span class="jp">${kanji}</span>${name}</span><small>${about}</small></button>`;
    }).join('');
    const unpainted = ['spring', 'autumn', 'winter', 'night', 'garden', 'sakura'].filter((t) => !ponds.includes(t)).map((t) => (t === 'garden' ? 'a garden' : t));
    const list = unpainted.length > 1 ? `${unpainted.slice(0, -1).join(', ')} and ${unpainted.at(-1)}` : unpainted[0];
    $('#set-ponds-note').textContent = unpainted.length && S.me?.role === 'owner'
      ? `${unpainted.length > 1 ? 'More ponds' : 'One more pond'} (${list}) can be painted with ChatGPT: see art/chatgpt-prompts.md.` : '';
    $('#friend-alerts-row').hidden = !inGroups();
    $('#cheer-alerts-row').hidden = !inGroups();
    $('#set-friend-alerts').checked = s.friendAlerts !== false;
    $('#set-cheer-alerts').checked = s.cheerAlerts !== false;
    $('#set-weekly-recap').checked = s.weeklyRecap !== false;
    if (S.me?.role === 'owner') renderPeopleAdmin();
    $('#set-themes').innerHTML = THEMES.map(([id, kanji, name, bg, accent]) => `
      <button type="button" class="theme" data-theme-pick="${id}" aria-pressed="${s.theme === id}">
        <span class="sw" style="--b:${bg};--a:${accent}"><i></i><i></i></span>
        <span class="nm"><span class="jp">${kanji}</span>${name}</span></button>`).join('');
    renderPushSettings();
    $('#set-remind').checked = !!s.reminder?.enabled;
    $('#set-remind-time').value = s.reminder?.time || '20:00';
    $('#set-remind-weekdays').checked = s.reminder?.weekdaysOnly !== false;
    $('#remind-row').hidden = !s.reminder?.enabled;
    const tzSel = $('#set-tz');
    if (!tzSel.options.length || tzSel.dataset.for !== s.timeZone) {
      let zones = [];
      try { zones = Intl.supportedValuesOf('timeZone'); } catch { zones = []; }
      if (!zones.includes(s.timeZone)) zones.unshift(s.timeZone);
      tzSel.innerHTML = zones.map((z) => `<option value="${esc(z)}"${z === s.timeZone ? ' selected' : ''}>${esc(z.replace(/_/g, ' '))}</option>`).join('');
      tzSel.dataset.for = s.timeZone;
    }
    const here = deviceZone();
    $('#tz-device-row').hidden = here === s.timeZone;
    $('#tz-device-text').innerHTML = `This device is in <b>${esc(here.replace(/_/g, ' '))}</b><small>Switch if you've moved, not for a trip</small>`;
    renderDevices();
    renderPasscode();
    renderAbout();
    $('#pair-row').hidden = false;
    $('#signout-row').hidden = !!S.me?.trusted;
    paintSync();
  }

  // your People & groups: who's on your Dakku, their devices, groups and invites
  async function renderPeopleAdmin(refresh = false) {
    const door = S.server?.addresses?.friends;
    $('#set-friends-door').innerHTML = door
      ? `<div class="row"><span class="row-label">The friends' door is open<small>Friends join and study from anywhere, without Tailscale, at <b>${esc(door)}</b></small></span></div>`
      : `<div class="row"><span class="row-label">The friends' door is closed<small>So friends can join without Tailscale, run <b>scripts/enable-friends.sh</b> (in Dakku's folder) on your PC once.</small></span></div>`;
    if (refresh || !S.admin) {
      try { S.admin = await api('GET', '/api/people'); } catch { if (!S.admin) { $('#set-people').innerHTML = '<p class="empty">Unavailable offline.</p>'; return; } }
    }
    const { people, groups, invites } = S.admin;
    const byId = peopleMap(people);
    const groupRows = groups.map((g) => `
      <div class="admin-group">
        <div class="admin-head"><b>${esc(g.name)}</b><span class="pbadges">${g.members.map((m) => byId[m] ? badgeHTML(byId[m]) : '').join('')}</span></div>
        <div class="admin-acts">
          <button type="button" class="btn small primary" data-invite-group="${esc(g.id)}">Invite</button>
          <select data-group-theme="${esc(g.id)}" aria-label="Pond for ${esc(g.name)}">${['', ...Art.pondThemes(), ...(Art.pondThemes().length > 1 ? ['seasonal'] : [])].map((t) => `<option value="${t}"${(g.theme || '') === t ? ' selected' : ''}>${t ? `${PONDS[t]?.[1] || t} pond` : 'Each person\'s own pond'}</option>`).join('')}</select>
          <button type="button" class="link" data-rename-group="${esc(g.id)}">Rename</button>
          <button type="button" class="link danger" data-delete-group="${esc(g.id)}">Delete</button>
        </div>
      </div>`).join('');
    const others = people.filter((p) => p.id !== 'me');
    const peopleRows = others.map((p) => `
      <div class="device">
        <span class="nm">${badgeHTML(p)} ${esc(p.name)}${p.studying ? '<em>studying now</em>' : ''}</span>
        <span class="meta">${plural(p.devices.length, 'device')}${p.lastSeen ? ` · seen ${esc(ago(p.lastSeen))}` : ''} · ${fmtMin(p.week)} this week · ${fmtHours(p.minutes)} h in all</span>
        <span class="acts"><button type="button" class="link" data-person-link="${esc(p.id)}">Sign-in link</button><button type="button" class="link danger" data-person-remove="${esc(p.id)}">Remove</button></span>
      </div>`).join('');
    const inviteRows = invites.map((i) => `
      <div class="device"><span class="nm">${i.person ? `Sign-in link for ${esc(byId[i.person]?.name || 'someone')}` : `Invite to ${esc(groups.find((g) => g.id === i.grp)?.name || 'a group')}`}</span>
        <span class="meta">${i.uses === 1 ? '1 use' : `${i.uses} uses`} left · until ${esc(fmtDate(dayKey(i.expires), { month: 'short', day: 'numeric' }))}</span>
        <span class="acts"><button type="button" class="link" data-invite-revoke="${esc(i.id)}">Take back</button></span></div>`).join('');
    $('#set-people').innerHTML = `
      ${groupRows || '<p class="empty">No groups yet.</p>'}
      <div class="row"><span class="row-label">Make a group<small>Then invite people into it</small></span><button type="button" class="btn small" data-act="new-group">New group</button></div>
      ${others.length ? `<h3 class="admin-sub">People</h3>${peopleRows}` : ''}
      ${invites.length ? `<h3 class="admin-sub">Invites waiting</h3>${inviteRows}` : ''}`;
  }

  async function renderDevices(refresh = false) {
    const host = $('#set-devices');
    if (refresh || !S.devices) {
      try { S.devices = (await api('GET', '/api/devices')).devices; } catch { if (!S.devices) { host.innerHTML = '<p class="empty">Device list unavailable offline.</p>'; return; } }
    }
    const current = S.me?.device?.id;
    host.innerHTML = (S.me?.trusted ? `<div class="device"><span class="nm">This PC<em>here</em></span><span class="meta">Runs Dakku · always signed in</span></div>` : '') +
      (S.devices.length ? S.devices.map((d) => `
        <div class="device"><span class="nm">${esc(d.name)}${d.id === current ? '<em>this device</em>' : ''}</span>
          <span class="meta">Last seen ${esc(ago(d.last_seen))}${d.last_ip ? ` · ${esc(d.last_ip)}` : ''}</span>
          <span class="acts"><button type="button" class="link" data-dev-rename="${esc(d.id)}">Rename</button><button type="button" class="link" data-dev-remove="${esc(d.id)}">Sign out</button></span></div>`).join('')
        : '<p class="empty">No other devices yet.</p>');
  }

  function renderPasscode() {
    const host = $('#set-passcode');
    if (S.me?.trusted) {
      host.innerHTML = `<div class="row"><span class="row-label">Your passcode<small>Five words. Use it to sign in on a new device.</small></span><button type="button" class="btn small" data-act="show-passcode">${S.passcode ? 'Hide' : 'Show passcode'}</button></div>
        ${S.passcode ? `<div class="passcode">${esc(S.passcode)}</div>` : ''}
        <div class="row"><span class="row-label">Make a new passcode<small>Signs out every other device</small></span><button type="button" class="btn small ghost" data-act="new-passcode">New passcode</button></div>`;
    } else {
      host.innerHTML = `<div class="row"><span class="row-label">Change the passcode<small>You'll need the current one. Other devices get signed out.</small></span><button type="button" class="btn small ghost" data-act="change-passcode">Change</button></div>
        <p class="note">Forgot it? Open Dakku on your PC to see it.</p>`;
    }
  }

  function renderAbout() {
    const a = S.server?.addresses || {};
    const rows = [];
    if (a.https) rows.push(['Anywhere (secure)', a.https, 'Best: works offline and can send notifications']);
    if (a.tailnet) rows.push(['Anywhere, with Tailscale on', a.tailnet, 'Your private Tailscale network']);
    for (const lan of a.lan || []) rows.push(['At home (Wi-Fi)', lan, '']);
    $('#set-about').innerHTML = `
      ${rows.map(([k, url, note]) => `<div class="addr"><span>${esc(k)}${note ? ` · ${esc(note)}` : ''}</span><code>${esc(url)}</code></div>`).join('')}
      <div class="addr"><span>Version</span><code>Dakku ${esc(S.server?.version || S.me?.version || '')} · days in ${esc(zone())}</code></div>`;
  }

  async function renderPushSettings() {
    const host = $('#set-push');
    const iOS = /iP(hone|ad|od)/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone;
    let html;
    if (location.protocol !== 'https:') {
      const a = S.server?.addresses?.https;
      html = `<p class="note">Notifications need Dakku's secure address.${a ? ` Open <b>${esc(a)}</b> instead.` : ' Run <b>scripts/enable-https.sh</b> (in Dakku\'s folder) on your PC once, then use the https address it prints.'}</p>`;
    } else if (!('serviceWorker' in navigator) || !('PushManager' in window) || typeof Notification === 'undefined') {
      html = iOS && !standalone ? '<p class="note">On iPhone, notifications work once Dakku is on your Home Screen: tap Share → <b>Add to Home Screen</b>, then open it from there.</p>' : "<p class=\"note\">This browser can't receive notifications.</p>";
    } else if (Notification.permission === 'denied') {
      html = '<p class="note">Notifications are blocked for Dakku in this browser\'s settings.</p>';
    } else {
      const reg = S.swReg || (await navigator.serviceWorker.getRegistration());
      S.pushSub = reg ? await reg.pushManager.getSubscription() : null;
      html = S.pushSub
        ? '<div class="row"><span class="row-label">On for this device<small>When a duck hatches, and your daily reminder</small></span><span class="inline"><button type="button" class="btn small" data-act="push-test">Test</button><button type="button" class="btn small ghost" data-act="push-off">Turn off</button></span></div>'
        : '<div class="row"><span class="row-label">Tell me when a duck hatches<small>Even when Dakku is closed</small></span><button type="button" class="btn small primary" data-act="push-on">Turn on</button></div>';
    }
    host.innerHTML = html;
  }

  const b64uBytes = (s) => {
    const raw = atob(s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4));
    return Uint8Array.from(raw, (c) => c.charCodeAt(0));
  };
  async function pushOn() {
    try {
      const perm = await Notification.requestPermission();
      if (perm !== 'granted') { toast('Notifications were not allowed.'); return; }
      const reg = S.swReg || (await navigator.serviceWorker.ready);
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64uBytes(S.vapidKey) });
      await api('POST', '/api/push/subscribe', { subscription: sub.toJSON() });
      S.pushSub = sub;
      toast('Notifications are on for this device.');
    } catch (err) {
      toast(err instanceof Offline ? "Your PC can't be reached right now." : `Couldn't turn them on: ${err.message}`);
    }
    renderPushSettings();
  }
  async function pushOff() {
    try {
      if (S.pushSub) {
        await api('POST', '/api/push/unsubscribe', { endpoint: S.pushSub.endpoint }).catch(() => {});
        await S.pushSub.unsubscribe();
      }
      S.pushSub = null;
      toast('Notifications are off for this device.');
    } catch (err) { toast(err.message); }
    renderPushSettings();
  }

  let pairTimer = 0;
  async function openPair() {
    const friend = S.me?.role === 'friend';
    $('#pair-dialog .steps li:first-child').hidden = friend; // friends don't need Tailscale
    if (!S.me?.trusted && !friend) {
      await confirmBox('Add a device', 'Pairing codes come from the PC that runs Dakku. Open Dakku there (http://localhost:8640) → Settings → Add a device. Or sign in on the new device with your five-word passcode.', 'OK', true);
      return;
    }
    const dlg = $('#pair-dialog');
    const fill = async () => {
      try {
        const res = await api('POST', '/api/pair');
        const url = friend ? res.url || location.origin : S.server?.addresses?.https || res.url || location.origin;
        $('#pair-url').textContent = url;
        $('#pair-qr').innerHTML = QR.svg(url);
        $('#pair-code').textContent = `${res.code.slice(0, 3)} ${res.code.slice(3)}`;
        clearInterval(pairTimer);
        const tick = () => {
          const left = res.expires - Date.now();
          $('#pair-expiry').textContent = left > 0 ? `Works once · expires in ${fmtClock(left)}` : 'Expired';
          if (left <= 0) clearInterval(pairTimer);
        };
        tick();
        pairTimer = setInterval(tick, 1000);
      } catch (err) { toast(err.message); }
    };
    await fill();
    $('#pair-new').onclick = fill;
    dlg.showModal();
    dlg.addEventListener('close', () => { clearInterval(pairTimer); renderDevices(true); }, { once: true });
  }

  /* ───────────── overlays, dialogs, toasts ───────────── */
  function toast(text, ms = 3200) {
    const el = document.createElement('div');
    el.className = 'toast';
    el.textContent = text;
    $('#toasts').appendChild(el);
    setTimeout(() => { el.classList.add('out'); setTimeout(() => el.remove(), 320); }, ms);
  }

  function confirmBox(title, text, yes = 'OK', alertOnly = false) {
    const dlg = $('#confirm-dialog');
    $('#confirm-title').textContent = title;
    $('#confirm-text').textContent = text;
    $('#confirm-yes').textContent = yes;
    $('#confirm-no').hidden = alertOnly;
    dlg.returnValue = '';
    dlg.showModal();
    return new Promise((resolve) => dlg.addEventListener('close', () => resolve(dlg.returnValue === 'yes'), { once: true }));
  }

  // a question with a short typed answer (a name), in Dakku's own sheet; resolves to the text or null
  function askText(title, text, label, value = '', yes = 'OK') {
    const dlg = $('#ask-dialog');
    $('#ask-title').textContent = title;
    $('#ask-text').textContent = text;
    $('#ask-text').hidden = !text;
    $('#ask-label').textContent = label;
    $('#ask-input').value = value;
    $('#ask-yes').textContent = yes;
    dlg.returnValue = '';
    dlg.showModal();
    setTimeout(() => { $('#ask-input').focus(); $('#ask-input').select(); }, 60);
    $('#ask-no').onclick = () => dlg.close('no');
    return new Promise((resolve) => dlg.addEventListener('close', () => {
      const v = $('#ask-input').value.trim();
      resolve(dlg.returnValue === 'yes' && v ? v : null);
    }, { once: true }));
  }

  let lastDone = null;
  function celebrate(s) {
    if (!s) return;
    const away = store.get(K.away, null);
    if (away && away.id === s.id && Date.now() - away.at >= AWAY_GRACE) return; // deep focus: the egg goes cold instead (see checkAway)
    markSeen(s.id);
    if (lastDone && lastDone.id === s.id && !$('#done').hidden) { lastDone = s; return; }
    lastDone = s;
    const d = derive();
    const info = Art.KINDS[Art.kindOf(s.species)];
    const card = $('#done .done-card');
    card.classList.remove('withered');
    $('#done-tree').innerHTML = Art.duckSVG(s.species);
    $('#done-kanji').textContent = '誕生';
    $('#done-title').textContent = `${info.kanji} ${info.name} hatched!`;
    const cheered = [...new Set(cheeredBy.get(s.id) || [])];
    $('#done-sub').textContent = `${fmtMin(s.minutes)}${s.tag ? ` of ${s.tag}` : ''}${s.rounds ? ` · 🍅 ×${s.rounds}` : ''}${cheered.length ? ` · cheered on by ${cheered.join(', ')}` : ''}`;
    // the PC may not have confirmed this duck yet: count it in already
    const pending = !S.sessions.has(s.id) && s.status === 'done';
    const byDay = new Map(d.byDay);
    const day = dayKey(s.start);
    if (pending) byDay.set(day, (byDay.get(day) || 0) + s.minutes);
    const todayMin = byDay.get(d.today) || 0;
    const streak = pending ? streaks(byDay, d.goal, d.today).current : d.streak;
    $('#done-stats').innerHTML = `<div><b>${todayMin}<small style="font-size:14px;font-weight:500">/${d.goal}</small></b><span>min today</span></div><div><b>${streak}</b><span>day streak</span></div><div><b>${d.trees + (pending ? 1 : 0)}</b><span>ducks in all</span></div>`;
    $('#done-share').hidden = false;
    $('#done-again').textContent = 'Hatch another';
    feathers(info.color);
    $('#done').hidden = false;
    render();
  }
  function showWithered(s) {
    if (!s) return;
    lastDone = null;
    $('#done .done-card').classList.add('withered');
    $('#done-tree').innerHTML = Art.duckSVG(s.species, { cold: true });
    $('#done-kanji').textContent = '残念';
    $('#done-title').textContent = 'This egg went cold';
    $('#done-sub').textContent = `${fmtMin(s.minutes)}${s.tag ? ` of ${s.tag}` : ''}${s.note ? ` · ${s.note}` : ''}. It stays in your pond, but doesn't count.`;
    $('#done-stats').innerHTML = '';
    $('#petals').innerHTML = '';
    $('#done-share').hidden = true;
    $('#done-again').textContent = 'Try again';
    $('#done').hidden = false;
  }
  function feathers(color) {
    const host = $('#petals');
    host.innerHTML = '';
    const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#57C7CF';
    const colors = lightTheme() ? ['#FFB3D1', '#E9C6FF', color, accent] : ['#FFFFFF', '#FFFFFF', color, accent]; // white doesn't show on a light page
    for (let i = 0; i < 24; i++) {
      const p = document.createElement('i');
      p.style.left = `${Math.random() * 100}%`;
      p.style.background = colors[i % colors.length];
      p.style.animationDuration = `${3 + Math.random() * 3}s`;
      p.style.animationDelay = `${Math.random() * 1.6}s`;
      p.style.setProperty('--dx', `${(Math.random() - 0.5) * 160}px`);
      p.style.setProperty('--r', `${(Math.random() - 0.5) * 720}deg`);
      host.appendChild(p);
    }
  }

  /* ───────────── share images ───────────── */
  const FONT_D = '"Shippori Mincho", "Noto Serif CJK JP", "Noto Serif JP", "Hiragino Mincho ProN", "Yu Mincho", serif';
  const FONT_B = '"Zen Kaku Gothic New", "Noto Sans CJK JP", "Noto Sans JP", "Hiragino Sans", system-ui, sans-serif';
  async function fontsReady() {
    if (!document.fonts) return;
    const want = [`600 40px ${FONT_D}`, `700 40px ${FONT_D}`, `500 40px ${FONT_B}`, `700 40px ${FONT_B}`, `400 40px ${FONT_B}`];
    await Promise.race([Promise.all(want.map((f) => document.fonts.load(f, '鴨Dakku0123見事'))), sleep(1500)]).catch(() => {});
  }
  function themeColors() {
    const cs = getComputedStyle(document.documentElement);
    const v = (name) => cs.getPropertyValue(name).trim();
    return { bg: v('--bg'), surface: v('--surface'), surface2: v('--surface-2'), ink: v('--ink'), ink2: v('--ink-2'), ink3: v('--ink-3'), line: v('--line'), accent: v('--accent'), leaf: v('--grow'), g: [v('--surface-2'), v('--g1'), v('--g2'), v('--g3'), v('--g4')] };
  }
  function paper(ctx, w, h, c) {
    ctx.fillStyle = c.bg;
    ctx.fillRect(0, 0, w, h);
    const rand = Art.rng('washi');
    ctx.globalAlpha = 0.05;
    for (let i = 0; i < 9000; i++) {
      ctx.fillStyle = rand() < 0.5 ? c.ink : c.surface;
      ctx.fillRect(rand() * w, rand() * h, 1 + rand() * 2, 1 + rand() * 2);
    }
    ctx.globalAlpha = 1;
  }
  function seal(ctx, x, y, size, text, color, rotate = -0.05) {
    ctx.save();
    ctx.translate(x + size / 2, y + size / 2);
    ctx.rotate(rotate);
    ctx.strokeStyle = color;
    ctx.lineWidth = Math.max(3, size * 0.06);
    const r = size * 0.18, s = size / 2;
    ctx.beginPath();
    ctx.roundRect(-s, -s, size, size, r);
    ctx.stroke();
    ctx.fillStyle = color;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    if (text.length === 1) {
      ctx.font = `700 ${size * 0.62}px ${FONT_D}`;
      ctx.fillText(text, 0, size * 0.04);
    } else {
      ctx.font = `700 ${size * 0.4}px ${FONT_D}`;
      [...text].forEach((ch, i) => ctx.fillText(ch, 0, (i - (text.length - 1) / 2) * size * 0.42 + size * 0.03));
    }
    ctx.restore();
  }
  function cardHeader(ctx, W, c, right) {
    seal(ctx, 72, 66, 64, '鴨', c.accent);
    ctx.fillStyle = c.ink;
    ctx.font = `600 40px ${FONT_D}`;
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'left';
    ctx.fillText('Dakku', 158, 100);
    ctx.fillStyle = c.ink2;
    ctx.font = `400 28px ${FONT_B}`;
    ctx.textAlign = 'right';
    ctx.fillText(right, W - 72, 100);
  }
  function cardFooter(ctx, W, H, c) {
    ctx.strokeStyle = c.line;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(72, H - 110);
    ctx.lineTo(W - 72, H - 110);
    ctx.stroke();
    ctx.fillStyle = c.ink3;
    ctx.font = `400 26px ${FONT_B}`;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText('鴨 Dakku · a duck for every focus session', 72, H - 66);
  }
  function statCols(ctx, x, y, w, items, c) {
    const col = w / items.length;
    items.forEach(([v, k], i) => {
      ctx.textAlign = 'left';
      ctx.textBaseline = 'alphabetic';
      ctx.fillStyle = c.ink;
      ctx.font = `700 64px ${FONT_B}`;
      ctx.fillText(v, x + col * i, y);
      ctx.fillStyle = c.ink2;
      ctx.font = `400 28px ${FONT_B}`;
      ctx.fillText(k, x + col * i, y + 44);
    });
  }
  function heatStrip(ctx, x, y, w, d, c, weeks = 20, gap = 6) {
    const cell = Math.floor((w - gap * (weeks - 1)) / weeks);
    const mon = addDays(d.today, -weekday(d.today) - 7 * (weeks - 1));
    const level = (m) => (m <= 0 ? 0 : m < d.goal / 2 ? 1 : m < d.goal ? 2 : m < d.goal * 2 ? 3 : 4);
    for (let wk = 0; wk < weeks; wk++) {
      for (let r = 0; r < 7; r++) {
        const k = addDays(mon, wk * 7 + r);
        if (k > d.today) continue;
        ctx.fillStyle = c.g[level(d.byDay.get(k) || 0)];
        ctx.beginPath();
        ctx.roundRect(x + wk * (cell + gap), y + r * (cell + gap), cell, cell, Math.min(6, cell / 4));
        ctx.fill();
      }
    }
    return 7 * (cell + gap);
  }

  // a pond as big as fits in the box, centered in it
  async function fitPond(ctx, scene, x, y, w, h, people = null) {
    await Art.ready(scene);
    const pw = Math.min(w, (h * scene.width) / scene.height), ph = (scene.height * pw) / scene.width;
    Art.drawPond(ctx, scene, x + (w - pw) / 2, y + (h - ph) / 2, pw, people);
  }

  async function makeCard(kind, opts = {}) {
    await Promise.all([fontsReady(), Art.loadSprites()]);
    const W = 1080, H = 1350;
    const canvas = document.createElement('canvas');
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext('2d');
    const c = themeColors();
    const d = derive();
    paper(ctx, W, H, c);
    const dateText = fmtDate(d.today, { month: 'long', day: 'numeric', year: 'numeric' });
    if (kind === 'stats') {
      const { rank } = rankFor(d.total);
      cardHeader(ctx, W, c, dateText);
      ctx.textAlign = 'left';
      ctx.textBaseline = 'alphabetic';
      ctx.fillStyle = c.ink2;
      ctx.font = `400 32px ${FONT_B}`;
      ctx.fillText(S.settings.name ? `${S.settings.name}'s study pond` : 'My study pond', 72, 236);
      ctx.fillStyle = c.ink;
      ctx.font = `600 60px ${FONT_D}`;
      const rankText = `${rank[1]} ${rank[2]}`;
      ctx.fillText(rankText, 72, 312);
      const rw = ctx.measureText(rankText).width;
      ctx.fillStyle = c.ink2;
      ctx.font = `400 30px ${FONT_B}`;
      ctx.fillText(rank[3], 72 + rw + 18, 312);
      seal(ctx, W - 72 - 150, 186, 150, rank[1], c.accent, -0.07);
      ctx.fillStyle = c.ink;
      ctx.font = `700 150px ${FONT_B}`;
      const hrs = fmtHours(d.total);
      ctx.fillText(hrs, 66, 476);
      const hw = ctx.measureText(hrs).width;
      ctx.fillStyle = c.ink2;
      ctx.font = `500 42px ${FONT_B}`;
      ctx.fillText('hours of focus', 66 + hw + 18, 476);
      statCols(ctx, 72, 572, W - 144, [[d.trees.toLocaleString(), d.trees === 1 ? 'duck hatched' : 'ducks hatched'], [String(d.streak), 'day streak'], [String(d.best), 'best streak']], c);
      const recent = d.list.filter((s) => s._day > addDays(d.today, -30));
      const scene = Art.pond((recent.length ? recent : d.list.slice(-40)).map((s) => ({ kind: s.species, cold: s.status === 'withered' })), { seed: 'card' + d.today, max: 120, minAspect: 0.4, maxAspect: 0.4, ...pondOpts(S.settings.pondTheme) });
      await fitPond(ctx, scene, 72, 642, W - 144, 374);
      ctx.fillStyle = c.ink2;
      ctx.font = `400 26px ${FONT_B}`;
      ctx.textAlign = 'left';
      ctx.fillText('Every day, the last 44 weeks', 72, 1062);
      heatStrip(ctx, 72, 1076, W - 144, d, c, 44, 4);
      cardFooter(ctx, W, H, c);
    } else if (kind === 'year') {
      const y = yearData(d);
      cardHeader(ctx, W, c, S.settings.name || dateText);
      ctx.textAlign = 'left';
      ctx.textBaseline = 'alphabetic';
      ctx.fillStyle = c.ink;
      ctx.font = `600 66px ${FONT_D}`;
      ctx.fillText(`My ${y.year} in ducks`, 72, 250);
      ctx.fillStyle = c.ink2;
      ctx.font = `400 32px ${FONT_B}`;
      ctx.fillText(`${fmtDate(`${y.year}-01-01`, { month: 'short', day: 'numeric' })} – ${fmtDate(d.today, { month: 'short', day: 'numeric' })}`, 72, 300);
      ctx.fillStyle = c.ink;
      ctx.font = `700 130px ${FONT_B}`;
      const hrs = fmtHours(y.minutes);
      ctx.fillText(hrs, 66, 448);
      const hw = ctx.measureText(hrs).width;
      ctx.fillStyle = c.ink2;
      ctx.font = `500 40px ${FONT_B}`;
      ctx.fillText('hours of focus', 66 + hw + 18, 448);
      statCols(ctx, 72, 540, W - 144, [[y.ducks.toLocaleString(), y.ducks === 1 ? 'duck hatched' : 'ducks hatched'], [String(y.days), y.days === 1 ? 'day studied' : 'days studied'],
        [y.best >= 0 ? y.monthName(y.best, 'short') : '–', 'best month']], c);
      const scene = Art.pond(y.list.map((s) => ({ kind: s.species, cold: s.status === 'withered' })), { seed: 'year' + y.year, max: 300, minAspect: 0.42, maxAspect: 0.42, ...pondOpts(S.settings.pondTheme) });
      await fitPond(ctx, scene, 72, 620, W - 144, 360);
      // a bar for each month, in the theme's colors
      const top = Math.max(60, ...y.months), bx = 72, by = 1010, bh = 120, band = (W - 144) / 12, bw = band - 18, now = +d.today.slice(5, 7) - 1;
      y.months.forEach((v, i) => {
        const h = (bh * v) / top;
        ctx.fillStyle = i === now ? c.accent : c.leaf;
        if (h > 0) { ctx.beginPath(); ctx.roundRect(bx + band * i + 9, by + bh - h, bw, h, [Math.min(8, bw / 2, h), Math.min(8, bw / 2, h), 0, 0]); ctx.fill(); }
        ctx.fillStyle = c.ink3;
        ctx.font = `400 22px ${FONT_B}`;
        ctx.textAlign = 'center';
        ctx.fillText(y.monthName(i, 'narrow'), bx + band * i + band / 2, by + bh + 32);
      });
      ctx.fillStyle = c.line;
      ctx.fillRect(bx, by + bh, W - 144, 2);
      const duck = y.duck && Art.KINDS[y.duck[0]];
      ctx.fillStyle = c.ink2;
      ctx.font = `400 28px ${FONT_B}`;
      ctx.textAlign = 'left';
      ctx.fillText([duck ? `Most hatched: ${duck.kanji} ${duck.name}` : '', y.tag ? `Top tag: ${y.tag[0]}` : ''].filter(Boolean).join(' · '), 72, 1210);
      cardFooter(ctx, W, H, c);
    } else if (kind === 'forest') {
      const b = rangeBounds(S.range, S.rangeOffset);
      const list = inRange(b);
      const grown = list.filter((s) => s.status !== 'withered');
      const minutes = grown.reduce((n, s) => n + s.minutes, 0);
      cardHeader(ctx, W, c, S.settings.name || dateText);
      ctx.textAlign = 'left';
      ctx.textBaseline = 'alphabetic';
      ctx.fillStyle = c.ink;
      ctx.font = `600 66px ${FONT_D}`;
      const title = { day: 'Today\u2019s ducks', week: 'This week\u2019s ducks', month: 'This month\u2019s ducks', year: 'This year\u2019s ducks' }[S.range];
      ctx.fillText(S.rangeOffset === 0 ? title : `My pond · ${b.label}`, 72, 250);
      ctx.fillStyle = c.ink2;
      ctx.font = `400 32px ${FONT_B}`;
      ctx.fillText(b.sub || b.label, 72, 300);
      // the pond fills the space between the title and the numbers
      const scene = Art.pond(list.map((s) => ({ kind: s.species, cold: s.status === 'withered' })), { seed: S.range + b.from, max: 500, maxAspect: 0.72, ...pondOpts(S.settings.pondTheme) });
      await fitPond(ctx, scene, 72, 344, W - 144, 680);
      const byTag = new Map();
      for (const s of grown) byTag.set(s.tag || 'Untagged', (byTag.get(s.tag || 'Untagged') || 0) + s.minutes);
      const top = [...byTag.entries()].sort((a, b2) => b2[1] - a[1])[0];
      statCols(ctx, 72, 1100, W - 144, [[minutes >= 60 ? `${fmtHours(minutes)}h` : `${minutes}m`, 'focused'], [grown.length.toLocaleString(), grown.length === 1 ? 'duck' : 'ducks'], [top ? `${Math.round((top[1] / Math.max(1, minutes)) * 100)}%` : '–', top ? top[0] : 'no tags yet']], c);
      cardFooter(ctx, W, H, c);
    } else if (kind === 'group') {
      const data = S.groupData[S.groupId];
      const who = peopleMap(data.people);
      cardHeader(ctx, W, c, dateText);
      ctx.textAlign = 'left';
      ctx.textBaseline = 'alphabetic';
      ctx.fillStyle = c.ink;
      ctx.font = `600 66px ${FONT_D}`;
      ctx.fillText(data.group.name, 72, 250);
      ctx.fillStyle = c.ink2;
      ctx.font = `400 32px ${FONT_B}`;
      ctx.fillText(`${{ week: 'This week', month: 'This month', all: 'All our ducks' }[S.groupRange]} · ${data.people.map((p) => p.name).join(', ')}`, 72, 300);
      const list = data.pond.filter((x) => inGroupRange(x, S.groupRange)).sort((a, b2) => a.start - b2.start);
      const scene = Art.pond(list.map((x) => ({ kind: x.species, cold: x.status === 'withered', person: x.person })),
        { seed: data.group.id + S.groupRange, max: 500, maxAspect: 0.72, ...pondOpts(data.group.theme || S.settings.pondTheme) });
      await fitPond(ctx, scene, 72, 344, W - 144, 680, who);
      const done = list.filter((x) => x.status !== 'withered'), minutes = done.reduce((n, x) => n + x.minutes, 0);
      statCols(ctx, 72, 1100, W - 144, [[minutes >= 60 ? `${fmtHours(minutes)}h` : `${minutes}m`, 'studied together'],
        [String(new Set(list.map((x) => x.room || x.id)).size), 'sessions'], [done.length.toLocaleString(), done.length === 1 ? 'duck' : 'ducks']], c);
      cardFooter(ctx, W, H, c);
    } else {
      const s = opts.session;
      const info = Art.KINDS[Art.kindOf(s.species)];
      cardHeader(ctx, W, c, dateText);
      const base = 760;
      const g = ctx.createRadialGradient(W / 2, base - 220, 30, W / 2, base - 220, 380);
      g.addColorStop(0, c.surface);
      g.addColorStop(1, c.bg);
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(W / 2, base - 220, 380, 0, Math.PI * 2);
      ctx.fill();
      // a little round pond, drawn like the ducks: flat water and a soft dark outline (the duck
      // brings its own ripples), with room around them for a couple of lily pads
      const blobFill = (cx, cy, rx, ry, fill, outline = true) => {
        ctx.beginPath();
        ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
        ctx.fillStyle = fill;
        ctx.fill();
        if (outline) { ctx.lineWidth = 5; ctx.strokeStyle = Art.INK; ctx.stroke(); }
      };
      blobFill(W / 2, base, 380, 104, Art.WATER.top);
      blobFill(W / 2 - 318, base + 22, 36, 14, '#9CC48C');
      blobFill(W / 2 + 316, base - 26, 28, 10, '#9CC48C');
      blobFill(W / 2 + 309, base - 32, 9, 6, '#F2A5C0');
      const size = 560;
      Art.drawDuck(ctx, s.species, W / 2 - size / 2, base - 1.12 * size, size, false, true);
      ctx.textAlign = 'center';
      ctx.textBaseline = 'alphabetic';
      ctx.fillStyle = c.accent;
      ctx.font = `700 92px ${FONT_D}`;
      ctx.fillText('誕生', W / 2, 1000);
      ctx.fillStyle = c.ink;
      ctx.font = `500 48px ${FONT_B}`;
      ctx.fillText(`+${fmtMin(s.minutes)}${s.tag ? ` · ${s.tag}` : ''}`, W / 2, 1080);
      ctx.fillStyle = c.ink2;
      ctx.font = `400 32px ${FONT_B}`;
      const byDay = new Map(d.byDay);
      if (!S.sessions.has(s.id)) byDay.set(dayKey(s.start), (byDay.get(dayKey(s.start)) || 0) + s.minutes);
      const todayMin = byDay.get(d.today) || 0;
      ctx.fillText(`${info.kanji} ${info.name} · ${todayMin}/${d.goal} min today · ${streaks(byDay, d.goal, d.today).current}-day streak`, W / 2, 1140);
      cardFooter(ctx, W, H, c);
    }
    return canvas;
  }

  let shareFile = null;
  async function share(kind, opts) {
    toast('Drawing your picture…', 1400);
    try {
      const canvas = await makeCard(kind, opts);
      const blob = await new Promise((r) => canvas.toBlob(r, 'image/png'));
      const name = `dakku-${kind}-${todayKey()}.png`;
      shareFile = new File([blob], name, { type: 'image/png' });
      const url = URL.createObjectURL(blob);
      const img = $('#share-img');
      if (img.dataset.url) URL.revokeObjectURL(img.dataset.url);
      img.src = url;
      img.dataset.url = url;
      const dl = $('#share-download');
      dl.href = url;
      dl.download = name;
      const canShare = !!(navigator.canShare && navigator.canShare({ files: [shareFile] }));
      $('#share-go').hidden = !canShare;
      $('#share-hint').textContent = canShare ? 'Share it to Messages, Instagram, or save it to Photos.' : 'Long-press the image to save it, or download it.';
      $('#share-dialog').showModal();
    } catch (err) {
      toast(`Couldn't draw it: ${err.message}`);
    }
  }

  /* ───────────── theme ───────────── */
  // An event is a theme and a pond together. Turning one on remembers your own, to go back to.
  function pickEvent(id) {
    const s = S.settings, on = s.theme === id && s.pondTheme === id;
    if (on) {
      const back = store.get(K.beforeEvent, null) || { theme: 'ai', pondTheme: 'classic' };
      saveSettings({ theme: back.theme, pondTheme: back.pondTheme });
      toast(`${PONDS[id][1]} is off. Your own colors and pond are back.`);
      return;
    }
    if (!EVENTS.some(([e]) => e === s.theme)) store.set(K.beforeEvent, { theme: s.theme, pondTheme: s.pondTheme || 'classic' });
    saveSettings({ theme: id, pondTheme: id });
    toast(`${PONDS[id][1]} is on. Tap it again to go back.`);
  }
  // what drifts down behind everything: petals for Sakura (in the page already), bats, leaves or snow
  // for the events. Made once per theme, from a seed, so it looks the same every time.
  function paintDrift(theme) {
    const host = $('.petals');
    if (!host) return;
    host.dataset.sakura ||= host.innerHTML;
    if (host.dataset.for === theme) return;
    host.dataset.for = theme;
    const r = Art.rng('drift' + theme), n = { halloween: 9, thanksgiving: 16, christmas: 34 }[theme], r1 = (v) => Math.round(v * 10) / 10;
    if (!n) { host.innerHTML = theme === 'sakura' ? host.dataset.sakura : ''; return; }
    let html = '';
    for (let i = 0; i < n; i++) {
      const x = r1(r() * 100), d = r1((theme === 'christmas' ? 14 : theme === 'halloween' ? 22 : 16) + r() * 14), w = r1(-r() * 30);
      const v = theme === 'thanksgiving' ? ` data-v="${i % 3}"` : theme === 'christmas' ? ` style="--x:${x}%;--d:${d}s;--w:${w}s;--s:${r1(4 + r() * 6)}px;--o:${r1(0.35 + r() * 0.5)}"` : '';
      html += theme === 'christmas' ? `<i${v}></i>` : `<i style="--x:${x}%;--y:${r1(8 + r() * 60)}vh;--d:${d}s;--w:${w}s"${v}></i>`;
    }
    if (theme === 'christmas') html += '<b style="--x:22%;--d:31s;--w:-6s">❄</b><b style="--x:58%;--d:36s;--w:-20s">❄</b><b style="--x:84%;--d:33s;--w:-12s">✦</b>';
    host.innerHTML = html;
  }
  function applyTheme() {
    const pref = S.settings?.theme || store.get(K.theme, 'ai');
    const theme = THEMES.some((t) => t[0] === pref) ? pref : 'ai';
    document.documentElement.dataset.theme = theme;
    paintDrift(theme);
    store.set(K.theme, pref);
    const bg = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim();
    $('meta[name="theme-color"]').setAttribute('content', bg || '#F2EDE3');
  }

  /* ───────────── sign in / out ───────────── */
  function showGate(id) {
    for (const g of ['gate', 'join-gate', 'unreachable', 'app']) $(`#${g}`).hidden = g !== id;
    const splash = $('#boot');
    if (splash && !splash.classList.contains('gone')) {
      splash.classList.add('gone');
      setTimeout(() => splash.remove(), 400);
    }
  }
  function signedOut() {
    disconnectLive();
    S.settings = null;
    store.del(K.cache);
    store.del(K.timer);
    if (joinCode()) { showJoin(); return; }
    showGate('gate');
    const iOS = /iP(hone|ad|od)/.test(navigator.userAgent);
    const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone;
    $('#gate-tip').hidden = !(iOS && !standalone);
    paintGate();
    setTimeout(() => $('#login-code').focus(), 50);
  }
  // at the friends' door there's no passcode: say what to do instead
  async function paintGate() {
    let me = null;
    try { me = await api('GET', '/api/whoami'); } catch { /* unreachable: keep the usual words */ }
    const door = !!me?.public;
    $('#gate-friend').hidden = !door;
    $('#gate-help').hidden = door;
    $('#login-label').textContent = door ? 'Code from your other device' : 'Passcode or pairing code';
    $('#login-code').placeholder = door ? '6 digits' : 'five words, or 6 digits';
  }

  // an invite link: …/join#code. The code waits here until it's used.
  function joinCode() {
    if (location.pathname.replace(/\/+$/, '') === '/join' && location.hash.length > 8) store.set(K.join, location.hash.slice(1));
    return store.get(K.join, '');
  }
  function forgetJoin() {
    store.del(K.join);
    if (location.pathname !== '/') history.replaceState(null, '', '/#together');
  }
  async function showJoin() {
    showGate('join-gate');
    const code = joinCode();
    let color = PALETTE[Math.floor(Math.random() * PALETTE.length)][0];
    const paint = () => {
      const name = $('#join-name').value.trim();
      $('#join-badge').textContent = name ? name[0].toUpperCase() : '?';
      $('#join-badge').style.setProperty('--c', color);
      $('#join-colors').innerHTML = PALETTE.map(([light, , kanji, nm]) => `<button type="button" style="--c:${light}" data-jcolor="${light}" title="${kanji} ${nm}" aria-label="${nm}" aria-pressed="${light === color}"></button>`).join('');
    };
    paint();
    $('#join-name').oninput = paint;
    $('#join-colors').onclick = (e) => { const b = e.target.closest('[data-jcolor]'); if (b) { color = b.dataset.jcolor; paint(); } };
    try {
      const peek = await api('POST', '/api/invite', { code });
      $('#join-title').textContent = peek.forPerson ? `Welcome back, ${peek.forPerson}` : peek.from ? `${peek.from} invited you` : "You're invited";
      $('#join-lede').textContent = peek.forPerson ? 'This link signs this device in to your Dakku pond.'
        : `Study together${peek.group ? ` in ${peek.group}` : ''}${peek.people.length > 1 ? ` with ${peek.people.join(', ')}` : ''}. Every focus session hatches a little duck, and you can join each other's sessions as they run.`;
      $('#join-form').querySelectorAll('label, input, .join-look, p.muted').forEach((el) => { el.hidden = !!peek.forPerson; });
      $('#join-btn').textContent = peek.forPerson ? 'Sign in' : 'Join';
      $('#join-name').required = !peek.forPerson;
    } catch (err) {
      $('#join-title').textContent = 'This invite has run out';
      $('#join-lede').textContent = err instanceof Offline ? "Dakku can't be reached right now. Try again in a moment." : err.message;
      $('#join-form').hidden = true;
      if (!(err instanceof Offline)) store.del(K.join);
    }
    $('#join-form').onsubmit = async (e) => {
      e.preventDefault();
      $('#join-btn').disabled = true;
      $('#join-msg').textContent = '';
      try {
        await api('POST', '/api/join', { code, name: $('#join-name').value.trim(), color, mark: $('#join-name').value.trim()[0]?.toUpperCase() || '' });
        forgetJoin();
        await start();
        location.hash = '#together';
      } catch (err) {
        $('#join-msg').textContent = err instanceof Offline ? "Dakku can't be reached right now." : err.message;
      } finally {
        $('#join-btn').disabled = false;
      }
    };
  }
  // already signed in here (say, a friend opening a second invite): just join the group
  async function useJoinCode() {
    const code = joinCode();
    if (!code) return;
    try {
      await api('POST', '/api/join', { code });
      toast('You joined the group.');
      await refreshTogetherNow();
      location.hash = '#together';
    } catch (err) { if (!(err instanceof Offline)) toast(err.message); }
    forgetJoin();
  }
  async function login(code) {
    const msg = $('#login-msg');
    msg.textContent = '';
    $('#login-btn').disabled = true;
    try {
      await api('POST', '/api/login', { passcode: code });
      $('#login-code').value = '';
      await start();
    } catch (err) {
      msg.textContent = err instanceof Offline ? "Can't reach your PC right now. Is Tailscale on?" : err.message;
    } finally {
      $('#login-btn').disabled = false;
    }
  }

  /* ───────────── events ───────────── */
  function wire() {
    window.addEventListener('hashchange', route);
    $('#login-form').addEventListener('submit', (e) => { e.preventDefault(); login($('#login-code').value); });
    $('#retry-btn').addEventListener('click', async () => { $('#retry-msg').textContent = 'Trying…'; await start(); $('#retry-msg').textContent = S.settings ? '' : 'Still no answer.'; });
    $('#sync').addEventListener('click', () => { flush(); pull(); toast(S.reachable ? 'Syncing…' : "Your PC can't be reached. Changes wait here until it can.", 1800); });
    $('#sync-now').addEventListener('click', () => { flush(); pull(); });

    // plant
    setupDial();
    $('#mode-seg').addEventListener('click', (e) => {
      const b = e.target.closest('[data-mode]');
      if (!b || S.timer) return;
      S.pick.mode = b.dataset.mode;
      renderPlantControls();
      paintTimer();
      savePick();
    });
    $('#pomo-pick').addEventListener('click', (e) => {
      const b = e.target.closest('[data-pomo]');
      if (!b || S.timer) return;
      const [low, high, step] = POMO_LIMITS[b.dataset.pomo];
      const p = { ...S.pick.pomo };
      p[b.dataset.pomo] = clamp(p[b.dataset.pomo] + step * +b.dataset.step, low, high);
      S.pick.pomo = p;
      renderPlantControls();
      paintTimer();
      savePickSoon();
    });
    $('#undo-btn').addEventListener('click', () => {
      const t = S.timer;
      if (!t || !undoLeft(t)) return;
      if (t.local) { finishLocalAction(t, 'cancel', serverNow(), { undo: true }); return; }
      timerAction('cancel', { undo: true });
    });
    $('#presets').addEventListener('click', (e) => {
      const b = e.target.closest('[data-min]');
      if (!b) return;
      S.pick.minutes = +b.dataset.min;
      markPresets();
      paintTimer();
      savePick();
    });
    $('#tag-chips').addEventListener('click', async (e) => {
      if (e.target.closest('[data-tag-add]')) {
        location.hash = '#settings';
        setTimeout(() => { $('#new-tag').focus(); $('#new-tag').scrollIntoView({ block: 'center' }); }, 120);
        return;
      }
      const b = e.target.closest('[data-tag]');
      if (!b) return;
      S.pick.tag = b.dataset.tag;
      $$('#tag-chips [data-tag]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      savePick();
    });
    $('#species-row').addEventListener('click', (e) => {
      if (e.target.closest('[data-sp-all]')) { openDucks('pick'); return; }
      const b = e.target.closest('[data-sp]');
      if (!b || b.disabled) return;
      if (b.dataset.sp === 'random') saveSettings({ randomSpecies: !S.settings.randomSpecies }, { quiet: true });
      else {
        S.pick.species = b.dataset.sp;
        if (S.settings.randomSpecies) saveSettings({ randomSpecies: false }, { quiet: true });
        savePick();
      }
      renderPlantControls();
      paintTimer();
    });
    $('#gallery-btn').addEventListener('click', () => openDucks('gallery'));
    $('#collection').addEventListener('click', (e) => { const b = e.target.closest('[data-duck]'); if (b) openDucks('gallery', b.dataset.duck); });
    $('#ducks-close').addEventListener('click', () => $('#ducks-dialog').close());
    $('#ducks-dialog').addEventListener('click', (e) => {
      if (e.target === e.currentTarget) { e.currentTarget.close(); return; } // outside the sheet
      const chosen = e.target.closest('[data-pick]');
      if (chosen) { chooseDuck(chosen.dataset.pick); return; }
      const hatchWith = e.target.closest('[data-hatch-with]');
      if (hatchWith) { chooseDuck(hatchWith.dataset.hatchWith); location.hash = '#hatch'; return; }
      const duck = e.target.closest('[data-duck]');
      if (duck) { showDuck(duck.dataset.duck); return; }
      if (e.target.closest('[data-back]')) { $('#duck-detail').hidden = true; $('#duck-grid').hidden = false; }
    });
    $('#plant-btn').addEventListener('click', startTimer);
    $('#open-sessions').addEventListener('change', (e) => { saveSettings({ openSessions: e.target.checked }, { quiet: true }); });
    document.addEventListener('click', (e) => { const j = e.target.closest('[data-join]'); if (j && !j.disabled) openJoin(j.dataset.join); });
    document.addEventListener('click', (e) => { const c = e.target.closest('[data-cheer]'); if (c) openCheer(c.dataset.cheer); });
    $('#cheer-picks').addEventListener('click', (e) => { const b = e.target.closest('[data-cheer-text]'); if (b) sendCheer(b.dataset.cheerText); });
    $('#cheer-form').addEventListener('submit', (e) => { e.preventDefault(); sendCheer($('#cheer-text').value); });
    $('#cheer-cancel').addEventListener('click', () => $('#cheer-dialog').close());
    $('#pause-btn').addEventListener('click', () => { unlockAudio(); timerAction(S.timer?.runFrom == null ? 'resume' : 'pause'); });
    $('#finish-btn').addEventListener('click', async () => {
      const t = S.timer;
      if (!t) return;
      const m = Math.round(elapsedOf(t) / MIN);
      if (t.mode === 'room') {
        if (await confirmBox('Leave now?', m >= 1 ? `Your duck hatches now, for the ${fmtMin(m)} you studied. ${nameOf(t.host)} keeps going.` : 'It has been under a minute, so nothing will be logged.', 'Leave')) timerAction('finish');
        return;
      }
      if (t.mode === 'timer' && elapsedOf(t) < t.planned - 30_000) {
        if (!(await confirmBox('Finish early?', m >= 1 ? `This logs ${fmtMin(m)} now and hatches your duck early.` : 'It has been under a minute, so nothing will be logged.', 'Finish'))) return;
      }
      if (t.mode === 'pomo' && elapsedOf(t) < t.planned - 30_000) {
        const f = Math.round(pomoFocus(t, elapsedOf(t)) / MIN), r = pomoRounds(t, elapsedOf(t));
        if (!(await confirmBox('Finish now?', f >= 1 ? `Your duck hatches now, for the ${fmtMin(f)} you focused${r ? ` (${r} of ${t.pomo.rounds} rounds)` : ''}. Breaks don't count.` : 'You haven\'t focused for a minute yet, so nothing will be logged.', 'Finish'))) return;
      }
      timerAction('finish');
    });
    $('#giveup-btn').addEventListener('click', async () => {
      if (!S.timer) return;
      if (S.timer.mode === 'room') {
        if (await confirmBox('Give up this egg?', `It goes cold, and ${nameOf(S.timer.host)} keeps going. To keep a duck for the time you studied, tap Leave instead.`, 'Give up')) timerAction('cancel');
        return;
      }
      if (await confirmBox('Give up this egg?', 'It goes cold. Cold eggs stay in your pond but don\'t count toward your goal.', 'Give up')) timerAction('cancel');
    });
    $('#done-close').addEventListener('click', () => { $('#done').hidden = true; });
    $('#done').addEventListener('click', (e) => { if (e.target.id === 'done') $('#done').hidden = true; });
    $('#done-again').addEventListener('click', () => { $('#done').hidden = true; location.hash = '#hatch'; route(); });
    $('#done-share').addEventListener('click', () => { if (lastDone) share('session', { session: lastDone }); });

    // pond
    $('#range-seg').addEventListener('click', (e) => { const b = e.target.closest('[data-range]'); if (!b) return; S.range = b.dataset.range; S.rangeOffset = 0; renderForest(); });
    $('#range-prev').addEventListener('click', () => { S.rangeOffset--; renderForest(); });
    $('#range-next').addEventListener('click', () => { if (S.rangeOffset < 0) { S.rangeOffset++; renderForest(); } });
    $('#forest-stage').addEventListener('click', forestHit);
    document.addEventListener('scroll', hidePop, { passive: true });
    $('#forest-share').addEventListener('click', () => share('forest'));

    // together
    $('#group-chips').addEventListener('click', (e) => { const b = e.target.closest('[data-group]'); if (!b) return; S.groupId = b.dataset.group; renderTogether(); });
    $('#group-range').addEventListener('click', (e) => { const b = e.target.closest('[data-grange]'); if (!b || !S.groupData[S.groupId]) return; S.groupRange = b.dataset.grange; renderGroup(S.groupData[S.groupId]); });
    $('#board-range').addEventListener('click', (e) => { const b = e.target.closest('[data-brange]'); if (!b || !S.groupData[S.groupId]) return; S.boardRange = b.dataset.brange; renderGroup(S.groupData[S.groupId]); });
    $('#group-stage').addEventListener('click', groupHit);
    document.addEventListener('click', (e) => { if (!e.target.closest('#group-stage') && !e.target.closest('#forest-stage')) hidePop(); });
    $('#group-share').addEventListener('click', () => { if (S.groupData[S.groupId]) share('group'); });
    $('#view-together').addEventListener('click', async (e) => {
      const a = e.target.closest('[data-act]');
      if (a) { handleAct(a.dataset.act); return; }
      const leave = e.target.closest('[data-leave]');
      if (leave) {
        if (!(await confirmBox('Leave this group?', 'Your ducks stay in its pond, but you won\'t see the group or its live sessions any more.', 'Leave'))) return;
        try { await api('DELETE', `/api/groups/${leave.dataset.leave}/members/${myId()}`); S.groupData = {}; await refreshTogetherNow(); } catch (err) { toast(err.message); }
        return;
      }
      const out = e.target.closest('[data-unmember]');
      if (out) {
        if (!(await confirmBox(`Take ${nameOf(out.dataset.unmember)} out of this group?`, 'Their ducks stay in its pond.', 'Remove'))) return;
        try { await api('DELETE', `/api/groups/${S.groupId}/members/${out.dataset.unmember}`); S.groupData = {}; await refreshTogetherNow(); } catch (err) { toast(err.message); }
      }
    });
    $('#join-dialog').addEventListener('click', (e) => {
      const sp = e.target.closest('[data-jsp]');
      if (sp) { S.joinPick.species = sp.dataset.jsp; paintJoinPick(); return; }
      const tg = e.target.closest('[data-jtag]');
      if (tg) { S.joinPick.tag = tg.dataset.jtag; paintJoinPick(); }
    });
    $('#join-room-form').addEventListener('submit', (e) => { e.preventDefault(); joinRoom(); });
    $('#join-room-cancel').addEventListener('click', () => $('#join-dialog').close());
    $('#invite-close').addEventListener('click', () => $('#invite-dialog').close());

    // a mouse wheel over a row that scrolls sideways (tags, ducks) scrolls it, until it reaches its end
    document.addEventListener('wheel', (e) => {
      if (e.ctrlKey || Math.abs(e.deltaX) >= Math.abs(e.deltaY)) return;
      const row = e.target.closest?.('.chips.scroll, .species-row');
      const max = row ? row.scrollWidth - row.clientWidth : 0;
      if (max <= 0 || (e.deltaY < 0 && row.scrollLeft <= 0) || (e.deltaY > 0 && row.scrollLeft >= max - 1)) return;
      row.scrollLeft += e.deltaY * (e.deltaMode === 1 ? 16 : 1);
      e.preventDefault();
    }, { passive: false });

    // stats
    $('#stats-share').addEventListener('click', () => share('stats'));
    $('#year-share').addEventListener('click', () => share('year'));
    $('#bars-seg').addEventListener('click', (e) => { const b = e.target.closest('[data-n]'); if (!b) return; S.barsN = +b.dataset.n; renderStats(); });
    $('#view-stats').addEventListener('click', (e) => {
      const t = e.target.closest('.table-toggle');
      if (!t) return;
      const card = t.closest('.card');
      card.classList.toggle('show-table');
      t.textContent = card.classList.contains('show-table') ? 'Chart' : 'Table';
    });
    $('#anki-refresh').addEventListener('click', async () => {
      try { S.anki = await api('GET', '/api/anki?refresh=1', undefined, { timeout: 20_000 }); saveCache(); renderAnki(); toast(S.anki.live ? 'Anki numbers updated.' : "Anki isn't open on your PC."); }
      catch (err) { toast(err instanceof Offline ? "Your PC can't be reached." : err.message); }
    });

    // log
    $('#log-add').addEventListener('click', () => openSession(null));
    $('#log-more').addEventListener('click', () => { S.logDays += 30; renderLog(); });
    $('#log-filter').addEventListener('click', (e) => { const b = e.target.closest('[data-log-tag]'); if (!b) return; S.logTag = b.dataset.logTag; renderLog(); });
    document.addEventListener('click', (e) => { const row = e.target.closest('[data-edit]'); if (row) openSession(row.dataset.edit); });
    $('#session-form').addEventListener('submit', saveSession);
    $('#f-cancel').addEventListener('click', () => $('#session-dialog').close());
    $('#f-delete').addEventListener('click', deleteSession);
    // a new entry ends now unless you pick its time yourself
    const followNow = () => {
      const dlg = $('#session-dialog');
      if (dlg.dataset.id || dlg.dataset.timeSet) return;
      const p = parts(Date.now() - (Math.round(+$('#f-min').value) || 0) * MIN);
      $('#f-date').value = `${p.year}-${p.month}-${p.day}`;
      $('#f-time').value = `${p.hour === '24' ? '00' : p.hour}:${p.minute}`;
    };
    $('#f-quick').addEventListener('click', (e) => { const b = e.target.closest('[data-m]'); if (b) { $('#f-min').value = b.dataset.m; followNow(); } });
    $('#f-min').addEventListener('input', followNow);
    for (const id of ['#f-date', '#f-time']) $(id).addEventListener('input', () => { $('#session-dialog').dataset.timeSet = '1'; });

    // settings
    $('#set-name').addEventListener('change', (e) => saveSettings({ name: e.target.value.trim().slice(0, 40) }, { quiet: true }));
    $('#set-goal').addEventListener('change', (e) => saveSettings({ goal: clamp(Math.round(+e.target.value || 30), 5, 600) }));
    $('#view-settings').addEventListener('click', async (e) => {
      const step = e.target.closest('[data-step]');
      if (step) { saveSettings({ goal: clamp(S.settings.goal + +step.dataset.step, 5, 600) }); return; }
      const pd = e.target.closest('[data-preset-del]');
      if (pd) { if (S.settings.presets.length > 1) saveSettings({ presets: S.settings.presets.filter((m) => m !== +pd.dataset.presetDel) }); return; }
      if (e.target.closest('[data-preset-add]')) {
        const v = prompt('Minutes for a new quick pick (1–300):', '50');
        const m = Math.round(+v);
        if (m >= 1 && m <= 300) saveSettings({ presets: [...new Set([...S.settings.presets, m])].sort((a, b) => a - b).slice(0, 6) });
        return;
      }
      const tc = e.target.closest('[data-tag-color]');
      if (tc) { const pal = $(`[data-palette="${tc.dataset.tagColor}"]`); pal.hidden = !pal.hidden; return; }
      const pick = e.target.closest('[data-pick-color]');
      if (pick) {
        const i = +pick.closest('[data-palette]').dataset.palette;
        saveSettings({ tags: S.settings.tags.map((t, j) => (j === i ? { ...t, color: pick.dataset.pickColor } : t)) });
        return;
      }
      const td = e.target.closest('[data-tag-del]');
      if (td) {
        const tag = S.settings.tags[+td.dataset.tagDel];
        if (await confirmBox(`Remove “${tag.name}”?`, 'Sessions keep their tag; it just leaves your quick list.', 'Remove')) {
          saveSettings({ tags: S.settings.tags.filter((_, j) => j !== +td.dataset.tagDel), ...(S.settings.tag === tag.name ? { tag: '' } : {}) });
          if (S.pick.tag === tag.name) S.pick.tag = '';
        }
        return;
      }
      const th = e.target.closest('[data-theme-pick]');
      if (th) { saveSettings({ theme: th.dataset.themePick }); return; }
      const pond = e.target.closest('[data-pond-pick]');
      if (pond) { saveSettings({ pondTheme: pond.dataset.pondPick }); return; }
      const deco = e.target.closest('[data-decor]');
      if (deco) {
        const on = new Set(S.settings.decor || []);
        if (on.has(deco.dataset.decor)) on.delete(deco.dataset.decor); else on.add(deco.dataset.decor);
        saveSettings({ decor: DECOR.map(([id]) => id).filter((id) => on.has(id)) });
        return;
      }
      const ev = e.target.closest('[data-event]');
      if (ev) { pickEvent(ev.dataset.event); return; }
      const pc = e.target.closest('[data-pcolor]');
      if (pc) { updateMe({ color: pc.dataset.pcolor }); return; }
      if (await peopleAdminClick(e)) return;
      const act = e.target.closest('[data-act]');
      if (act) handleAct(act.dataset.act);
      const ren = e.target.closest('[data-dev-rename]');
      if (ren) {
        const dev = S.devices.find((x) => x.id === ren.dataset.devRename);
        const name = prompt('Name this device:', dev?.name || '');
        if (name && name.trim()) { try { await api('PATCH', `/api/devices/${dev.id}`, { name: name.trim() }); renderDevices(true); } catch (err) { toast(err.message); } }
        return;
      }
      const rem = e.target.closest('[data-dev-remove]');
      if (rem) {
        const dev = S.devices.find((x) => x.id === rem.dataset.devRemove);
        const self = dev?.id === S.me?.device?.id;
        if (await confirmBox(`Sign out ${dev?.name || 'this device'}?`, self ? "You'll need the passcode or a pairing code to come back." : 'It will need the passcode or a pairing code to sign in again.', 'Sign out')) {
          try { await api('DELETE', `/api/devices/${dev.id}`); if (self) signedOut(); else renderDevices(true); } catch (err) { toast(err.message); }
        }
      }
    });
    $('#view-settings').addEventListener('change', async (e) => {
      if (e.target.id === 'set-mark') { updateMe({ mark: e.target.value }); return; }
      if (e.target.id === 'set-friend-alerts') { saveSettings({ friendAlerts: e.target.checked }, { quiet: true }); return; }
      if (e.target.id === 'set-cheer-alerts') { saveSettings({ cheerAlerts: e.target.checked }, { quiet: true }); return; }
      if (e.target.id === 'set-weekly-recap') { saveSettings({ weeklyRecap: e.target.checked }, { quiet: true }); return; }
      const gt = e.target.closest('[data-group-theme]');
      if (gt) {
        try { await api('PATCH', `/api/groups/${gt.dataset.groupTheme}`, { theme: gt.value }); S.groupData = {}; await refreshTogetherNow(); toast('Pond changed.'); } catch (err) { toast(err.message); }
        return;
      }
      const n = e.target.closest('[data-tag-name]');
      if (n) {
        const i = +n.dataset.tagName, name = n.value.trim().slice(0, 24), old = S.settings.tags[i].name;
        if (!name || S.settings.tags.some((t, j) => j !== i && t.name.toLowerCase() === name.toLowerCase())) { n.value = old; return; }
        saveSettings({ tags: S.settings.tags.map((t, j) => (j === i ? { ...t, name } : t)), ...(S.settings.tag === old ? { tag: name } : {}) });
        if (S.pick.tag === old) S.pick.tag = name;
      }
    });
    $('#add-tag-form').addEventListener('submit', (e) => {
      e.preventDefault();
      const name = $('#new-tag').value.trim().slice(0, 24);
      if (!name) return;
      if (S.settings.tags.some((t) => t.name.toLowerCase() === name.toLowerCase())) { toast('You already have that tag.'); return; }
      saveSettings({ tags: [...S.settings.tags, { name, color: PALETTE[S.settings.tags.length % PALETTE.length][0] }] });
      $('#new-tag').value = '';
      toast(`Added “${name}”.`);
    });
    $('#set-sound').addEventListener('change', (e) => { saveSettings({ sound: e.target.checked }, { quiet: true }); if (e.target.checked) { unlockAudio(); chime(); } });
    $('#set-awake').addEventListener('change', (e) => saveSettings({ keepAwake: e.target.checked }, { quiet: true }));
    $('#set-deep').addEventListener('change', (e) => saveSettings({ deepFocus: e.target.checked }, { quiet: true }));
    $('#set-random').addEventListener('change', (e) => saveSettings({ randomSpecies: e.target.checked }, { quiet: true }));
    $('#set-remind').addEventListener('change', (e) => saveSettings({ reminder: { ...S.settings.reminder, enabled: e.target.checked } }));
    $('#set-remind-time').addEventListener('change', (e) => { if (/^\d\d:\d\d$/.test(e.target.value)) saveSettings({ reminder: { ...S.settings.reminder, time: e.target.value } }, { quiet: true }); });
    $('#set-remind-weekdays').addEventListener('change', (e) => saveSettings({ reminder: { ...S.settings.reminder, weekdaysOnly: e.target.checked } }, { quiet: true }));
    $('#set-tz').addEventListener('change', (e) => saveSettings({ timeZone: e.target.value }));
    $('#tz-device').addEventListener('click', () => saveSettings({ timeZone: deviceZone() }));
    $('#pair-btn').addEventListener('click', openPair);
    $('#pair-close').addEventListener('click', () => $('#pair-dialog').close());
    $('#signout').addEventListener('click', async () => {
      if (!(await confirmBox('Sign out of this device?', S.outbox.length ? `${S.outbox.length} change(s) haven't synced yet; they stay on this device until you sign back in.` : "You'll need the passcode or a pairing code to come back.", 'Sign out'))) return;
      try { await api('POST', '/api/logout'); } catch { /* signed out locally anyway */ }
      signedOut();
    });
    $('#import-file').addEventListener('change', async (e) => {
      const file = e.target.files[0];
      e.target.value = '';
      if (!file) return;
      try {
        const data = JSON.parse(await file.text());
        const res = await api('POST', '/api/import', { data, since: S.cursor }, { timeout: 60_000 });
        applyPull(res);
        toast(`Imported ${plural(res.imported, 'session')}.`);
      } catch (err) { toast(err instanceof SyntaxError ? "That file isn't JSON." : err.message); }
    });
    $('#share-close').addEventListener('click', () => $('#share-dialog').close());
    $('#share-go').addEventListener('click', async () => {
      if (!shareFile) return;
      try { await navigator.share({ files: [shareFile], title: '鴨 Dakku' }); } catch (err) { if (err.name !== 'AbortError') toast(err.message); }
    });
    for (const dlg of $$('dialog.sheet')) dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.close(); });

    // the page coming and going
    document.addEventListener('visibilitychange', async () => {
      if (document.hidden) {
        noteAway();
        wakeLock(false);
        disconnectLive();
        saveCache();
      } else {
        S.swReg?.update().catch(() => {}); // pick up a new version of Dakku
        connectLive();
        await pull();
        await flush();
        checkAway();
        wakeLock(true);
        render();
      }
    });
    window.addEventListener('pagehide', () => { noteAway(); saveCache(); });
    window.addEventListener('online', () => { flush(); connectLive(); });
    matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', () => { applyTheme(); render(); });
    let resizeTimer = 0;
    window.addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { if (S.view === 'stats') renderStats(); }, 200); });
    $('#view-plant').addEventListener('click', (e) => { const a = e.target.closest('[data-act]'); if (a) handleAct(a.dataset.act); });
  }

  // your badge: color and mark, as friends see them on your ducks
  async function updateMe(patch) {
    try {
      const person = await api('PATCH', `/api/people/${myId()}`, patch);
      S.me.person = person;
      if (S.together) S.together.people = S.together.people.map((p) => (p.id === person.id ? person : p));
      S.groupData = {};
      S.admin = null;
      saveCache();
      renderSettings();
    } catch (err) { toast(err instanceof Offline ? "Your PC can't be reached." : err.message); }
  }

  async function peopleAdminClick(e) {
    const t = (sel) => e.target.closest(sel);
    const ask = (title, text, yes) => confirmBox(title, text, yes);
    const run = async (fn) => { try { await fn(); S.groupData = {}; await refreshTogetherNow(); renderPeopleAdmin(true); } catch (err) { toast(err instanceof Offline ? "Your PC can't be reached." : err.message); } };
    let el;
    if ((el = t('[data-invite-group]'))) {
      const g = S.admin?.groups.find((x) => x.id === el.dataset.inviteGroup);
      openInvite({ group: g.id }, `Invite someone to ${g.name}`, 'They open this on their phone or computer, pick a name, and they\'re in: no Tailscale or app needed.');
    } else if ((el = t('[data-rename-group]'))) {
      const g = S.admin?.groups.find((x) => x.id === el.dataset.renameGroup);
      const name = await askText('Rename the group', '', 'Group name', g?.name || '', 'Rename');
      if (name) await run(() => api('PATCH', `/api/groups/${g.id}`, { name }));
    } else if ((el = t('[data-delete-group]'))) {
      const g = S.admin?.groups.find((x) => x.id === el.dataset.deleteGroup);
      if (await ask(`Delete ${g?.name}?`, 'Everyone keeps their own ducks, but the group, its pond and its invites are gone.', 'Delete')) await run(() => api('DELETE', `/api/groups/${g.id}`));
    } else if ((el = t('[data-person-link]'))) {
      const who = S.admin?.people.find((x) => x.id === el.dataset.personLink);
      openInvite({ person: who.id }, `A sign-in link for ${who.name}`, `For ${who.name}'s new phone or computer: it signs that device in to their pond. It works once.`);
    } else if ((el = t('[data-person-remove]'))) {
      const who = S.admin?.people.find((x) => x.id === el.dataset.personRemove);
      if (await ask(`Remove ${who?.name}?`, 'They\'re signed out everywhere and leave every group. Ducks from sessions you did together stay in those ponds.', 'Remove')) await run(() => api('DELETE', `/api/people/${who.id}`));
    } else if ((el = t('[data-invite-revoke]'))) {
      await run(() => api('DELETE', `/api/invites/${el.dataset.inviteRevoke}`));
    } else return false;
    return true;
  }

  async function handleAct(act) {
    if (act === 'pair') openPair();
    else if (act === 'new-group') newGroup();
    else if (act === 'invite') {
      const g = S.together?.groups.find((x) => x.id === S.groupId);
      if (g) openInvite({ group: g.id }, `Invite someone to ${g.name}`, 'They open this on their phone or computer, pick a name, and they\'re in: no Tailscale or app needed.');
    }
    else if (act === 'welcomed') { store.set(K.ui, { ...store.get(K.ui, {}), welcomed: true }); renderPlantSide(); }
    else if (act === 'show-passcode') {
      if (S.passcode) { S.passcode = null; renderPasscode(); return; }
      try { S.passcode = (await api('GET', '/api/passcode')).passcode; renderPasscode(); } catch (err) { toast(err.message); }
    } else if (act === 'new-passcode') {
      if (!(await confirmBox('Make a new passcode?', 'Every other device gets signed out and needs the new passcode or a pairing code.', 'Make new'))) return;
      try { S.passcode = (await api('POST', '/api/passcode', { next: '', signOutOthers: true })).passcode; renderPasscode(); renderDevices(true); toast('New passcode made.'); } catch (err) { toast(err.message); }
    } else if (act === 'change-passcode') {
      const current = prompt('Your current passcode:');
      if (!current) return;
      try {
        const res = await api('POST', '/api/passcode', { current, next: '', signOutOthers: true });
        await confirmBox('Your new passcode', `${res.passcode}\n\nWrite it down: other devices need it to sign in again.`, 'Got it', true);
      } catch (err) { toast(err.message); }
    } else if (act === 'push-on') pushOn();
    else if (act === 'push-off') pushOff();
    else if (act === 'push-test') {
      try { await api('POST', '/api/push/test'); toast('Sent. It should arrive in a moment.'); } catch (err) { toast(err.message); }
    }
  }

  /* ───────────── start up ───────────── */
  async function start() {
    try {
      const data = await api('GET', '/api/bootstrap');
      applyBootstrap(data);
      showGate('app');
      route();
      connectLive();
      await flush();
      checkAway();
      resumeCelebration();
      useJoinCode();
    } catch (err) {
      if (err.status === 401) return signedOut();
      if (S.settings) { showGate('app'); route(); return; } // offline: keep going with what this device has
      showGate('unreachable');
    }
  }
  function resumeCelebration() {
    // an egg you started here hatched while Dakku was closed
    for (const id of store.get(K.mine, []).slice(0, 3)) {
      const s = S.sessions.get(id);
      if (s && !seen(id) && s.status === 'done' && Date.now() - (s.start + s.minutes * MIN) < 6 * HOUR) { celebrate(s); break; }
      if (s) markSeen(id);
    }
  }

  function registerWorker() {
    if (!('serviceWorker' in navigator)) return;
    const secure = location.protocol === 'https:' || ['localhost', '127.0.0.1'].includes(location.hostname);
    if (!secure) return;
    const hadController = !!navigator.serviceWorker.controller;
    navigator.serviceWorker.register('/sw.js').then((reg) => { S.swReg = reg; reg.update().catch(() => {}); }).catch(() => {});
    let reloaded = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (!hadController || reloaded || S.dragging) return;
      reloaded = true;
      location.reload(); // a new version of Dakku arrived
    });
  }

  function loadFonts() {
    // added from here rather than in the page, so a slow or blocked Google never holds up opening Dakku
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@500;600;700&family=Zen+Kaku+Gothic+New:wght@400;500;700&family=Zen+Maru+Gothic:wght@500;700&display=swap';
    document.head.appendChild(link);
  }

  function boot() {
    loadFonts();
    applyTheme();
    // ChatGPT's paintings replace the drawn placeholders as they arrive (drawn again at most every quarter second)
    let repaint = 0;
    const paintIn = () => { repaint ||= setTimeout(() => { repaint = 0; lastGrowKey = ''; render(); }, 250); };
    Art.loadSprites(paintIn).then((ok) => { if (ok) paintIn(); });
    wire();
    registerWorker();
    const cached = store.get(K.cache, null);
    if (cached?.settings) {
      loadCache(cached);
      showGate('app');
      route();
    }
    start();
    setInterval(() => {
      tickTimer();
      if (S.timer && S.view === 'plant' && !document.hidden) paintTimer();
      else if (S.timer) paintTitle();
    }, 250);
    // the clocks on friends' sessions
    setInterval(() => {
      if (document.hidden) return;
      for (const el of $$('[data-ends]')) el.textContent = fmtClock(Math.max(0, +el.dataset.ends - serverNow()));
    }, 1000);
    setInterval(() => {
      if (!S.settings || document.hidden) return;
      if (D && D.today !== todayKey()) render();
      if (!S.live) pull();
      if (S.outbox.length) flush();
      paintSync();
    }, 30_000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
