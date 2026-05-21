// === components/back-to-top.js ===
function initBackToTop() {
    const btn = document.getElementById('backToTop');
    if (!btn) return;
    const threshold = 400;
    let shown = false;

    const update = () => {
        const y = window.scrollY || document.documentElement.scrollTop;
        const shouldShow = y > threshold;
        if (shouldShow === shown) return;
        shown = shouldShow;
        if (shouldShow) {
            btn.hidden = false;
            // Defer one frame so the .visible transition triggers from
            // hidden=>visible state.
            requestAnimationFrame(() => btn.classList.add('visible'));
        } else {
            btn.classList.remove('visible');
            // Match CSS transition duration for the fade-out before hiding
            // the element entirely (so it's removed from focus order).
            setTimeout(() => { if (!shown) btn.hidden = true; }, 220);
        }
    };

    window.addEventListener('scroll', update, { passive: true });
    btn.addEventListener('click', () => {
        if (typeof trackEvent === 'function') {
            const doc = document.documentElement;
            const y = window.scrollY || doc.scrollTop;
            const total = Math.max(doc.scrollHeight - window.innerHeight, 1);
            const scroll_pct = Math.max(0, Math.min(100, Math.round((y / total) * 100)));
            trackEvent('back-to-top-clicado', { scroll_pct });
        }
        const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        window.scrollTo({ top: 0, behavior: prefersReduced ? 'auto' : 'smooth' });
    });
    update();
}

