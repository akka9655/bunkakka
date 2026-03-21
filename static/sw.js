const CACHE_NAME = 'bunker-cache-v6';
const STATIC_ASSETS = [
    '/',
    '/static/style.css?v=1.0.0',
    '/static/app.js?v=1.1.0',
    '/static/legal.js?v=1.0.1',
    '/manifest.json?v=bunker5',
    '/static/icon.png',
    '/static/icon-192.png',
    '/static/icon-512.png',
    '/static/favicon.png',
    '/static/favicon.ico',
    'https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
    'https://cdn.tailwindcss.com',
    'https://cdnjs.cloudflare.com/ajax/libs/animejs/3.2.1/anime.min.js'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS);
        }).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const requestUrl = new URL(event.request.url);

    // Skip API calls from cache
    if (requestUrl.pathname.startsWith('/api/')) {
        event.respondWith(fetch(event.request));
        return;
    }

    // Cache First for static assets, falling back to network
    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            if (cachedResponse) {
                return cachedResponse;
            }
            return fetch(event.request).then((networkResponse) => {
                // If the response is valid, cache it
                if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') {
                    return networkResponse;
                }
                const responseToCache = networkResponse.clone();
                caches.open(CACHE_NAME).then((cache) => {
                    cache.put(event.request, responseToCache);
                });
                return networkResponse;
            });
        }).catch(() => {
            // Offline fallback 
            if (event.request.mode === 'navigate') {
                return caches.match('/');
            }
        })
    );
});
