/* 鴨 Dakku — service worker: opens the app without a connection, and shows notifications.
   The server stamps BUILD with a fingerprint of the app's files, so any update installs itself. */
'use strict';

const BUILD = '__BUILD__';
const CACHE = `dakku-${BUILD}`;
const FONTS = 'dakku-fonts';
const PICTURES = 'dakku-pictures'; // kept through updates: 70-odd pictures are slow to fetch again over the internet
// (the Home Screen icons aren't here: they're only fetched when Dakku is added to one, and that's online)
const SHELL = ['/', '/app.css', '/app.js', '/art.js', '/kinds.js', '/qr.js', '/lofi.js', '/manifest.webmanifest', '/icons/favicon.png'];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(SHELL.map((url) => new Request(url, { cache: 'no-cache' })));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    // the pictures and fonts saved before Dakku had its name ("mori-…") are kept: they're slow to fetch again
    for (const [from, to] of [['mori-pictures', PICTURES], ['mori-fonts', FONTS]]) {
      if (!(await caches.has(from))) continue;
      const old = await caches.open(from), kept = await caches.open(to);
      for (const req of await old.keys()) if (!(await kept.match(req))) await kept.put(req, await old.match(req));
    }
    for (const key of await caches.keys()) if (![CACHE, FONTS, PICTURES].includes(key)) await caches.delete(key);
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin === self.location.origin) {
    if (url.pathname.startsWith('/api/')) return; // your data always comes live from the PC
    if (url.pathname.startsWith('/ducks/') && url.searchParams.has('v')) event.respondWith(picture(req));
    else event.respondWith(req.mode === 'navigate' ? page(req) : asset(req, event));
  } else if (url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com') {
    event.respondWith(font(req));
  }
});

function withTimeout(promise, ms) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('timeout')), ms);
    promise.then((v) => { clearTimeout(timer); resolve(v); }, (e) => { clearTimeout(timer); reject(e); });
  });
}

// the page: fresh when the PC answers quickly, otherwise the copy saved last time
async function page(req) {
  const cache = await caches.open(CACHE);
  try {
    const res = await withTimeout(fetch(req), 4000);
    if (res.ok) cache.put('/', res.clone());
    return res;
  } catch {
    return (await cache.match('/')) || Response.error();
  }
}

// scripts, styles, icons and the list of pictures: straight from the saved copy, refreshed in the background
async function asset(req, event) {
  const list = new URL(req.url).pathname === '/ducks/ducks.json';
  const cache = await caches.open(list ? PICTURES : CACHE);
  const hit = await cache.match(req, { ignoreSearch: true });
  const fresh = fetch(req).then((res) => {
    if (res.ok) {
      cache.put(req, res.clone());
      if (list) event.waitUntil(forget(res.clone()));
    }
    return res;
  }).catch(() => null);
  return hit || (await fresh) || Response.error();
}

// a picture: its address ends in its version (?v=), so a saved one is never out of date and is kept
// as it is; nothing is asked of the PC for it again
async function picture(req) {
  const cache = await caches.open(PICTURES);
  const hit = await cache.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok) cache.put(req, res.clone());
  return res;
}

// the saved pictures the list no longer has (an old version of one, a duck that's gone)
async function forget(listRes) {
  const keep = new Set((await listRes.text()).match(/\/ducks\/[^"]+/g) || []);
  const cache = await caches.open(PICTURES);
  for (const req of await cache.keys()) {
    const url = new URL(req.url);
    if (url.pathname !== '/ducks/ducks.json' && !keep.has(url.pathname + url.search)) await cache.delete(req);
  }
}

async function font(req) {
  const cache = await caches.open(FONTS);
  const hit = await cache.match(req);
  if (hit) return hit;
  try {
    const res = await fetch(req);
    if (res.ok || res.type === 'opaque') cache.put(req, res.clone());
    return res;
  } catch {
    return Response.error();
  }
}

self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch { data = { body: event.data ? event.data.text() : '' }; }
  // iPhone requires every push to show a notification right away
  event.waitUntil(self.registration.showNotification(data.title || '鴨 Dakku', {
    body: data.body || '',
    tag: data.tag || 'dakku',
    renotify: true,
    icon: '/icons/icon-192.png',
    data: { url: data.url || '/' },
  }));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = new URL(event.notification.data?.url || '/', self.location.origin).href;
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const win of windows) {
      if (new URL(win.url).origin === self.location.origin && 'focus' in win) return win.focus();
    }
    return self.clients.openWindow(url);
  })());
});
