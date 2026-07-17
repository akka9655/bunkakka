const CACHE_NAME = 'bunker-cache-v11';
// Only cache assets we control (opaque CDN responses break cache.addAll)
const PRECACHE_ASSETS = [
    '/',
    '/static/style.css?v=3.4.1',
    '/static/app.js?v=3.4.2',
    '/static/legal.js?v=1.0.1',
    '/manifest.json?v=bunker6',
    '/static/icon.png',
    '/static/icon-192.png',
    '/static/icon-512.png',
    '/static/favicon.png',
    '/static/favicon.ico'
];

// Install: precache only our own assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(PRECACHE_ASSETS))
            .then(() => self.skipWaiting())
            .catch(err => console.error('[SW] Precache failed:', err))
    );
});

// Activate: clean old caches immediately
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // 1. API calls: always network, never cache
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(event.request).catch(() => new Response(
                JSON.stringify({ error: 'Offline. Please check your connection.' }),
                { headers: { 'Content-Type': 'application/json' } }
            ))
        );
        return;
    }

    // 2. CDN third-party: network-first, cache fallback (no precache — opaque safe)
    if (url.origin !== self.location.origin) {
        event.respondWith(
            caches.open(CACHE_NAME).then(cache =>
                fetch(event.request)
                    .then(res => { 
                        if (res && (res.status === 200 || res.status === 0)) {
                            cache.put(event.request, res.clone()); 
                        }
                        return res; 
                    })
                    .catch(() => cache.match(event.request))
            )
        );
        return;
    }

    // 3. Own assets: cache-first, network fallback, then offline page
    event.respondWith(
        caches.match(event.request).then(cached => {
            if (cached) {
                // Background revalidate
                fetch(event.request).then(res => {
                    if (res && res.status === 200) {
                        caches.open(CACHE_NAME).then(c => c.put(event.request, res));
                    }
                }).catch(() => {});
                return cached;
            }
            return fetch(event.request).then(res => {
                if (res && res.status === 200) {
                    const clone = res.clone();
                    caches.open(CACHE_NAME).then(c => c.put(event.request, clone));
                }
                return res;
            }).catch(() => {
                // Offline: serve root for navigation
                if (event.request.mode === 'navigate') return caches.match('/');
            });
        })
    );
});

