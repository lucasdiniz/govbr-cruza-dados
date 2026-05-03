// === components/credibility-dialog.js ===
function initCredibilityDialog() {
    // Fase 8: badge de credibilidade no footer abre modal com fontes.
    // Marcacao migrada para <md-dialog> (slots: headline, content, actions).
    // md-dialog auto-fecha em ESC + scrim; fecha via [data-md-dialog-close]
    // ou close() programatico.
    const btn = document.getElementById('credibilityOpen');
    const dialog = document.getElementById('credibility-dialog');
    if (!btn || !dialog) return;
    btn.addEventListener('click', () => {
        dialog.show ? dialog.show() : dialog.setAttribute('open', '');
    });
    dialog.querySelectorAll('[data-md-dialog-close]').forEach((closer) => {
        closer.addEventListener('click', () => dialog.close());
    });
}


