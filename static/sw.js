// Moor Water PWA — Service Worker
// Served from root /sw.js to maintain full app scope

const CACHE_NAME = 'moor-water-v2';
const SHELL_ASSETS = [
  '/',
  '/login',
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/icon.svg',
  '/manifest.json'
];

// ── Install: pre-cache the app shell ──────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[SW] Pre-caching app shell');
        // addAll fails if ANY request fails — use individual adds with catch
        return Promise.allSettled(
          SHELL_ASSETS.map(url =>
            cache.add(url).catch(err =>
              console.warn('[SW] Could not cache:', url, err)
            )
          )
        );
      })
      .then(() => self.skipWaiting())
  );
});

// ── Activate: clean up old caches ─────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter(key => key !== CACHE_NAME)
          .map(key => {
            console.log('[SW] Removing old cache:', key);
            return caches.delete(key);
          })
      )
    ).then(() => self.clients.claim())
  );
});

// ── Fetch: routing strategy ───────────────────
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // 1. Skip non-GET requests entirely (POST, DELETE, etc.)
  if (request.method !== 'GET') return;

  // 2. Skip chrome-extension and non-http requests
  if (!url.protocol.startsWith('http')) return;

  // 3. API calls — Network only (never cache auth/ledger data)
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(request).catch(() =>
        new Response(
          JSON.stringify({ error: 'offline', message: 'No network. Data saved to device.' }),
          { headers: { 'Content-Type': 'application/json' }, status: 503 }
        )
      )
    );
    return;
  }

  // 4. Static assets — Cache first, then network update in background
  if (url.pathname.startsWith('/static/') || url.pathname === '/sw.js' || url.pathname === '/manifest.json') {
    event.respondWith(
      caches.match(request).then((cached) => {
        // Serve cached immediately, refresh in background
        const networkFetch = fetch(request).then((networkRes) => {
          if (networkRes && networkRes.status === 200) {
            const clone = networkRes.clone();
            caches.open(CACHE_NAME).then(c => c.put(request, clone));
          }
          return networkRes;
        }).catch(() => {});

        return cached || networkFetch;
      })
    );
    return;
  }

  // 5. HTML page routes — Network first, fall back to cache
  if (request.headers.get('accept') && request.headers.get('accept').includes('text/html')) {
    event.respondWith(
      fetch(request)
        .then((networkRes) => {
          // Cache fresh HTML for offline use
          if (networkRes && networkRes.status === 200) {
            const clone = networkRes.clone();
            caches.open(CACHE_NAME).then(c => c.put(request, clone));
          }
          return networkRes;
        })
        .catch(() =>
          caches.match(request)
            .then(cached => cached || caches.match('/login'))
        )
    );
    return;
  }

  // 6. Everything else — network with cache fallback
  event.respondWith(
    fetch(request).catch(() => caches.match(request))
  );
});
