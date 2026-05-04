// === components/dialog-decorate.js ===
function _dialogSectionNavLabel(rawText) {
    const text = String(rawText || '').replace(/\s+/g, ' ').trim();
    if (!text) return 'Resumo';
    if (/dados cadastrais|dados da empresa|dados da licitacao|dados desta licitacao/i.test(text)) return 'Resumo';
    if (/^resumo do mes/i.test(text)) return 'Resumo';
    if (/resumo de pagamentos|pagamentos recentes|empenhos recentes|quanto esta empresa/i.test(text)) return 'Pagamentos';
    if (/quem mais recebeu|top fornecedores/i.test(text)) return 'Fornecedores';
    if (/em que a cidade gastou|top elementos|elementos de despesa/i.test(text)) return 'Despesas';
    if (/areas do governo|funcao ?\/ ?programa/i.test(text)) return 'Areas';
    if (/como foi contratado|modalidade/i.test(text)) return 'Modalidade';
    if (/maiores pagamentos do mes|empenhos do mes/i.test(text)) return 'Maiores';
    if (/vinculos como servidor|empregos publicos/i.test(text)) return 'Vinculos';
    if (/empresas vinculadas|aparece como socio/i.test(text)) return 'Empresas';
    if (/sancoes|punicoes/i.test(text)) return 'Sancoes';
    if (/pgfn|divida ativa|impostos federais/i.test(text)) return 'PGFN';
    if (/leniencia|acordos? de colaboracao/i.test(text)) return 'Leniencia';
    if (/bolsa familia/i.test(text)) return 'Bolsa Familia';
    if (/ceaf|expulsoes/i.test(text)) return 'CEAF';
    if (/outros municipios|outras cidades/i.test(text)) return 'Outras cidades';
    if (/proponentes|empresas que participaram/i.test(text)) return 'Proponentes';
    if (/despesas vinculadas|pagamentos desta licitacao/i.test(text)) return 'Despesas';
    if (/quem recebeu|^credor/i.test(text)) return 'Credor';
    if (/em que foi gasto|classificacao orcamentaria/i.test(text)) return 'Classificacao';
    if (/de onde veio|^origem/i.test(text)) return 'Origem';
    if (/^valores$/i.test(text)) return 'Valores';
    if (/^descricao$/i.test(text)) return 'Descricao';
    if (/pagamentos do governo as empresas|empenhos recebidos pelas empresas/i.test(text)) return 'Empenhos';
    return text.split(' ').slice(0, 2).join(' ');
}

