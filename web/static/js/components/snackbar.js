// === components/snackbar.js ===
function showToast(message, durationMs = 2200) {
    const el = document.getElementById('toast');
    if (!el) return;
    el.textContent = message;
    el.hidden = false;
    // Next frame para animar entrada
    requestAnimationFrame(() => el.classList.add('visible'));
    if (_toastTimer) clearTimeout(_toastTimer);
    _toastTimer = setTimeout(() => {
        el.classList.remove('visible');
        setTimeout(() => { el.hidden = true; }, 200);
    }, durationMs);
}

