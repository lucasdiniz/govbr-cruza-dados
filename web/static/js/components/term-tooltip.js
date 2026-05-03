// === components/term-tooltip.js ===
function initTermTooltips() {
    const closeOtherTips = (active) => {
        document.querySelectorAll('.term.tip-open, .kpi-card-tip.tip-open').forEach(el => {
            if (el !== active) el.classList.remove('tip-open');
        });
    };
    document.addEventListener('click', (e) => {
        const term = e.target.closest('.term[data-tip], .kpi-card-tip[data-tip]');
        const isKpiTip = term && term.classList.contains('kpi-card-tip');
        // Fecha abertos em outro clique
        closeOtherTips(term);
        if (term) {
            if (isKpiTip) {
                e.preventDefault();
                e.stopPropagation();
                term.classList.toggle('tip-open');
                return;
            }
            // Em touch devices, tap alterna
            if (matchMedia('(hover: none)').matches) {
                e.preventDefault();
                term.classList.toggle('tip-open');
            }
        }
    });
    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        const term = e.target.closest('.kpi-card-tip[data-tip]');
        if (!term) return;
        e.preventDefault();
        e.stopPropagation();
        closeOtherTips(term);
        term.classList.toggle('tip-open');
    });
}

