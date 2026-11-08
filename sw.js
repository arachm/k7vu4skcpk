// Čeština obrazem: offline support. The app files come from the cache at once and are refreshed in the background;
// photos and fonts are kept after the first view so they also work offline.
// Version 23 (8. 11. 2026) — must match APP_VER in index.html.
const APP = 'cz-app-v23.3';
const CORE = ['./', './index.html', './speak-audio.js', './extra-audio.js', './manifest.webmanifest', './icon-v2-192.png', './icon-v2-512.png'];
self.addEventListener('install', e => {
  // fetch each file fresh (not from the browser's short-term cache); a missing file must not block the update
  e.waitUntil(caches.open(APP).then(c => Promise.all(CORE.map(u => fetch(new Request(u, { cache: 'reload' })).then(r => r.ok && c.put(u, r)).catch(() => null)))).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== APP && k !== 'cz-photos' && k !== 'cz-fonts' && k !== 'cz-state').map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin === location.origin) {
    e.respondWith(caches.open(APP).then(async c => {
      const hit = await c.match(req, { ignoreSearch: true }) || (req.mode === 'navigate' ? await c.match('./index.html') : null);
      const net = fetch(new Request(url.href, { cache: 'no-cache', credentials: 'same-origin' })).then(res => { if (res.ok) c.put(req, res.clone()); return res; }).catch(() => null);
      return hit || (await net) || new Response('Offline', { status: 503 });
    }));
    return;
  }
  const isPhoto = /(^|\.)wikimedia\.org$/.test(url.hostname) && !url.pathname.includes('/api.php');
  const isFont = /fonts\.(googleapis|gstatic)\.com$/.test(url.hostname);
  if (isPhoto || isFont) {
    e.respondWith(caches.open(isPhoto ? 'cz-photos' : 'cz-fonts').then(async c => {
      const hit = await c.match(req);
      if (hit) return hit;
      try { const res = await fetch(req); c.put(req, res.clone()); return res; } catch (err) { return Response.error(); }
    }));
  }
});

// daily reminder: Android may wake the app about once a day; remind only if today has no practice yet
self.addEventListener('periodicsync', e => {
  if (e.tag !== 'cz-remind') return;
  e.waitUntil(caches.open('cz-state').then(c => c.match('./__state')).then(r => r ? r.json() : null).then(st => {
    if (!st || !st.on) return;
    const d = new Date(), today = `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`, [h, m] = String(st.remind || '19:00').split(':').map(Number);
    if (st.last === today || d.getHours() * 60 + d.getMinutes() < h * 60 + m) return;
    return self.registration.showNotification('Čeština obrazem', { body: 'Dnes ještě nemáš češtinu. Stačí 5 minut!', icon: 'icon-v2-192.png', badge: 'icon-v2-192.png', tag: 'cz-remind' });
  }).catch(() => null));
});
self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: 'window' }).then(cs => cs.length ? cs[0].focus() : self.clients.openWindow('./')));
});
