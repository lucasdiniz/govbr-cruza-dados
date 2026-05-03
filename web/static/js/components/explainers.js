// === components/explainers.js ===
function initExplainers() {
    // Fase 4: "O que isso significa?" inline. Sempre comeca fechado:
    // explicacao aberta por padrao empurra os registros para baixo em mobile.
    const buttons = document.querySelectorAll('.explainer-btn[data-explainer-target]');
    if (!buttons.length) return;
    buttons.forEach(btn => {
        const targetId = btn.dataset.explainerTarget;
        const panel = document.getElementById(targetId);
        if (!panel) return;
        const key = `explainer:${targetId}`;
        panel.hidden = true;
        btn.setAttribute('aria-expanded', 'false');
        btn.classList.remove('is-open');
        try { localStorage.removeItem(key); } catch (_) { /* quota/private mode */ }
        btn.addEventListener('click', (e) => {
            // Nao propaga para finding-head (evita toggle de collapse)
            e.stopPropagation();
            e.preventDefault();
            const willOpen = panel.hidden;
            panel.hidden = !willOpen;
            btn.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
            btn.classList.toggle('is-open', willOpen);
        });
    });
}


