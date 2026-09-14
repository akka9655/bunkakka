const CACHE_NAME = 'bunker-cache-v22';

// Precache application shell assets (cached 100% on device for 0ms loads & 0 origin transfer)
const PRECACHE_ASSETS = [
    '/',
    '/calendar',
    '/static/style.css?v=3.5.2',
    '/static/app.js?v=3.6.1',
    '/static/calendar.css?v=3.5.0',
    '/static/calendar.js?v=3.5.0',
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

    // 1. API calls: ALWAYS network, never cache UI shell
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(event.request).catch(() => new Response(
                JSON.stringify({ error: 'Offline. Please check your connection.' }),
                { headers: { 'Content-Type': 'application/json' } }
            ))
        );
        return;
    }

    // 2. Only intercept own origin requests.
    // Let browser native cache & network handle third-party CDNs (Tailwind, cdnjs, Google Fonts)
    // without risky service worker opaque caching or invalid response errors.
    if (url.origin !== self.location.origin) {
        return;
    }

    // 3. Navigation requests: Cache-first for Instant App Shell (0ms, 0 Vercel function calls)
    if (event.request.mode === 'navigate' || url.pathname === '/' || url.pathname === '/calendar' || url.pathname === '/index.html' || url.pathname === '/calendar.html') {
        const targetPath = (url.pathname === '/calendar' || url.pathname === '/calendar.html') ? '/calendar' : '/';
        event.respondWith(
            caches.match(targetPath).then(cached => {
                if (cached) return cached;
                return fetch(event.request).then(res => {
                    if (res && res.status === 200) {
                        const clone = res.clone();
                        caches.open(CACHE_NAME).then(c => c.put(targetPath, clone));
                    }
                    return res;
                }).catch(() => caches.match('/'));
            })
        );
        return;
    }

    // 4. Own static assets (CSS, JS, images, icons): Pure Cache-First
    event.respondWith(
        caches.match(event.request).then(cached => {
            if (cached) return cached;
            return fetch(event.request).then(res => {
                if (res && res.status === 200) {
                    const clone = res.clone();
                    caches.open(CACHE_NAME).then(c => c.put(event.request, clone));
                }
                return res;
            });
        })
    );
});
