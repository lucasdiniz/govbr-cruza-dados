// === components/mode-toggle.js ===
// ───────── Helpers UI globais: toast, back-to-top, Web Share ─────────

// ───────── Modo Cidadao / Auditor ─────────
function getMode() {
    try { return localStorage.getItem('mode') === 'auditor' ? 'auditor' : 'citizen'; }
    catch(e) { return 'citizen'; }
}
function setMode(mode) {
    const m = mode === 'auditor' ? 'auditor' : 'citizen';
    try { localStorage.setItem('mode', m); } catch(e) {}
    document.documentElement.classList.toggle('audit-mode', m === 'auditor');
    const btn = document.getElementById('modeToggle');
    if (btn) {
        btn.setAttribute('aria-pressed', m === 'auditor' ? 'true' : 'false');
        btn.setAttribute(
            'aria-label',
            m === 'auditor'
                ? 'Modo auditor ativo. Toque para voltar ao modo cidadao'
                : 'Modo cidadao ativo. Toque para ligar o modo auditor'
        );
        btn.setAttribute('title', m === 'auditor' ? 'Modo auditor ativo' : 'Modo cidadao ativo');
        btn.dataset.currentMode = m;
    }
    document.dispatchEvent(new CustomEvent('modechange', { detail: { mode: m } }));
}
function initModeToggle() {
    // Garante consistencia entre html.audit-mode (setado no head) e localStorage
    setMode(getMode());
    const btn = document.getElementById('modeToggle');
    if (!btn) return;
    btn.addEventListener('click', () => {
        const next = getMode() === 'auditor' ? 'citizen' : 'auditor';
        setMode(next);
        if (navigator.vibrate) { try { navigator.vibrate(10); } catch(e) {} }
        const msg = next === 'auditor'
            ? 'Modo auditor ligado — termos técnicos e dados completos'
            : 'Modo cidadão — linguagem simples';
        if (typeof showToast === 'function') showToast(msg, 2000);
    });
}

