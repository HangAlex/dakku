/* 鴨 Dakku — ♪ lofi while you study.
   Tap ♪ on the Hatch screen and a Spotify playlist plays, shuffled; tap it again to stop. Under the
   clock: the song's name, back, play/pause, skip and the volume. The songs were found on YouTube by
   scripts/lofi.py (which writes lofi.json) and play through YouTube's player, kept out of sight.
   Dakku steers that player with messages, the way YouTube's player API does inside, so no YouTube
   script runs in Dakku. */
'use strict';

(() => {
  const YT = 'https://www.youtube-nocookie.com';
  const $ = (sel) => document.querySelector(sel);
  const PLAYING = 1, ENDED = 0, LOADING = 3; // YouTube's player states (-1 not started, 2 paused, 5 ready)
  const ICON = {
    play: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.2v13.6L18.6 12z"/></svg>',
    pause: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.5 5h4v14h-4zM13.5 5h4v14h-4z"/></svg>',
  };
  const KEY = 'dakku:lofi'; // this device's volume
  // iPhones leave the volume to their own buttons (a page can't change it), so they get no slider
  const CAN_SET_VOLUME = (() => { try { const a = document.createElement('audio'); a.volume = 0.5; return a.volume === 0.5; } catch { return false; } })();
  const L = {
    songs: null,
    queue: [], at: 0,        // this time's shuffled order, and the song playing
    on: false,
    frame: null, ready: false, hello: 0,
    state: -1, time: 0,      // as the player last said
    volume: 80,
    changedAt: 0, misses: 0, missedFor: 0, // when the song last changed; songs in a row YouTube couldn't play
    note: '',
  };

  function shuffled(songs, notFirst) {
    const a = songs.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    if (a.length > 1 && a[0] === notFirst) [a[0], a[1]] = [a[1], a[0]]; // never the same song twice running
    return a;
  }

  const post = (msg) => L.frame?.contentWindow?.postMessage(JSON.stringify({ id: 1, channel: 'widget', ...msg }), YT);
  const send = (func, args = []) => post({ event: 'command', func, args });

  async function power() {
    if (L.on) { // off: the song waits, paused, for next time
      L.on = false;
      send('pauseVideo');
      tap(false);
      paint();
      return;
    }
    L.on = true;
    if (L.frame) send('playVideo');
    else if (!(await open())) L.on = false;
    paint();
  }

  async function open() {
    if (!L.songs) {
      try {
        const res = await fetch('lofi.json');
        L.songs = (await res.json()).tracks.filter((s) => /^[\w-]{11}$/.test(s.yt));
      } catch { L.songs = null; }
      if (!L.songs?.length) { L.songs = null; say("The lofi songs didn't load. Try again in a moment."); return false; }
    }
    L.queue = shuffled(L.songs);
    L.at = 0;
    L.misses = 0;
    L.state = -1;
    L.note = '';
    const f = document.createElement('iframe');
    f.title = 'Lofi player';
    f.allow = 'autoplay; encrypted-media';
    f.referrerPolicy = 'strict-origin-when-cross-origin'; // YouTube won't play for a page that doesn't say where it is
    const q = new URLSearchParams({ enablejsapi: 1, autoplay: 1, playsinline: 1, rel: 0, iv_load_policy: 3, widgetid: 1, origin: location.origin });
    f.src = `${YT}/embed/${L.queue[0].yt}?${q}`;
    f.addEventListener('load', () => { L.ready = false; listen(); });
    L.frame = f;
    L.changedAt = Date.now();
    $('#lofi-screen').replaceChildren(f);
    return true;
  }

  // the player only answers once it's been asked to, so ask until it does
  function listen() {
    clearInterval(L.hello);
    let tries = 0;
    L.hello = setInterval(() => {
      if (L.ready || !L.frame) { clearInterval(L.hello); return; }
      if (++tries > 60) { clearInterval(L.hello); L.note = "YouTube isn't answering right now."; paint(); return; }
      post({ event: 'listening' });
    }, 250);
  }

  window.addEventListener('message', (e) => {
    if (e.origin !== YT || !L.frame || e.source !== L.frame.contentWindow) return;
    let m;
    try { m = typeof e.data === 'string' ? JSON.parse(e.data) : e.data; } catch { return; }
    if (!m || typeof m !== 'object') return;
    if ((m.event === 'onReady' || m.event === 'initialDelivery') && !L.ready) {
      L.ready = true;
      send('addEventListener', ['onStateChange']);
      send('addEventListener', ['onError']);
      loudness(L.volume);
      // an iPhone won't play sound until the video itself has been tapped once: show it, just for that
      setTimeout(() => { if (L.on && L.state !== PLAYING && L.state !== LOADING) tap(true); }, 2500);
    }
    if (m.event === 'onStateChange') changed(m.info);
    else if (m.event === 'infoDelivery' && m.info) {
      if (typeof m.info.currentTime === 'number') L.time = m.info.currentTime;
      if (typeof m.info.playerState === 'number') changed(m.info.playerState);
    }
    else if (m.event === 'onError') missed();
  });

  function changed(state) {
    if (typeof state !== 'number' || state === L.state) return;
    L.state = state;
    if (state === PLAYING) {
      L.misses = 0;
      L.note = '';
      tap(false);
      if (!L.on) send('pauseVideo'); // turned off while it was still starting
    }
    if (state === ENDED && Date.now() - L.changedAt > 3000) next();
    paint();
  }

  // a song YouTube won't play here (taken down, or blocked where you are): on to the next one
  function missed() {
    if (L.missedFor === L.changedAt) return; // the same song, told twice
    L.missedFor = L.changedAt;
    if (++L.misses >= 5) { L.note = "YouTube won't play these songs right now."; paint(); return; }
    setTimeout(next, 600);
  }

  function go(at) {
    L.at = at;
    L.changedAt = Date.now();
    L.time = 0;
    send('loadVideoById', [{ videoId: L.queue[at].yt }]);
    if (!L.on) send('pauseVideo');
    paint();
  }

  function next() {
    if (!L.frame) return;
    if (L.at + 1 < L.queue.length) { go(L.at + 1); return; }
    L.queue = shuffled(L.songs, L.queue[L.at]); // through them all: a new order
    go(0);
  }

  // back: to the start of this song, or (in its first seconds) to the one before
  function back() {
    if (!L.frame) return;
    if (L.time > 4 || L.at === 0) { send('seekTo', [0, true]); L.time = 0; return; }
    go(L.at - 1);
  }

  const playing = () => L.state === PLAYING || L.state === LOADING;

  function loudness(volume, keep) {
    if (!CAN_SET_VOLUME) return;
    L.volume = volume;
    send('setVolume', [volume]);
    if (volume > 0) send('unMute');
    if (keep) try { localStorage.setItem(KEY, JSON.stringify({ volume })); } catch { /* private browsing */ }
  }

  function tap(show) {
    const p = $('#lofi-player');
    p.classList.toggle('tap', show);
    p.inert = !show; // out of sight, it's out of reach too
  }

  function say(text) {
    const el = document.createElement('div');
    el.className = 'toast';
    el.textContent = text;
    $('#toasts').appendChild(el);
    setTimeout(() => { el.classList.add('out'); setTimeout(() => el.remove(), 320); }, 3200);
  }

  function paint() {
    const btn = $('#lofi-btn');
    btn.classList.toggle('on', L.on);
    btn.setAttribute('aria-pressed', String(L.on));
    btn.title = L.on ? 'Stop the lofi' : 'Play lofi';
    $('#lofi').hidden = !L.on;
    if (!L.on || !L.queue.length) return;
    const song = L.queue[L.at];
    $('#lofi-title').textContent = song.title;
    $('#lofi-by').textContent = L.note || song.artists.join(', ');
    $('#lofi-by').classList.toggle('note', !!L.note);
    const play = $('#lofi-play'), now = playing() ? 'pause' : 'play';
    if (play.dataset.icon !== now) {
      play.dataset.icon = now;
      play.innerHTML = ICON[now];
      play.setAttribute('aria-label', now === 'pause' ? 'Pause' : 'Play');
      play.title = play.getAttribute('aria-label');
    }
  }

  function wire() {
    if (!$('#lofi-btn')) return;
    try { const v = JSON.parse(localStorage.getItem(KEY))?.volume; if (Number.isFinite(v)) L.volume = Math.max(0, Math.min(100, v)); } catch { /* none kept */ }
    const vol = $('#lofi-vol');
    vol.hidden = !CAN_SET_VOLUME;
    vol.value = L.volume;
    vol.addEventListener('input', () => loudness(+vol.value));
    vol.addEventListener('change', () => loudness(+vol.value, true));
    $('#lofi-btn').addEventListener('click', power);
    $('#lofi-play').addEventListener('click', () => send(playing() ? 'pauseVideo' : 'playVideo'));
    $('#lofi-next').addEventListener('click', () => { L.misses = 0; next(); });
    $('#lofi-prev').addEventListener('click', back);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire);
  else wire();
})();
