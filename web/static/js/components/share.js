// === components/share.js ===
async function triggerShare(data) {
    const url = data.url || window.location.href;
    const title = data.title || document.title;
    const text = data.text || '';
    const isTouch = (navigator.maxTouchPoints || 0) > 0 || matchMedia('(hover: none)').matches;
    if (isTouch && navigator.share) {
        try {
            await navigator.share({ title, text, url });
            return;
        } catch (err) {
            if (err && err.name === 'AbortError') return;
            // segue pra fallback
        }
    }
    if (navigator.clipboard && navigator.clipboard.writeText && window.isSecureContext) {
        try {
            await navigator.clipboard.writeText(url);
            showToast('Link copiado para a area de transferencia');
            return;
        } catch { /* noop */ }
    }
    // Fallback final: textarea + execCommand (funciona mesmo sem secure context)
    try {
        const ta = document.createElement('textarea');
        ta.value = url;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        const ok = document.execCommand('copy');
        document.body.removeChild(ta);
        if (ok) { showToast('Link copiado'); return; }
    } catch { /* noop */ }
    showToast('Nao foi possivel compartilhar. Copie a URL da barra de enderecos.');
}

function initShareButtons() {
    document.querySelectorAll('[data-share]').forEach((btn) => {
        btn.addEventListener('click', (ev) => {
            ev.preventDefault();
            triggerShare({
                title: btn.dataset.shareTitle || document.title,
                text: btn.dataset.shareText || '',
                url: btn.dataset.shareUrl || window.location.href,
            });
        });
    });
}

