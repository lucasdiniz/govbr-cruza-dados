// === components/denuncia-dialog.js ===
function initDenunciaDialog() {
    // Marcacao migrada para <md-dialog>. O botao "Como denunciar" e' um
    // <md-filled-button> — gateamos com whenMD3Ready() para garantir
    // upgrade completo antes de qualquer click.
    const btn = document.getElementById('denunciaOpen');
    const dialog = document.getElementById('denuncia-dialog');
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


let _toastTimer = null;
