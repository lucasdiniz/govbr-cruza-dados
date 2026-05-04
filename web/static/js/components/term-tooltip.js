// === components/term-tooltip.js ===
function initTermTooltips() {
    const closeOtherTips = (active) => {
        document.querySelectorAll('.term.tip-open').forEach(el => {
            if (el !== active) el.classList.remove('tip-open');
        });
    };
    document.addEventListener('click', (e) => {
        const term = e.target.closest('.term[data-tip]');
        // Fecha abertos em outro clique
        closeOtherTips(term);
        if (term) {
            // Em touch devices, tap alterna
            if (matchMedia('(hover: none)').matches) {
                e.preventDefault();
                term.classList.toggle('tip-open');
            }
        }
    });
}

