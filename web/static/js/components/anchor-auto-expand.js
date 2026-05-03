// === components/anchor-auto-expand.js ===
function initAnchorAutoExpand() {
    // Qualquer clique em <a href="#X"> dentro da pagina, OU navegacao por hashchange,
    // expande o report-section/finding-card de destino antes de scrollar. Cobre
    // KPI strip, narrativa, links inline e back/forward do navegador.
    const handleHash = (hash, ev) => {
        if (!hash || hash === '#') return;
        const target = document.getElementById(hash.slice(1));
        if (!target) return;
        if (ev) ev.preventDefault();
        expandReportContext(target);
        _scrollAndFlash(target);
        history.replaceState(null, '', hash);
    };
    document.addEventListener('click', (e) => {
        const link = e.target.closest('a[href^="#"]');
        if (!link) return;
        // Ignora links que sao apenas "#" ou estao dentro de modais que tratam navegacao propria
        const href = link.getAttribute('href');
        if (!href || href === '#') return;
        // Nao interceptar dropdowns/abas/etc que usam href="#" como hook
        if (link.dataset.skipAnchorExpand === 'true') return;
        handleHash(href, e);
    });
    // Carga inicial com hash na URL
    if (window.location.hash) {
        // Dar um tick para o DOM estar pronto e finding-cards carregadas
        setTimeout(() => handleHash(window.location.hash, null), 80);
    }
    window.addEventListener('hashchange', () => handleHash(window.location.hash, null));
}


