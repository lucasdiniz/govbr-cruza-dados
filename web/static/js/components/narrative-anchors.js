// === components/narrative-anchors.js ===
function initNarrativeAnchors() {
    // Smooth scroll + flash highlight para links da narrativa da hero
    const narr = document.querySelector('.city-narrative');
    if (!narr) return;
    narr.addEventListener('click', (e) => {
        const link = e.target.closest('a[href^="#"]');
        if (!link) return;
        const targetId = link.getAttribute('href').slice(1);
        const target = document.getElementById(targetId);
        if (!target) return;
        e.preventDefault();
        expandReportContext(target);
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        target.classList.remove('anchor-flash');
        // Force reflow para reiniciar animacao
        void target.offsetWidth;
        target.classList.add('anchor-flash');
        setTimeout(() => target.classList.remove('anchor-flash'), 1800);
        // Atualiza hash sem jumping
        history.replaceState(null, '', '#' + targetId);
    });
}

function initCityNarrativeToggle() { /* removido: resumo sempre visivel completo */ }


function initDestaques() { /* removido: substituido por initAnchorAutoExpand */ }


function _scrollAndFlash(target) {
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    target.classList.remove('anchor-flash');
    void target.offsetWidth;
    target.classList.add('anchor-flash');
    setTimeout(() => target.classList.remove('anchor-flash'), 1800);
}

