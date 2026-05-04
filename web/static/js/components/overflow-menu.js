// === components/overflow-menu.js ===
//
// Topnav overflow menu (mobile). Combines mode-toggle + font-size into a
// single md-icon-button that opens an md-menu with grouped items:
//
//   * Modo cidadao / Modo auditor (selected by current mode)
//   * Fonte normal / grande / extra grande (selected by current level)
//
// On desktop (>640px) the wrapper is display:none and the two original
// buttons (#modeToggle, #fontSizeToggle) remain visible. On mobile
// (<=640px) the original buttons are display:none and only this overflow
// menu is shown — see components/topnav.css.
//
// The actual mode/font logic lives in mode-toggle.js + font-toggle.js
// (window.__getAppMode/__setAppMode and window.__getFontLevel/__setFontLevel).
// This module only handles menu open/close, item click dispatch, and
// keeping md-menu-item[selected] in sync with current state.
//
// md-menu uses positioning="popover" so it renders in the top layer (escapes
// the topnav stacking context). Anchor by ID via the `anchor` attribute.

function initOverflowMenu() {
    const btn = document.getElementById('overflowMenuBtn');
    const menu = document.getElementById('overflowMenu');
    if (!btn || !menu) return;

    function syncSelected() {
        const mode = (typeof window.__getAppMode === 'function')
            ? window.__getAppMode()
            : 'citizen';
        const level = (typeof window.__getFontLevel === 'function')
            ? window.__getFontLevel()
            : 'normal';
        menu.querySelectorAll('md-menu-item[data-mode]').forEach((it) => {
            it.selected = (it.dataset.mode === mode);
        });
        menu.querySelectorAll('md-menu-item[data-fontlevel]').forEach((it) => {
            it.selected = (it.dataset.fontlevel === level);
        });
    }

    // Toggle open on icon-button click. md-menu fecha sozinho ao clicar
    // fora ou em um item (close-menu event).
    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        menu.open = !menu.open;
        btn.setAttribute('aria-expanded', menu.open ? 'true' : 'false');
    });

    // md-menu emite "opening" / "closing" / "opened" / "closed".
    menu.addEventListener('opening', () => {
        syncSelected();
        btn.setAttribute('aria-expanded', 'true');
    });
    menu.addEventListener('closed', () => {
        btn.setAttribute('aria-expanded', 'false');
    });

    // md-menu-item dispatches "close-menu" when activated; menu listens for
    // it and closes itself. We listen on the menu (bubbles) so we can read
    // the originating item via the event's itemPath.
    menu.addEventListener('close-menu', (e) => {
        const item = e.detail && e.detail.initiator;
        if (!item) return;
        if (item.dataset.mode && typeof window.__setAppMode === 'function') {
            window.__setAppMode(item.dataset.mode);
        } else if (item.dataset.fontlevel && typeof window.__setFontLevel === 'function') {
            window.__setFontLevel(item.dataset.fontlevel);
        }
        // Selected-state refresh after the menu finishes closing so reopens
        // show the new state.
        setTimeout(syncSelected, 0);
        if (navigator.vibrate) { try { navigator.vibrate(8); } catch (_) {} }
    });

    // External changes (other code paths) should reflect in selected state.
    document.addEventListener('modechange', syncSelected);
    document.addEventListener('fontlevelchange', syncSelected);

    // Initial sync — items may not be upgraded yet, but setting selected is
    // a plain attribute so it survives the upgrade.
    syncSelected();
    if (typeof window.whenMD3Ready === 'function') {
        window.whenMD3Ready(syncSelected);
    }
}
