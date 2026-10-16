// DOTS · mapa del campo sin señal: guarda la página y las imágenes del campo en el teléfono.
const SHELL = 'campo-shell-v1', TILES = 'campo-tiles-v1';
const FILES = ['/campo', '/campo/index.html', '/campo/app.js', '/campo/campo.css', '/campo/vendor/leaflet.js', '/campo/vendor/leaflet.css', '/campo/manifest.webmanifest', '/dots-logo.svg'];
self.addEventListener('install', e => { e.waitUntil(caches.open(SHELL).then(c => c.addAll(FILES)).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => { e.waitUntil(self.clients.claim()); });
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (u.hostname.endsWith('arcgisonline.com')) {
    e.respondWith(caches.open(TILES).then(async c => (await c.match(e.request)) || fetch(e.request).then(r => { if (r.ok) c.put(e.request, r.clone()); return r; }).catch(() => new Response('', { status: 504 }))));
    return;
  }
  if (u.origin === location.origin && u.pathname.startsWith('/campo')) {
    e.respondWith(fetch(e.request).then(r => { if (r.ok && e.request.method === 'GET') caches.open(SHELL).then(c => c.put(e.request, r.clone())); return r; })
      .catch(() => caches.match(e.request, { ignoreSearch: true }).then(r => r || caches.match('/campo/index.html'))));
  }
});
