// ADR Parts e-shop – service worker
// Nahrazuje starý katalog (cache 'adr-catalog-v1', cache-first): při aktivaci smaže všechny staré
// mezipaměti, stránky (HTML) a data.json načítá vždy ze sítě, obrázky a statické soubory
// z mezipaměti s aktualizací na pozadí. Cizí domény (Firebase, Tawk.to, CDN) neobsluhuje.
const CACHE_NAME = 'adr-eshop-v2';

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(names => Promise.all(names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  const isPage = req.mode === 'navigate' || url.pathname === '/' || url.pathname.endsWith('.html');
  if (isPage || url.pathname.endsWith('.json') || url.pathname.endsWith('sw.js')) {
    // network-first
    event.respondWith(
      fetch(req)
        .then(res => {
          if (res.ok) { const copy = res.clone(); caches.open(CACHE_NAME).then(c => c.put(req, copy)); }
          return res;
        })
        .catch(() => caches.match(req).then(r => r || caches.match('/')))
    );
    return;
  }
  // stale-while-revalidate pro obrázky a ostatní statické soubory
  event.respondWith(
    caches.open(CACHE_NAME).then(cache =>
      cache.match(req).then(cached => {
        const net = fetch(req).then(res => { if (res.ok) cache.put(req, res.clone()); return res; }).catch(() => cached);
        return cached || net;
      })
    )
  );
});
