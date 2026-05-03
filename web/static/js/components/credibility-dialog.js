// === components/credibility-dialog.js ===
function initCredibilityDialog() {
    // Fase 8: badge de credibilidade no footer abre modal com fontes.
    const btn = document.getElementById('credibilityOpen');
    const dialog = document.getElementById('credibility-dialog');
    if (!btn || !dialog) return;
    btn.addEventListener('click', () => {
        if (typeof dialog.showModal === 'function') dialog.showModal();
        else dialog.setAttribute('open', '');
    });
    dialog.addEventListener('click', (e) => {
        if (e.target === dialog) dialog.close();
    });
    dialog.querySelector('.dialog-close')?.addEventListener('click', () => dialog.close());
}


