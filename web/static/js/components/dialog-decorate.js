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
}

// Unified detail cache — evicts on fetch error
const _detailCache = {};

