// === lib/scroll-deep.js ===
// Dispara evento Umami `scroll-deep` quando user atinge marcos de scroll:
// 50%, 75%, 100%. Mede engagement real — diferencia "abriu e saiu" de
// "leu o relatorio inteiro".
//
// Props enviadas:
//   percent : 50 | 75 | 100  (number, marco atingido)
//   pagina  : 'cidade' | 'empresa' | 'empresa-municipio' | 'caso' | 'home' |
//             'mapa' | 'sobre' | 'glossario' | 'outro'
//
// Cada marco eh disparado UMA UNICA VEZ por page load (deduplicado).
// Scroll usa requestAnimationFrame throttle pra nao spam-track.

function _scrollDeepPageKind() {
    const p = window.location.pathname;
    if (p.startsWith('/cidade/')) return 'cidade';
    if (p.startsWith('/empresa/') && p.split('/').length >= 4) return 'empresa-municipio';
    if (p.startsWith('/empresa/')) return 'empresa';
    if (p.startsWith('/caso/')) return 'caso';
    if (p === '/' || p === '/index') return 'home';
    if (p === '/mapa') return 'mapa';
    if (p === '/sobre') return 'sobre';
    if (p === '/glossario') return 'glossario';
    return 'outro';
}

function initScrollDeep() {
    const pagina = _scrollDeepPageKind();
    if (pagina === 'outro') return;
    const fired = new Set();
    let ticking = false;
    const onScroll = () => {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(() => {
            ticking = false;
            const doc = document.documentElement;
            const scrolled = (window.scrollY || window.pageYOffset || 0) + window.innerHeight;
            const total = Math.max(doc.scrollHeight, doc.offsetHeight, 1);
            const pct = (scrolled / total) * 100;
            [50, 75, 100].forEach(mark => {
                if (!fired.has(mark) && pct >= mark) {
                    fired.add(mark);
                    if (typeof trackEvent === 'function') {
                        trackEvent('scroll-deep', { percent: mark, pagina });
                    }
                }
            });
        });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
}
