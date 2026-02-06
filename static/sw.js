// Cache Version - Increment this when you update CSS/JS/HTML
const CACHE_VERSION = '1.0.1';
const CACHE_NAME = `bunker-v${CACHE_VERSION}`;

const ASSETS_TO_CACHE = [
    '/',
    '/static/manifest.json',
    '/static/icon-192.png',
    '/static/icon-512.png',
    '/static/style.css',
    '/static/app.js',
    '/static/legal.js'
];

self.addEventListener('install', (event) => {
    self.skipWaiting(); // Force immediate activation
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log(`[SW] Installing cache: ${CACHE_NAME}`);
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        // Delete old caches when version changes
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        console.log(`[SW] Deleting old cache: ${cacheName}`);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => {
            console.log(`[SW] Activated: ${CACHE_NAME}`);
            return clients.claim();
        })
    );
});

self.addEventListener('fetch', (event) => {
    // Network first, fall back to cache for main page
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request).catch(() => {
                return caches.match('/');
            })
        );
        return;
    }

    // Cache first for static assets (CSS, JS, images)
    event.respondWith(
        caches.match(event.request).then((response) => {
            return response || fetch(event.request);
        })
    );
});
