// === components/dialog-history-swipe.js ===
// ── Dialog: history integration + swipe-to-close (mobile) ──────────
// Objetivo: botao voltar do Android/gesto iOS fecha o dialog em vez de
// sair da pagina. Ao abrir o dialog empilhamos um state; se o usuario
// voltar, o popstate fecha o dialog.
let _dialogHistoryState = false;

function _dialogOnOpen() {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog) return;
    document.body.classList.add('dialog-open');
    if (!_dialogHistoryState) {
        try {
            history.pushState({ tpbDialog: true }, '', '');
            _dialogHistoryState = true;
        } catch { /* ignore */ }
    }
}

function _dialogOnClose() {
    _dialogReset();
    if (_dialogHistoryState) {
        _dialogHistoryState = false;
        if (history.state && history.state.tpbDialog) {
            // Removemos nosso state do historico sem disparar navegacao
            try { history.back(); } catch { /* ignore */ }
        }
    }
}

window.addEventListener('popstate', () => {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog || !dialog.open) {
        _dialogHistoryState = false;
        return;
    }
    // Popstate com dialog aberto -> fechamos o dialog (state ja foi consumido)
    _dialogHistoryState = false;
    dialog.close();
});

function _initDialogSwipeToClose() {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog) return;

    // So ativa em dispositivos touch + viewport mobile
    const isTouchMobile = () =>
        window.matchMedia('(hover: none) and (pointer: coarse)').matches &&
        window.innerWidth <= 640;

    let startY = 0;
    let lastY = 0;
    let lastTime = 0;
    let velocity = 0;
    let dragging = false;
    let allowDrag = false;
    const CLOSE_DIST = 120;
    const CLOSE_VELOCITY = 0.8; // px/ms

    const header = () => dialog.querySelector('.dialog-header');
    const body = () => dialog.querySelector('.dialog-body');

    dialog.addEventListener('touchstart', (e) => {
        if (!isTouchMobile()) return;
        if (e.touches.length !== 1) return;
        const touch = e.touches[0];
        // Swipe-down so inicia se o toque comeca no header OU no topo do body com scrollTop=0
        const target = e.target;
        const inHeader = header() && header().contains(target);
        const b = body();
        const scrolledTop = b && b.scrollTop <= 0;
        if (!inHeader && !scrolledTop) {
            allowDrag = false;
            return;
        }
        allowDrag = true;
        startY = touch.clientY;
        lastY = startY;
        lastTime = e.timeStamp;
        velocity = 0;
        dragging = false;
    }, { passive: true });

    dialog.addEventListener('touchmove', (e) => {
        if (!allowDrag || !isTouchMobile()) return;
        const touch = e.touches[0];
        const dy = touch.clientY - startY;
        // So arrasta pra baixo
        if (dy <= 0) {
            dragging = false;
            dialog.classList.remove('dragging');
            dialog.style.transform = '';
            return;
        }
        // Se o body esta rolado, nao arrasta o dialog
        const b = body();
        const inHeader = header() && header().contains(e.target);
        if (!inHeader && b && b.scrollTop > 0) {
            allowDrag = false;
            dialog.classList.remove('dragging');
            dialog.style.transform = '';
            return;
        }
        dragging = true;
        dialog.classList.add('dragging');
        const dt = e.timeStamp - lastTime;
        if (dt > 0) velocity = (touch.clientY - lastY) / dt;
        lastY = touch.clientY;
        lastTime = e.timeStamp;
        // Aplica translate com resistencia leve
        dialog.style.transform = `translateY(${dy}px)`;
        dialog.style.opacity = String(Math.max(0.5, 1 - dy / 600));
    }, { passive: true });

    const finishDrag = (cancelled) => {
        if (!dragging) {
            dialog.classList.remove('dragging');
            dialog.style.transform = '';
            dialog.style.opacity = '';
            return;
        }
        dragging = false;
        const dy = lastY - startY;
        const shouldClose = !cancelled && (dy > CLOSE_DIST || velocity > CLOSE_VELOCITY);
        dialog.classList.remove('dragging');
        if (shouldClose) {
            dialog.classList.add('closing');
            dialog.style.transform = '';
            dialog.style.opacity = '';
            setTimeout(() => {
                dialog.classList.remove('closing');
                dialog.close();
            }, 220);
            if ('vibrate' in navigator) { try { navigator.vibrate(10); } catch {} }
        } else {
            dialog.style.transform = '';
            dialog.style.opacity = '';
        }
    };

    dialog.addEventListener('touchend', () => finishDrag(false), { passive: true });
    dialog.addEventListener('touchcancel', () => finishDrag(true), { passive: true });
}

