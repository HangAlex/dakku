/* 鴨 Dakku — service worker: opens the app without a connection, and shows notifications.
   The server stamps BUILD with a fingerprint of the app's files, so any update installs itself. */
'use strict';

const BUILD = '__BUILD__';
const CACHE = `mori-${BUILD}`;
const FONTS = 'mori-fonts';
const SHELL = ['/', '/app.css', '/app.js', '/art.js', '/kinds.js', '/qr.js', '/lofi.js', '/manifest.webmanifest',
  '/icons/icon-192.png', '/icons/apple-touch-icon.png', '/icons/favicon.png'];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(SHELL.map((url) => new Request(url, { cache: 'no-cache' })));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) if (key !== CACHE && key !== FONTS) await caches.delete(key);
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin === self.location.origin) {
    if (url.pathname.startsWith('/api/')) return; // your data always comes live from the PC
    event.respondWith(req.mode === 'navigate' ? page(req) : asset(req));
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

// scripts, styles and icons: straight from the saved copy, refreshed in the background
async function asset(req) {
  const cache = await caches.open(CACHE);
  const hit = await cache.match(req, { ignoreSearch: true });
  const fresh = fetch(req).then((res) => {
    if (res.ok) cache.put(req, res.clone());
    return res;
  }).catch(() => null);
  return hit || (await fresh) || Response.error();
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
    tag: data.tag || 'mori',
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
