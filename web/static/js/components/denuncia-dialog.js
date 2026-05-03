// === components/denuncia-dialog.js ===
function initDenunciaDialog() {
    const btn = document.getElementById('denunciaOpen');
    const dialog = document.getElementById('denuncia-dialog');
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


let _toastTimer = null;
