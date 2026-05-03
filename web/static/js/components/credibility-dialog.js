// === components/credibility-dialog.js ===
function initCredibilityDialog() {
    // Fase 8: badge de credibilidade no footer abre modal com fontes.
    // Marcacao migrada para <md-dialog> (slots: headline, content, actions).
    // Gateamos com whenMD3Ready() para garantir que md-dialog tenha upgrade
    // (dialog.show definido) antes que qualquer click possa chegar.
    const btn = document.getElementById('credibilityOpen');
    const dialog = document.getElementById('credibility-dialog');
    if (!btn || !dialog) return;
    const ready = typeof window.whenMD3Ready === 'function' ? window.whenMD3Ready() : Promise.resolve();
    ready.then(() => {
        btn.addEventListener('click', () => {
            dialog.show ? dialog.show() : dialog.setAttribute('open', '');
        });
        dialog.querySelectorAll('[data-md-dialog-close]').forEach((closer) => {
            closer.addEventListener('click', () => dialog.close());
        });
    });
}


