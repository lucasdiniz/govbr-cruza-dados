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
    // md-dialog renders its visible content as a <dialog> inside its
    // shadowRoot. Host transforms don't reliably propagate to top-layer
    // descendants across browsers, so we animate the inner dialog (and
    // scrim) directly via inline styles for drag tracking, then hand off
    // to md-dialog's WAAPI close animation via getCloseAnimation override
    // for the final commit. shadowRoot is null until md-dialog upgrades —
    // resolve lazily on each touch.
    const innerDialog = () => dialog.shadowRoot?.querySelector('dialog');
    const scrim = () => dialog.shadowRoot?.querySelector('.scrim');

    const setDragVisuals = (dy) => {
        const inner = innerDialog();
        const sc = scrim();
        if (inner) {
            inner.style.transition = 'none';
            inner.style.transform = `translateY(${dy}px)`;
        }
        if (sc) {
            sc.style.transition = 'none';
            sc.style.opacity = String(Math.max(0, 0.32 * (1 - dy / 600)));
        }
    };
    const clearDragVisuals = () => {
        const inner = innerDialog();
        const sc = scrim();
        if (inner) {
            inner.style.transform = '';
            inner.style.transition = '';
        }
        if (sc) {
            sc.style.opacity = '';
            sc.style.transition = '';
        }
    };
    const animateSnapBack = () => {
        // User released before threshold — animate inner dialog + scrim
        // back to rest position. Uses WAAPI so it composes cleanly with
        // md-dialog's own animations and auto-cleans up.
        const inner = innerDialog();
        const sc = scrim();
        if (inner) {
            inner.style.transition = '';
            const cur = inner.style.transform;
            inner.style.transform = '';
            inner.animate(
                [{ transform: cur || 'translateY(0)' }, { transform: 'translateY(0)' }],
                { duration: 220, easing: 'cubic-bezier(0.2, 0.8, 0.2, 1)' }
            );
        }
        if (sc) {
            const curOp = sc.style.opacity;
            sc.style.transition = '';
            sc.style.opacity = '';
            sc.animate(
                [{ opacity: curOp || '0.32' }, { opacity: '0.32' }],
                { duration: 220, easing: 'linear' }
            );
        }
    };

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
            clearDragVisuals();
            return;
        }
        // Se o body esta rolado, nao arrasta o dialog
        const b = body();
        const inHeader = header() && header().contains(e.target);
        if (!inHeader && b && b.scrollTop > 0) {
            allowDrag = false;
            dialog.classList.remove('dragging');
            clearDragVisuals();
            return;
        }
        dragging = true;
        dialog.classList.add('dragging');
        const dt = e.timeStamp - lastTime;
        if (dt > 0) velocity = (touch.clientY - lastY) / dt;
        lastY = touch.clientY;
        lastTime = e.timeStamp;
        // Aplica translate na shadow-internal dialog (top-layer-safe).
        // Resistencia: divisor cresce com o dy para o usuario sentir
        // que "esticou" se for muito longe.
        const tracked = dy < 200 ? dy : 200 + (dy - 200) * 0.5;
        setDragVisuals(tracked);
    }, { passive: true });

    const finishDrag = (cancelled) => {
        if (!dragging) {
            dialog.classList.remove('dragging');
            clearDragVisuals();
            return;
        }
        dragging = false;
        const dy = lastY - startY;
        const shouldClose = !cancelled && (dy > CLOSE_DIST || velocity > CLOSE_VELOCITY);
        dialog.classList.remove('dragging');
        if (shouldClose) {
            // Hand off to md-dialog's close animation pipeline. We override
            // getCloseAnimation just for this close so the slide-down picks
            // up where the drag left off (translateY(dy)) and continues to
            // 100% off-screen. md-dialog calls dialog.animate(...) on the
            // inner shadow elements with our keyframes, then closes the
            // top-layer dialog when the animation finishes.
            const tracked = dy < 200 ? dy : 200 + (dy - 200) * 0.5;
            const origGetClose = dialog.getCloseAnimation;
            dialog.getCloseAnimation = () => ({
                dialog: [[
                    [{ transform: `translateY(${tracked}px)` }, { transform: 'translateY(100%)' }],
                    { duration: 220, easing: 'cubic-bezier(0.2, 0.8, 0.2, 1)', fill: 'forwards' }
                ]],
                scrim: [[
                    [{ opacity: String(Math.max(0, 0.32 * (1 - tracked / 600))) }, { opacity: '0' }],
                    { duration: 220, easing: 'linear', fill: 'forwards' }
                ]],
                container: [], headline: [], content: [], actions: []
            });
            // Restore default close animation after the dialog finishes
            // closing; otherwise the next non-swipe close would also use
            // our slide-down keyframes.
            dialog.addEventListener('closed', () => {
                dialog.getCloseAnimation = origGetClose;
                clearDragVisuals();
            }, { once: true });
            dialog.close();
            if ('vibrate' in navigator) { try { navigator.vibrate(10); } catch {} }
        } else {
            // Snap back to rest position.
            animateSnapBack();
        }
    };

    dialog.addEventListener('touchend', () => finishDrag(false), { passive: true });
    dialog.addEventListener('touchcancel', () => finishDrag(true), { passive: true });
}

