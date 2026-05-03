// === components/denuncia-dialog.js ===
function initDenunciaDialog() {
    // Marcacao migrada para <md-dialog>. Auto-fecha via ESC/scrim e
    // [data-md-dialog-close].
    const btn = document.getElementById('denunciaOpen');
    const dialog = document.getElementById('denuncia-dialog');
    if (!btn || !dialog) return;
    btn.addEventListener('click', () => {
        dialog.show ? dialog.show() : dialog.setAttribute('open', '');
    });
    dialog.querySelectorAll('[data-md-dialog-close]').forEach((closer) => {
        closer.addEventListener('click', () => dialog.close());
    });
}


let _toastTimer = null;
