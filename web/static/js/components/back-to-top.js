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
            requestAnimationFrame(() => btn.classList.add('visible'));
        } else {
            btn.classList.remove('visible');
            setTimeout(() => { if (!shown) btn.hidden = true; }, 220);
        }
    };

    window.addEventListener('scroll', update, { passive: true });
    btn.addEventListener('click', () => {
        const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        window.scrollTo({ top: 0, behavior: prefersReduced ? 'auto' : 'smooth' });
    });
    update();
}

