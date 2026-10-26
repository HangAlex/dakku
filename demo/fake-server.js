/* 鴨 Dakku demo, on its own (no PC): the PC's side, worked out in your browser.
 *
 * It starts from a snapshot of the demo Dakku (snapshot.js, made by build.py) and answers the app's
 * /api calls the way mori/app.py does: timers run out and hatch, you can join Mina or Kai, sessions
 * and settings sync. The clock starts at the moment of the snapshot and runs on from your first
 * visit of the day, so the demo looks just as it did then. Your own ducks and choices are kept in
 * this browser until the next day, when it starts over.
 */
(() => {
  const SNAP = window.DAKKU_SNAPSHOT;
  const KEY = 'dakku-demo:v1';
  const MIN = 60_000, UNDO = 10_000, MAX_STOPWATCH = 240 * MIN;
  const RealDate = Date;
  const realNow = () => RealDate.now();
  const dayOf = (d = new RealDate()) => `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;

  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(KEY)); } catch { saved = null; }
  if (!saved || saved.snap !== SNAP.at || saved.day !== dayOf() || !(saved.anchor <= realNow())) {
    const keep = saved && saved.snap === SNAP.at ? { settings: saved.settings, person: saved.person, groupTheme: saved.groupTheme } : {};
    saved = { snap: SNAP.at, day: dayOf(), anchor: realNow(), sessions: {}, timer: null, ...keep };
    // a fresh start: what the app kept from last time would bring back sessions that are gone now
    try { for (const k of Object.keys(localStorage)) if (k.startsWith('mori:') && k !== 'mori:lofi' && k !== 'mori:theme') localStorage.removeItem(k); } catch { /* private mode */ }
  }
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch { /* private mode */ } };
  save();

  // the clock: the snapshot's moment, running on in real time
  const offset = SNAP.at - saved.anchor;
  const now = () => realNow() + offset;
  class DemoDate extends RealDate {
    constructor(...args) { if (args.length) super(...args); else super(realNow() + offset); }
    static now() { return realNow() + offset; }
  }
  window.Date = DemoDate;

  /* ── state ── */
  const B = SNAP.bootstrap;
  const me = { ...B.me, person: { ...B.me.person, ...(saved.person || {}) } };
  let settings = { ...B.settings, ...(saved.settings || {}) };
  const sessions = new Map(B.sessions.map((s) => [s.id, { ...s, rev: 0 }]));
  for (const s of Object.values(saved.sessions)) sessions.set(s.id, s);
  let rev = Math.max(B.cursor, ...Object.values(saved.sessions).map((s) => s.rev));
  let mine = saved.timer;
  const people = () => B.together.people.map((p) => (p.id === 'me' ? { ...p, ...me.person } : p));
  const groups = () => B.together.groups.map((g) => (saved.groupTheme !== undefined && g.id === SNAP.group.group.id ? { ...g, theme: saved.groupTheme } : g));

  // friends studying right now: their timers, as they were (one starts again when it's over)
  const friends = new Map();
  for (const r of B.together.rooms) {
    if (r.host === 'me') continue;
    const t = { id: r.id, host: r.host, mode: r.mode, startedAt: r.startedAt, acc: 0, runFrom: r.startedAt, tag: r.tag, species: r.species,
      open: r.open, pomo: r.pomo, planned: r.mode === 'pomo' ? r.pomo.rounds * r.pomo.focus + (r.pomo.rounds - 1) * r.pomo.brk : r.elapsed + r.remaining };
    friends.set(r.host, t);
  }

  const persist = () => {
    saved.settings = settings;
    saved.timer = mine;
    saved.sessions = Object.fromEntries([...sessions].filter(([, s]) => s.rev > 0));
    save();
  };
  const publicSession = (s) => { const { rev: _, person: __, ...rest } = s; return rest; };
  const newId = () => Math.random().toString(36).slice(2, 10) + Math.random().toString(36).slice(2, 6);
  const kinds = () => (window.Art?.ORDER?.length ? window.Art.ORDER : Object.keys(window.MORI_DUCKS || { shiro: 1 }));
  const speciesFor = (requested) => (kinds().includes(requested) ? requested : settings.randomSpecies ? kinds()[Math.floor(Math.random() * kinds().length)] : settings.species);

  class ApiError extends Error { constructor(status, message, extra = {}) { super(message); this.status = status; this.extra = extra; } }

  /* ── timers: the same rules as mori/app.py ── */
  function pomoPhase(t, elapsed) {
    const p = t.pomo, cycle = p.focus + p.brk;
    const e = Math.max(0, Math.min(elapsed, t.planned)), rnd = Math.floor(e / cycle), rest = e % cycle;
    if (rnd >= p.rounds) return [p.rounds, 'focus', 0];
    return rest < p.focus ? [rnd + 1, 'focus', p.focus - rest] : [rnd + 1, 'break', cycle - rest];
  }
  function pomoFocus(t, elapsed) {
    const p = t.pomo, cycle = p.focus + p.brk, e = Math.max(0, elapsed);
    return Math.min(p.rounds * p.focus, Math.floor(e / cycle) * p.focus + Math.min(e % cycle, p.focus));
  }
  const pomoRounds = (t, elapsed) => (elapsed < t.pomo.focus ? 0 : Math.min(t.pomo.rounds, Math.floor((elapsed - t.pomo.focus) / (t.pomo.focus + t.pomo.brk)) + 1));
  function view(t, at = now()) {
    if (!t) return null;
    const running = t.runFrom != null, elapsed = t.acc + (running ? at - t.runFrom : 0);
    const out = { ...t, elapsed, running, now: at, remaining: null, endsAt: null };
    if (t.mode === 'timer' || t.mode === 'pomo') {
      out.remaining = Math.max(0, t.planned - elapsed);
      out.endsAt = running ? t.runFrom + t.planned - t.acc : null;
    }
    if (t.mode === 'pomo') {
      [out.round, out.phase, out.phaseLeft] = pomoPhase(t, elapsed);
      out.focused = pomoFocus(t, elapsed);
    }
    return out;
  }
  const allTimers = () => [...friends].concat(mine ? [['me', mine]] : []);
  function party(room, host, at) {
    return allTimers().filter(([pid, t]) => (pid === host && t.id === room) || t.room === room)
      .map(([pid, t]) => ({ person: pid, species: t.species, tag: t.tag, since: t.startedAt, elapsed: view(t, at).elapsed, running: t.runFrom != null, host: pid === host }))
      .sort((a, b) => (a.host === b.host ? a.since - b.since : a.host ? -1 : 1));
  }
  function timerView(t = mine, at = now()) {
    const v = view(t, at);
    if (!v) return null;
    const host = t.host || 'me', room = t.room || t.id;
    if (t.room) { const h = friends.get(host); v.hostTimer = h && h.id === room ? view(h, at) : null; }
    v.party = party(room, host, at);
    v.cheers = [];
    return v;
  }
  function studied(t, at, hostT = t.room ? friends.get(t.host) : null) {
    const elapsed = view(t, at).elapsed;
    if (t.mode === 'pomo') return pomoFocus(t, elapsed);
    if (t.mode === 'room' && hostT && hostT.id === t.room && hostT.mode === 'pomo' && 'hostAt' in t) {
      const h = Math.min(view(hostT, at).elapsed, hostT.planned);
      return Math.max(0, pomoFocus(hostT, h) - pomoFocus(hostT, t.hostAt));
    }
    return elapsed;
  }
  function log(t, minutes, status, at, note = '', rounds = 0) {
    const s = { id: t.id, start: t.startedAt, minutes, tag: t.tag, species: t.species, status, source: t.source || 'mori', manual: false,
      note, updated: at, deleted: false, room: t.room || '', rounds, rev: ++rev };
    sessions.set(s.id, s);
    return publicSession(s);
  }
  function together(at = now()) {
    const rooms = [];
    for (const [host, t] of allTimers()) {
      if (t.room) continue;
      const here = !!mine && (mine.id === t.id || mine.room === t.id);
      if (host !== 'me' && !here && !(t.open && at - t.startedAt >= UNDO)) continue;
      const v = view(t, at);
      rooms.push({ id: t.id, host, tag: t.tag, species: t.species, mode: t.mode, startedAt: t.startedAt, remaining: v.remaining, endsAt: v.endsAt,
        running: v.running, elapsed: v.elapsed, open: !!t.open, phase: v.phase ?? null, round: v.round ?? null, phaseLeft: v.phaseLeft ?? null,
        pomo: t.pomo || null, party: party(t.id, host, at), mine: here });
    }
    return { groups: groups(), people: people(), rooms };
  }

  function timerAction(body) {
    const at = now(), action = body.action;
    let result;
    if (action === 'start') {
      if (mine) throw new ApiError(409, 'A timer is already running.', { timer: timerView() });
      const mode = ['stopwatch', 'pomo'].includes(body.mode) ? body.mode : 'timer';
      let minutes = Math.max(1, Math.min(300, Math.round(+body.minutes || settings.minutes)));
      const pomo = mode === 'pomo' ? { focus: 25, brk: 5, rounds: 4, ...(settings.pomo || {}), ...(body.pomo || {}) } : null;
      if (pomo) minutes = pomo.focus * pomo.rounds;
      let started = at;
      if (body.startedAt != null && at - 6 * 3600_000 <= body.startedAt && body.startedAt <= at) started = body.startedAt;
      let acc = 0, runFrom = started;
      if (body.elapsed != null) { acc = Math.max(0, Math.min(body.elapsed, at - started)); runFrom = body.running === false ? null : at; }
      const t = { id: /^[A-Za-z0-9_-]{4,64}$/.test(body.id || '') && !sessions.has(body.id) ? body.id : newId(), mode, planned: mode === 'timer' ? minutes * MIN : null,
        startedAt: started, acc, runFrom, tag: String(body.tag ?? settings.tag).trim().slice(0, 40), species: speciesFor(body.species || (settings.randomSpecies ? null : settings.species)),
        deep: !!body.deep, source: 'mori', device: 'Demo', updated: at, open: body.open ?? settings.openSessions !== false, announced: false };
      if (pomo) {
        t.pomo = { focus: pomo.focus * MIN, brk: pomo.brk * MIN, rounds: pomo.rounds };
        t.planned = pomo.rounds * t.pomo.focus + (pomo.rounds - 1) * t.pomo.brk;
      }
      if (mode !== 'stopwatch' && view(t, at).elapsed >= t.planned) result = { timer: null, session: log(t, minutes, 'done', at, '', pomo ? pomo.rounds : 0) };
      else { mine = t; result = { timer: view(t, at) }; }
    } else if (action === 'join') {
      if (mine) throw new ApiError(409, 'Finish your own session first.', { timer: timerView() });
      const entry = [...friends].find(([, t]) => t.id === body.room);
      if (!entry) throw new ApiError(404, 'That session has already ended.');
      const [host, hostT] = entry, gid = newId();
      mine = { id: gid, mode: 'room', planned: null, room: hostT.id, host, startedAt: at, acc: 0, runFrom: at, tag: String(body.tag ?? settings.tag).trim().slice(0, 40),
        hostAt: view(hostT, at).elapsed, announced: false, species: speciesFor(body.species || (settings.randomSpecies ? null : settings.species)),
        deep: !!body.deep, source: 'mori', device: 'Demo', updated: at };
      result = { timer: view(mine, at) };
    } else if (action === 'drop') {
      if (mine && body.id === mine.id) mine = null;
      result = { timer: null };
    } else if (['pause', 'resume', 'finish', 'cancel'].includes(action)) {
      if (!mine) throw new ApiError(409, 'No timer is running.', { timer: null });
      if (body.id && body.id !== mine.id) throw new ApiError(409, 'That timer has already ended.', { timer: timerView() });
      const t = mine;
      if (action === 'pause') { if (t.runFrom != null) Object.assign(t, { acc: t.acc + at - t.runFrom, runFrom: null, updated: at }); result = { timer: view(t, at) }; }
      else if (action === 'resume') { if (t.runFrom == null) Object.assign(t, { runFrom: at, updated: at }); result = { timer: view(t, at) }; }
      else if (action === 'finish') {
        let minutes = Math.round(studied(t, at) / MIN);
        if (t.mode === 'timer') minutes = Math.min(minutes, Math.round(t.planned / MIN));
        if (t.mode === 'pomo') minutes = Math.min(minutes, Math.round((t.pomo.focus * t.pomo.rounds) / MIN));
        minutes = Math.min(minutes, MAX_STOPWATCH / MIN);
        const rounds = t.mode === 'pomo' ? pomoRounds(t, view(t, at).elapsed) : 0;
        mine = null;
        result = { timer: null, session: minutes < 1 ? null : log(t, minutes, 'done', at, '', rounds) };
      } else {
        const v = view(t, at), s = studied(t, at);
        mine = null;
        result = v.elapsed < MIN || s < MIN || (at - t.startedAt <= UNDO + 2000 && body.undo)
          ? { timer: null, session: null }
          : { timer: null, session: log(t, Math.floor(s / MIN), 'withered', at, body.reason === 'left' ? 'Left Dakku during deep focus' : '') };
      }
    } else throw new ApiError(400, 'Unknown timer action.');
    if (result.timer) result.timer = timerView();
    persist();
    changed();
    return result;
  }

  // every second, as the PC does: timers that run out hatch, and a friend whose session is over starts another
  setInterval(() => {
    const at = now();
    let any = false;
    for (const [host, t] of friends) {
      if (view(t, at).elapsed < t.planned) continue;
      if (mine && mine.room === t.id) { hatchGuest(at, t); }
      const startedAt = at - 60_000;
      friends.set(host, { ...t, id: `${host}-live-${Math.floor(at / 60_000)}`, startedAt, runFrom: startedAt, acc: 0 });
      any = true;
    }
    if (mine && mine.room) {
      const h = friends.get(mine.host);
      if (!h || h.id !== mine.room || view(mine, at).elapsed >= MAX_STOPWATCH) { hatchGuest(at, null); any = true; }
    } else if (mine && mine.runFrom != null) {
      const t = mine, elapsed = t.acc + at - t.runFrom;
      if (t.mode === 'timer' && elapsed >= t.planned) { log(t, Math.round(t.planned / MIN), 'done', at); mine = null; any = true; }
      else if (t.mode === 'pomo' && elapsed >= t.planned) { log(t, Math.round((t.pomo.focus * t.pomo.rounds) / MIN), 'done', at, '', t.pomo.rounds); mine = null; any = true; }
      else if (t.mode === 'stopwatch' && elapsed >= MAX_STOPWATCH) { log(t, MAX_STOPWATCH / MIN, 'done', at, 'Stopped automatically after 4 hours'); mine = null; any = true; }
    }
    if (any) { persist(); changed(); }
  }, 1000);
  function hatchGuest(at, hostT) {
    const t = mine;
    const minutes = Math.min(Math.round(studied(t, at, hostT) / MIN), MAX_STOPWATCH / MIN);
    mine = null;
    if (minutes >= 1) log(t, minutes, 'done', at);
  }

  /* ── sync ── */
  function pull(since) {
    return { cursor: rev, sessions: [...sessions.values()].filter((s) => s.rev > since || since < B.cursor).map(publicSession), settings, timer: timerView(), now: now() };
  }
  function push(body) {
    const at = now();
    for (const op of body.ops || []) {
      if (op.op === 'upsert' && op.session && op.session.id) {
        const old = sessions.get(op.session.id);
        if (!old && (op.session.start == null || op.session.minutes == null)) continue;
        const s = { status: 'done', source: 'sync', manual: false, note: '', tag: '', room: '', rounds: 0, ...old, ...op.session, deleted: false, rev: ++rev };
        if (!s.species) s.species = speciesFor(null);
        sessions.set(s.id, s);
      } else if (op.op === 'delete' && sessions.has(op.id)) {
        sessions.set(op.id, { ...sessions.get(op.id), deleted: true, updated: Math.min(+op.updated || at, at + MIN), rev: ++rev });
      }
    }
    if (body.settings && typeof body.settings === 'object') putSettings(body.settings);
    persist();
    return pull(+body.since || 0);
  }
  function putSettings(patch) {
    const reminder = patch.reminder ? { ...settings.reminder, ...patch.reminder } : settings.reminder;
    settings = { ...settings, ...patch, reminder };
    if (patch.name !== undefined) me.person = { ...me.person, name: settings.name || 'You' };
    saved.person = me.person;
  }

  /* ── the group pond: the snapshot's, with the sessions you studied with a friend added ── */
  function groupView(gid) {
    if (gid !== SNAP.group.group.id) throw new ApiError(404, 'No such group.');
    const yours = [...sessions.values()].filter((s) => s.rev > 0 && s.room && !s.deleted).map((s) => ({ ...publicSession(s), person: 'me', own: s.minutes }));
    return { ...SNAP.group, group: groups()[0], people: people(), pond: [...SNAP.group.pond, ...yours] };
  }

  function route(method, path, query, body) {
    const p = path.replace(/^\/api/, '');
    if (method === 'GET') {
      if (p === '/whoami') return me;
      if (p === '/bootstrap') return { ...B, me, settings, timer: timerView(), cursor: rev, now: now(), together: together(),
        sessions: [...sessions.values()].filter((s) => !s.deleted).map(publicSession) };
      if (p === '/sync') return pull(+(query.get('since') || 0));
      if (p === '/timer') return { timer: timerView() };
      if (p === '/together') return together();
      if (p === '/anki') return SNAP.anki;
      if (p === '/devices') return { devices: [], current: 'demo' };
      if (p.startsWith('/groups/')) return groupView(decodeURIComponent(p.slice(8)));
      if (p === '/health') return { ok: true, app: 'mori', version: me.version, demo: true };
      throw new ApiError(404, 'Not found.');
    }
    if (method === 'POST' && p === '/sync') return push(body);
    if (method === 'POST' && p === '/timer') return timerAction(body);
    if (method === 'PUT' && p === '/settings') { putSettings(body.settings || body); persist(); changed(); return { settings }; }
    if (method === 'POST' && p === '/cheer') return { ok: true };
    if (method === 'PATCH' && p === '/people/me') {
      me.person = { ...me.person, ...(body.color ? { color: body.color } : {}), ...(body.mark !== undefined ? { mark: String(body.mark).replace(/\s+/g, '').slice(0, 4) || me.person.mark } : {}) };
      saved.person = me.person; persist(); changed();
      return me.person;
    }
    if (method === 'PATCH' && p.startsWith('/groups/') && 'theme' in body) { saved.groupTheme = body.theme; persist(); changed(); return groups()[0]; }
    throw new ApiError(403, "That's switched off in the demo.");
  }

  /* ── the app's line to the PC: fetch for /api, and the live updates ── */
  const realFetch = window.fetch.bind(window);
  window.fetch = async (input, init = {}) => {
    const url = new URL(typeof input === 'string' ? input : input.url, location.href);
    if (url.origin !== location.origin || !url.pathname.startsWith('/api/')) return realFetch(input, init);
    let body = {};
    try { body = init.body ? JSON.parse(init.body) : {}; } catch { body = {}; }
    await new Promise((r) => setTimeout(r, 40));
    let status = 200, data;
    try { data = route((init.method || 'GET').toUpperCase(), url.pathname, url.searchParams, body); }
    catch (err) { status = err.status || 500; data = { error: err.message, ...(err.extra || {}) }; }
    return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
  };
  const live = new Set();
  class DemoEvents {
    constructor() { this.readyState = 1; this.handlers = {}; live.add(this); setTimeout(() => this.onopen?.(), 30); }
    addEventListener(type, fn) { (this.handlers[type] ||= []).push(fn); }
    removeEventListener(type, fn) { this.handlers[type] = (this.handlers[type] || []).filter((f) => f !== fn); }
    close() { this.readyState = 2; live.delete(this); }
  }
  DemoEvents.CONNECTING = 0; DemoEvents.OPEN = 1; DemoEvents.CLOSED = 2;
  window.EventSource = DemoEvents;
  function changed() {
    setTimeout(() => {
      const data = JSON.stringify({ rev, timer: timerView(), together: true });
      for (const es of live) for (const fn of es.handlers.change || []) fn({ data });
    }, 20);
  }
})();
