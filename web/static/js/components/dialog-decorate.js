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
    // adjacent tab with a smooth follow-finger animation. The current
    // section translates with the touch (with rubber-band resistance at
    // tab boundaries); on release, it either commits with a slide-out +
    // slide-in (page-turn feel) or snaps back to its original position.
    //
    // Skips touches that start inside a horizontally scrollable container
    // (.tbl-wrap with overflow) so native table scrolling still works,
    // and aborts if vertical motion dominates (lets the swipe-to-close
    // handler in dialog-history-swipe.js own vertical gestures).
    if (body._swipeTabsBound) return;
    body._swipeTabsBound = true;
    const SWIPE_DIST = 60;        // px of horizontal motion to commit
    const SWIPE_VELOCITY = 0.5;   // px/ms — fast flick also commits
    const SWIPE_RATIO = 1.3;      // |dx| must beat |dy| by this factor
    const DRAG_THRESHOLD = 8;     // px before drag becomes "active" (visual)
    const SWAP_DURATION = 200;    // ms — slide-out + slide-in segments
    const SNAP_DURATION = 180;    // ms — snap-back when not committed
    const SWAP_EASING = 'cubic-bezier(0.4, 0, 0.2, 1)';
    const BOUNDARY_RESIST = 0.3;  // multiplier when dragging past first/last

    const isTouchMobile = () =>
        window.matchMedia('(hover: none) and (pointer: coarse)').matches;

    let sx = 0, sy = 0, lx = 0, ly = 0, st = 0, vx = 0;
    let active = false;
    // Drag visual state. Created lazily once horizontal motion passes the
    // DRAG_THRESHOLD so taps + vertical scrolls don't move anything.
    let drag = null;

    function getCurrentSection() {
        const id = body._activeDialogSectionId;
        return sections.find((s) => s.id === id) || null;
    }
    function getNeighbor(direction) {
        // direction: +1 = next (swipe left), -1 = prev (swipe right)
        const idx = sections.indexOf(getCurrentSection());
        const nidx = idx + direction;
        return (nidx >= 0 && nidx < sections.length) ? sections[nidx] : null;
    }
    function setupDrag() {
        const current = getCurrentSection();
        if (!current) return null;
        // Pin styles so transforms apply cleanly. Saves originals so we
        // can restore them after the animation (or snap-back).
        const prevTransform = current.style.transform;
        const prevTransition = current.style.transition;
        const prevWillChange = current.style.willChange;
        current.style.transition = 'none';
        current.style.willChange = 'transform';
        // Signal to the vertical swipe-to-close handler (dialog-history-swipe.js)
        // that a horizontal tab swipe has taken over; it must abort any
        // in-flight vertical drag and ignore further moves until cleared.
        body.dataset.tabSwiping = '1';
        return { current, prevTransform, prevTransition, prevWillChange };
    }
    function applyDragTransform(dx) {
        if (!drag) return;
        // Rubber-band resistance when dragging past the first/last tab in
        // the unavailable direction. The user gets visual feedback that
        // they've reached the edge but the section doesn't run away with
        // the finger.
        let visible = dx;
        const targetDir = dx < 0 ? 1 : -1;
        if (!getNeighbor(targetDir)) {
            visible = dx * BOUNDARY_RESIST;
        }
        drag.current.style.transform = `translateX(${visible}px)`;
        drag.lastVisibleDx = visible;
    }
    function restoreSectionStyles(section, snapshot) {
        section.style.transform = snapshot.prevTransform || '';
        section.style.transition = snapshot.prevTransition || '';
        section.style.willChange = snapshot.prevWillChange || '';
        // Once the section is settled, drop the cross-handler signal so
        // future vertical swipes (e.g., to close) can engage normally.
        delete body.dataset.tabSwiping;
    }
    function snapBack() {
        if (!drag) return;
        const { current } = drag;
        const startX = drag.lastVisibleDx || 0;
        const snapshot = drag;
        drag = null;
        const anim = current.animate(
            [{ transform: `translateX(${startX}px)` }, { transform: 'translateX(0)' }],
            { duration: SNAP_DURATION, easing: SWAP_EASING, fill: 'none' }
        );
        anim.onfinish = () => restoreSectionStyles(current, snapshot);
        anim.oncancel = () => restoreSectionStyles(current, snapshot);
    }
    function commitSwap(direction) {
        if (!drag) return;
        const target = getNeighbor(direction);
        if (!target) { snapBack(); return; }
        const { current } = drag;
        const startX = drag.lastVisibleDx || 0;
        const width = body.clientWidth || window.innerWidth || 360;
        const exitX = direction > 0 ? -width : width;
        const enterFromX = direction > 0 ? width : -width;
        const snapshot = drag;
        drag = null;

        // Phase 1: current slides out to the exit side.
        const out = current.animate(
            [{ transform: `translateX(${startX}px)`, opacity: 1 },
             { transform: `translateX(${exitX}px)`, opacity: 0.3 }],
            { duration: SWAP_DURATION, easing: SWAP_EASING, fill: 'forwards' }
        );
        out.onfinish = () => {
            restoreSectionStyles(current, snapshot);
            // Now formally activate the target (this hides current, shows
            // target via setActive's `section.hidden = ...` loop).
            setActive(target.id, { scroll: false });
            // Phase 2: target slides in from the opposite side.
            const targetSnapshot = {
                prevTransform: target.style.transform,
                prevTransition: target.style.transition,
                prevWillChange: target.style.willChange,
            };
            target.style.transition = 'none';
            target.style.willChange = 'transform';
            const enter = target.animate(
                [{ transform: `translateX(${enterFromX}px)`, opacity: 0.3 },
                 { transform: 'translateX(0)', opacity: 1 }],
                { duration: SWAP_DURATION, easing: SWAP_EASING, fill: 'none' }
            );
            enter.onfinish = () => restoreSectionStyles(target, targetSnapshot);
            enter.oncancel = () => restoreSectionStyles(target, targetSnapshot);
            // Light haptic on commit (post-handover for stable feel).
            if ('vibrate' in navigator) {
                try { navigator.vibrate(8); } catch { /* ignore */ }
            }
        };
        out.oncancel = () => {
            restoreSectionStyles(current, snapshot);
        };
    }

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
        drag = null; // lazy init when motion passes the threshold
    }, { passive: true });

    body.addEventListener('touchmove', (e) => {
        if (!active || e.touches.length !== 1) return;
        const t = e.touches[0];
        const dt = e.timeStamp - st;
        if (dt > 0) vx = (t.clientX - lx) / Math.max(1, e.timeStamp - st);
        lx = t.clientX;
        ly = t.clientY;
        const dx = lx - sx;
        const dy = ly - sy;
        const adx = Math.abs(dx);
        const ady = Math.abs(dy);
        // Initialize drag visuals once we have meaningful horizontal
        // motion that's clearly horizontal (not a vertical scroll start).
        if (!drag && adx > DRAG_THRESHOLD && adx > ady) {
            drag = setupDrag();
        }
        if (drag) applyDragTransform(dx);
    }, { passive: true });

    const finishGesture = () => {
        if (!active) return;
        active = false;
        if (!drag) return;
        const dx = lx - sx;
        const dy = ly - sy;
        const adx = Math.abs(dx);
        const ady = Math.abs(dy);
        // Vertical motion dominated → snap back, leave vertical to the
        // swipe-to-close handler (which also fires touchend on the dialog
        // host, not the body).
        if (ady > adx * 0.8) { snapBack(); return; }
        const fastFlick = Math.abs(vx) >= SWIPE_VELOCITY;
        const minDist = fastFlick ? 30 : SWIPE_DIST;
        if (adx < minDist || adx < ady * SWIPE_RATIO) { snapBack(); return; }
        const dir = dx < 0 ? 1 : -1;
        if (!getNeighbor(dir)) { snapBack(); return; }
        commitSwap(dir);
    };
    body.addEventListener('touchend', finishGesture, { passive: true });
    body.addEventListener('touchcancel', () => {
        if (drag) snapBack();
        active = false;
    }, { passive: true });
}

// Unified detail cache — evicts on fetch error
const _detailCache = {};

