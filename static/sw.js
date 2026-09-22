const CACHE_NAME = 'bunker-cache-v28';
const RUNTIME_CACHE = 'bunker-runtime-v28';

// Precache core UI application shell assets (stored 100% on device for 0ms offline loads)
const PRECACHE_ASSETS = [
    '/',
    '/calendar',
    '/feedback',
    '/static/style.css?v=3.5.6',
    '/static/app.js?v=3.6.6',
    '/static/calendar.css?v=3.5.1',
    '/static/calendar.js?v=3.5.1',
    '/static/legal.js?v=1.0.1',
    '/manifest.json?v=bunker6',
    '/static/icon.png',
    '/static/icon-192.png',
    '/static/icon-512.png',
    '/static/favicon.png',
    '/static/favicon.ico'
];

// Install: precache our own application shell immediately
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(PRECACHE_ASSETS))
            .then(() => self.skipWaiting())
            .catch(err => console.error('[SW] Precache failed:', err))
    );
});

// Activate: clean up older cache generations immediately
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME && k !== RUNTIME_CACHE).map(k => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // 1. API calls: ALWAYS network, never serve stale shell for data
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(event.request).catch(() => new Response(
                JSON.stringify({ error: 'Offline. Please check your connection.' }),
                { headers: { 'Content-Type': 'application/json' } }
            ))
        );
        return;
    }

    // 2. Third-party UI CDN assets (Tailwind, FontAwesome, Google Fonts, AnimeJS)
    // Cache on mobile device storage so all fonts, icons & styles work 100% offline & instant
    const isUiCdn = url.hostname.includes('cdn.tailwindcss.com') ||
                    url.hostname.includes('cdnjs.cloudflare.com') ||
                    url.hostname.includes('fonts.googleapis.com') ||
                    url.hostname.includes('fonts.gstatic.com') ||
                    url.hostname.includes('cdn.jsdelivr.net');

    if (isUiCdn) {
        event.respondWith(
            caches.open(RUNTIME_CACHE).then(cache => {
                return cache.match(event.request).then(cached => {
                    if (cached) return cached;
                    return fetch(event.request).then(networkRes => {
                        if (networkRes && (networkRes.status === 200 || networkRes.type === 'opaque')) {
                            cache.put(event.request, networkRes.clone());
                        }
                        return networkRes;
                    }).catch(() => cached || new Response('', { status: 408 }));
                });
            })
        );
        return;
    }

    // Only intercept own origin requests for remaining rules
    if (url.origin !== self.location.origin) {
        return;
    }

    // 3. Navigation requests: Cache-First for Instant Mobile UI Shell (0ms, 0 Vercel function calls)
    if (event.request.mode === 'navigate' || url.pathname === '/' || url.pathname === '/calendar' || url.pathname === '/feedback' || url.pathname === '/index.html' || url.pathname === '/calendar.html' || url.pathname === '/feedback.html') {
        const targetPath = (url.pathname === '/calendar' || url.pathname === '/calendar.html') ? '/calendar'
                         : (url.pathname === '/feedback' || url.pathname === '/feedback.html') ? '/feedback'
                         : '/';
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
