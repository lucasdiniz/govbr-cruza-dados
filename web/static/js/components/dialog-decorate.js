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

    const nav = document.createElement('div');
    nav.className = 'dialog-nav';
    nav.setAttribute('role', 'tablist');
    nav.setAttribute('aria-label', 'Secoes do dialogo');
    nav.setAttribute('aria-orientation', 'horizontal');
    nav.innerHTML = sections.map((section, idx) =>
        `<button type="button" role="tab" id="${section.id}-tab" class="dialog-nav-btn${idx === 0 ? ' is-active' : ''}" aria-selected="${idx === 0 ? 'true' : 'false'}" aria-controls="${section.id}" tabindex="${idx === 0 ? '0' : '-1'}" data-dialog-target="${section.id}">${_esc(section.dataset.dialogLabel || `Secao ${idx + 1}`)}</button>`
    ).join('');
    const introNote = body.querySelector(':scope > .dialog-history-note');
    if (introNote) introNote.insertAdjacentElement('afterend', nav);
    else body.prepend(nav);

    const buttons = Array.from(nav.querySelectorAll('.dialog-nav-btn'));
    const setActive = (id, opts = {}) => {
        const activeButton = buttons.find(btn => btn.dataset.dialogTarget === id);
        if (!activeButton) return false;
        buttons.forEach((btn) => {
            const active = btn.dataset.dialogTarget === id;
            btn.classList.toggle('is-active', active);
            btn.setAttribute('aria-selected', active ? 'true' : 'false');
            btn.tabIndex = active ? 0 : -1;
        });
        sections.forEach((section) => {
            section.hidden = section.id !== id;
        });
        body._activeDialogSectionId = id;
        if (opts.focus) {
            activeButton.focus({ preventScroll: true });
            activeButton.scrollIntoView({
                block: 'nearest',
                inline: 'nearest',
                behavior: opts.smooth === false ? 'auto' : 'smooth',
            });
        }
        if (opts.scroll) body.scrollTo({ top: 0, behavior: opts.smooth === false ? 'auto' : 'smooth' });
        return true;
    };
    body._activateDialogSection = setActive;

    buttons.forEach((btn, idx) => {
        btn.addEventListener('click', () => {
            setActive(btn.dataset.dialogTarget, { scroll: true });
        });
        btn.addEventListener('keydown', (event) => {
            let nextIndex = -1;
            if (event.key === 'ArrowRight') nextIndex = (idx + 1) % buttons.length;
            else if (event.key === 'ArrowLeft') nextIndex = (idx - 1 + buttons.length) % buttons.length;
            else if (event.key === 'Home') nextIndex = 0;
            else if (event.key === 'End') nextIndex = buttons.length - 1;
            else return;
            event.preventDefault();
            const next = buttons[nextIndex];
            setActive(next.dataset.dialogTarget, { focus: true, scroll: false });
        });
    });
    setActive(sections[0].id, { smooth: false });
}

// Unified detail cache — evicts on fetch error
const _detailCache = {};