function _decorateDialogBody(body) {
    if (!body) return;
    if (body._dialogNavScrollHandler) {
        body.removeEventListener('scroll', body._dialogNavScrollHandler);
        body._dialogNavScrollHandler = null;
    }
    body.querySelector('.dialog-nav')?.remove();

    const sections = Array.from(body.querySelectorAll('.dialog-section'));
    if (sections.length < 2) {
        body._activateDialogSection = null;
        body._activeDialogSectionId = '';
        return;
    }

    sections.forEach((section, idx) => {
        if (!section.id) section.id = `dialog-section-${idx + 1}`;
        const heading = section.querySelector('h4');
        section.dataset.dialogLabel = _dialogSectionNavLabel(heading ? heading.textContent : `Secao ${idx + 1}`);
        section.setAttribute('aria-labelledby', `${section.id}-tab`);
        section.classList.add('dialog-tab-panel');
        section.setAttribute('role', 'tabpanel');
        section.hidden = idx !== 0;
    });

    // MD3 secondary tabs — sticky bar at top of dialog body. md-tabs handles
    // keyboard navigation (arrow keys), focus, and the active indicator
    // internally. We wrap in a div.dialog-nav so existing CSS sticky/padding
    // overrides keep applying without touching the shadow root.
    const nav = document.createElement('div');
    nav.className = 'dialog-nav';
    const tabs = document.createElement('md-tabs');
    tabs.setAttribute('aria-label', 'Secoes do dialogo');
    tabs.innerHTML = sections.map((section, idx) =>
        `<md-secondary-tab id="${section.id}-tab" data-dialog-target="${section.id}" aria-controls="${section.id}"${idx === 0 ? ' active' : ''}>${_esc(section.dataset.dialogLabel || `Secao ${idx + 1}`)}</md-secondary-tab>`
    ).join('');
    nav.appendChild(tabs);
    const introNote = body.querySelector(':scope > .dialog-history-note');
    if (introNote) introNote.insertAdjacentElement('afterend', nav);
    else body.prepend(nav);

    const tabEls = Array.from(tabs.querySelectorAll('md-secondary-tab'));
    const setActive = (id, opts = {}) => {
        const activeTab = tabEls.find(t => t.dataset.dialogTarget === id);
        if (!activeTab) return false;
        tabEls.forEach((tab) => {
            const isActive = tab.dataset.dialogTarget === id;
            // md-tabs reads `active` (boolean) on each tab. Setting it
            // imperatively keeps state in sync without relying on the
            // tab-set's selectionChange event.
            if (isActive) tab.setAttribute('active', '');
            else tab.removeAttribute('active');
        });
        sections.forEach((section) => {
            section.hidden = section.id !== id;
        });
        body._activeDialogSectionId = id;
        if (opts.focus) {
            activeTab.focus({ preventScroll: true });
            activeTab.scrollIntoView({
                block: 'nearest',
                inline: 'nearest',
                behavior: opts.smooth === false ? 'auto' : 'smooth',
            });
        }
        if (opts.scroll) body.scrollTo({ top: 0, behavior: opts.smooth === false ? 'auto' : 'smooth' });
        return true;
    };
    body._activateDialogSection = setActive;

    // md-tabs dispatches `change` when the user activates a different tab via
    // click or keyboard. Read the new active tab from event.target.activeTab
    // (provided by md-tabs once upgraded).
    tabs.addEventListener('change', () => {
        const active = tabs.activeTab || tabEls.find(t => t.hasAttribute('active'));
        if (!active) return;
        const id = active.dataset.dialogTarget;
        if (id && id !== body._activeDialogSectionId) {
            setActive(id, { scroll: true });
        }
    });

    setActive(sections[0].id, { smooth: false });

    // ─── Horizontal swipe to change tabs (mobile / touch) ──────────────
    // On touch devices, swiping the dialog body left/right moves to the
    // adjacent tab. Skips touches that start inside a horizontally
    // scrollable container (.tbl-wrap with overflow) so native table
    // scrolling still works, and aborts if vertical motion dominates
    // (lets the swipe-to-close handler in dialog-history-swipe.js own
    // vertical gestures).
    if (body._swipeTabsBound) return;
    body._swipeTabsBound = true;
    const SWIPE_DIST = 60;        // px of horizontal motion to commit
    const SWIPE_VELOCITY = 0.5;   // px/ms — fast flick also commits
    const SWIPE_RATIO = 1.3;      // |dx| must beat |dy| by this factor

    const isTouchMobile = () =>
        window.matchMedia('(hover: none) and (pointer: coarse)').matches;

    let sx = 0, sy = 0, lx = 0, ly = 0, st = 0, vx = 0;
    let active = false;

    body.addEventListener('touchstart', (e) => {
        if (!isTouchMobile() || e.touches.length !== 1) return;
        // Bail if the touch starts inside a horizontally scrollable
        // container that actually has overflow. Lets the user pan tables
        // with both fingers without accidentally swapping tabs.
        let el = e.target;
        while (el && el !== body) {
            if (el.scrollWidth > el.clientWidth + 4) return;
            el = el.parentElement;
        }
        const t = e.touches[0];
        sx = lx = t.clientX;
        sy = ly = t.clientY;
        st = e.timeStamp;
        vx = 0;
        active = true;
    }, { passive: true });

    body.addEventListener('touchmove', (e) => {
        if (!active || e.touches.length !== 1) return;
        const t = e.touches[0];
        const dt = e.timeStamp - st;
        if (dt > 0) vx = (t.clientX - lx) / Math.max(1, e.timeStamp - st);
        lx = t.clientX;
        ly = t.clientY;
    }, { passive: true });

    const commitSwipe = () => {
        if (!active) return;
        active = false;
        const dx = lx - sx;
        const dy = ly - sy;
        const adx = Math.abs(dx);
        const ady = Math.abs(dy);
        // Vertical motion dominates → leave it for the swipe-to-close path
        if (ady > adx * 0.8) return;
        // A fast flick can commit at a shorter distance, but still needs
        // at least ~30px to count (avoids accidental taps + jitter).
        const fastFlick = Math.abs(vx) >= SWIPE_VELOCITY;
        const minDist = fastFlick ? 30 : SWIPE_DIST;
        if (adx < minDist) return;
        if (adx < ady * SWIPE_RATIO) return;
        const currentId = body._activeDialogSectionId;
        const idx = tabEls.findIndex(t => t.dataset.dialogTarget === currentId);
        if (idx < 0) return;
        // dx < 0 (swipe left)  → next tab
        // dx > 0 (swipe right) → previous tab
        const dir = dx < 0 ? 1 : -1;
        const nextIdx = idx + dir;
        if (nextIdx < 0 || nextIdx >= tabEls.length) return;
        const next = tabEls[nextIdx];
        setActive(next.dataset.dialogTarget, { scroll: true });
        // Light haptic feedback on supported devices
        if ('vibrate' in navigator) {
            try { navigator.vibrate(8); } catch { /* ignore */ }
        }
    };
    body.addEventListener('touchend', commitSwipe, { passive: true });
    body.addEventListener('touchcancel', () => { active = false; }, { passive: true });
}

// Unified detail cache — evicts on fetch error
const _detailCache = {};

