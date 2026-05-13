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
            const total = Math.max(doc.scrollHeight, doc.offsetHeight, 1);
            // Skip paginas que cabem inteiras na viewport — sem scroll real
            // possivel, qualquer disparo de 50/75/100% seria espurio e
            // poluiria a metrica de engagement (objetivo: distinguir
            // abriu-e-saiu de leu-inteiro). 1.2x da viewport eh o
            // threshold pra exigir conteudo significativo abaixo da dobra.
            if (total <= window.innerHeight * 1.2) return;
            const scrolled = (window.scrollY || window.pageYOffset || 0) + window.innerHeight;
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
    // Nao chamamos onScroll() no init — exigimos pelo menos UMA rolada
    // pra evitar disparar 50/75/100 em paginas com scroll mas user
    // chegou ja perto do final via deep-link/anchor.
}
