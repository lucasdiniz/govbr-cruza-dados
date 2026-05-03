// === components/font-toggle.js ===
function initFontSizeToggle() {
    // Fase 13: 3 niveis (normal / lg / xl). Cicla em ordem e persiste.
    const btn = document.getElementById('fontSizeToggle');
    if (!btn) return;
    const LEVELS = ['normal', 'lg', 'xl'];
    const LABELS = { normal: 'A', lg: 'A', xl: 'A' };
    const SUFFIX = { normal: '+', lg: '++', xl: '+++' };
    const html = document.documentElement;

    function currentLevel() {
        if (html.classList.contains('font-xl')) return 'xl';
        if (html.classList.contains('font-lg')) return 'lg';
        return 'normal';
    }
    function applyLevel(level) {
        html.classList.remove('font-lg', 'font-xl');
        if (level === 'lg') html.classList.add('font-lg');
        else if (level === 'xl') html.classList.add('font-xl');
        try {
            if (level === 'normal') localStorage.removeItem('font-size');
            else localStorage.setItem('font-size', level);
        } catch (_) {}
        updateLabel(level);
    }
    function updateLabel(level) {
        const span = btn.querySelector('.font-toggle-label');
        if (span) span.innerHTML = LABELS[level] + '<span class="font-plus">' + SUFFIX[level] + '</span>';
        btn.setAttribute('aria-label', `Tamanho da fonte: ${level === 'normal' ? 'normal' : level === 'lg' ? 'grande' : 'maior'} (clique para alternar)`);
        btn.dataset.level = level;
    }
    updateLabel(currentLevel());
    btn.addEventListener('click', () => {
        const cur = currentLevel();
        const next = LEVELS[(LEVELS.indexOf(cur) + 1) % LEVELS.length];
        applyLevel(next);
        if (navigator.vibrate) navigator.vibrate(8);
    });
}


