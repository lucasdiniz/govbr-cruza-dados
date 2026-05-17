// TransparenciaPB service worker.
// Strategy:
//  - Static assets (/static/*): stale-while-revalidate with cache fallback.
//  - HTML/navigation: network-first with cache fallback (so user can navigate recently visited
//    pages offline). Avoids serving stale interactive data when online.
//  - API/tudo mais: network only (nao cacheia dados, que podem mudar).
//
// CACHE_VERSION é derivado de /static/dist/manifest.json (asset hash) — auto-bump por deploy.
// Fallback estatico (FALLBACK_CACHE_VERSION) é usado quando manifest indisponível
// (dev mode sem build, ou race no deploy).

const FALLBACK_CACHE_VERSION = 'tpb-v47-fallback';

// Lista mínima usada APENAS quando manifest.json não pode ser fetched.
// Mantém PWA instalável mesmo em deploy race / 404 transitorio.
const FALLBACK_CORE_ASSETS = [
    '/static/logo-nego.png',
    '/static/favicon.ico',
    '/static/icon-32.png',
    '/static/icon-192.png',
    '/static/manifest.webmanifest',
];

// Resolve manifest no install: pega cache_version e core assets hashed.
async function resolveCoreAssets() {
    try {
        const res = await fetch('/static/dist/manifest.json', {
            cache: 'no-store',
            credentials: 'same-origin',
        });
        if (!res.ok) throw new Error(`manifest fetch ${res.status}`);
        const manifest = await res.json();
        const cacheVersion = manifest.__cache_version__ || FALLBACK_CACHE_VERSION;
        const hashedAssets = [];
        for (const key of ['core.js', 'mapa.js', 'index.css']) {
            const file = manifest[key];
            if (file) hashedAssets.push(`/static/dist/${file}`);
        }
        return {
            cacheVersion,
            assets: [
                ...hashedAssets,
                '/static/js/md3/imports.js',
                '/static/vendor/material-web/material-web-bundle.js',
                '/static/vendor/leaflet/leaflet.css',
                '/static/vendor/leaflet/leaflet.js',
                '/static/vendor/leaflet/images/marker-icon.png',
                '/static/vendor/leaflet/images/marker-icon-2x.png',
                '/static/vendor/leaflet/images/marker-shadow.png',
                ...FALLBACK_CORE_ASSETS,
            ],
        };
    } catch (e) {
        console.warn('[sw] manifest fetch failed, using fallback', e);
        return {
            cacheVersion: FALLBACK_CACHE_VERSION,
            assets: FALLBACK_CORE_ASSETS,
        };
    }
}

self.addEventListener('install', (event) => {
    event.waitUntil((async () => {
        const { cacheVersion, assets } = await resolveCoreAssets();
        const staticCache = `${cacheVersion}-static`;
        // Persistimos cache_version pra activate/fetch usarem o mesmo nome.
        self.__currentCacheVersion = cacheVersion;
        try {
            const cache = await caches.open(staticCache);
            // Cada asset individualmente: se um falhar, os outros ainda
            // entram no cache (cache.addAll é all-or-nothing).
            await Promise.all(assets.map((url) =>
                cache.add(new Request(url, { cache: 'reload' })).catch(() => null)
            ));
        } catch (e) {
            console.warn('[sw] install cache failed', e);
        }
        await self.skipWaiting();
    })());
});

self.addEventListener('activate', (event) => {
    event.waitUntil((async () => {
        // Re-resolve manifest pra detectar cache_version atual (caso o SW
        // tenha sido reativado sem install novo, ex: navegador reabriu).
        let cacheVersion = self.__currentCacheVersion;
        let resolvedFromManifest = !!cacheVersion;
        if (!cacheVersion) {
            try {
                const resolved = await resolveCoreAssets();
                cacheVersion = resolved.cacheVersion;
                self.__currentCacheVersion = cacheVersion;
                // Sucesso so se a versao retornada NAO eh o fallback estatico.
                // Se for fallback, o fetch do manifest provavelmente falhou e
                // nao queremos purgar caches validos com nome diferente.
                resolvedFromManifest = cacheVersion !== FALLBACK_CACHE_VERSION;
            } catch {
                resolvedFromManifest = false;
            }
        }
        // Cleanup so quando temos certeza da versao atual (manifest fetched
        // OK ou install setou). Network-fail no activate NAO purga caches —
        // isso evita wipe acidental do cache hashed valido quando o user
        // reabre offline ou em rede flaky.
        if (resolvedFromManifest && cacheVersion) {
            const keys = await caches.keys();
            await Promise.all(keys.filter((k) => !k.startsWith(cacheVersion)).map((k) => caches.delete(k)));
        }
        await self.clients.claim();
    })());
});

function getStaticCacheName() {
    return `${self.__currentCacheVersion || FALLBACK_CACHE_VERSION}-static`;
}

function getPagesCacheName() {
    return `${self.__currentCacheVersion || FALLBACK_CACHE_VERSION}-pages`;
}

function isStaticAsset(url) {
    return url.pathname.startsWith('/static/');
}

function isManifest(url) {
    return url.pathname === '/static/dist/manifest.json';
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

    // Manifest sempre network-first (sem cache estavel) — é o ponto de
    // verdade pra invalidação.
    if (isManifest(url)) return;

    if (isStaticAsset(url)) {
        event.respondWith(staleWhileRevalidate(request, getStaticCacheName()));
        return;
    }

    if (isNavigation(request)) {
        event.respondWith(networkFirst(request, getPagesCacheName()));
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
