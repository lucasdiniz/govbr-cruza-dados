// TransparenciaPB service worker.
// Strategy:
//  - Static assets (/static/*): stale-while-revalidate with cache fallback.
//  - HTML/navigation: network-first with cache fallback (so user can navigate recently visited
//    pages offline). Avoids serving stale interactive data when online.
//  - API/tudo mais: network only (nao cacheia dados, que podem mudar).
//
// Bump CACHE_VERSION para invalidar caches antigos.

const CACHE_VERSION = 'tpb-v38';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const PAGES_CACHE = `${CACHE_VERSION}-pages`;

const CORE_ASSETS = [
    '/static/css/index.css',
    '/static/js/pages/main.js',
    '/static/js/pages/mapa.js',
    '/static/js/graph-animation.js',
    '/static/js/md3/imports.js',
    '/static/vendor/material-web/material-web-bundle.js',
    '/static/vendor/leaflet/leaflet.css',
    '/static/vendor/leaflet/leaflet.js',
    '/static/vendor/leaflet/images/marker-icon.png',
    '/static/vendor/leaflet/images/marker-icon-2x.png',
    '/static/vendor/leaflet/images/marker-shadow.png',
    '/static/logo-nego.png',
    '/static/favicon.ico',
    '/static/icon-32.png',
    '/static/icon-192.png',
    '/static/manifest.webmanifest',
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(STATIC_CACHE).then((cache) =>
            cache.addAll(CORE_ASSETS).catch(() => null)
        ).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys.filter((k) => !k.startsWith(CACHE_VERSION)).map((k) => caches.delete(k))
            )
        ).then(() => self.clients.claim())
    );
});

function isStaticAsset(url) {
    return url.pathname.startsWith('/static/');
}

function isNavigation(request) {
    return request.mode === 'navigate' ||
        (request.method === 'GET' && request.headers.get('accept')?.includes('text/html'));
}

self.addEventListener('fetch', (event) => {
    const { request } = event;
    if (request.method !== 'GET') return;

    const url = new URL(request.url);
    if (url.origin !== self.location.origin) return;

    if (isStaticAsset(url)) {
        event.respondWith(staleWhileRevalidate(request, STATIC_CACHE));
        return;
    }

    if (isNavigation(request)) {
        event.respondWith(networkFirst(request, PAGES_CACHE));
        return;
    }
});

async function staleWhileRevalidate(request, cacheName) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);
    const network = fetch(request).then((res) => {
        if (res && res.status === 200) cache.put(request, res.clone()).catch(() => null);
        return res;
    }).catch(() => null);
    return cached || network || new Response('', { status: 504 });
}

async function networkFirst(request, cacheName) {
    const cache = await caches.open(cacheName);
    try {
        const res = await fetch(request);
        if (res && res.status === 200) cache.put(request, res.clone()).catch(() => null);
        return res;
    } catch {
        const cached = await cache.match(request);
        if (cached) return cached;
        return new Response('<h1>Sem conexao</h1><p>Tente novamente quando estiver online.</p>', {
            status: 503,
            headers: { 'Content-Type': 'text/html; charset=utf-8' }
        });
    }
}
