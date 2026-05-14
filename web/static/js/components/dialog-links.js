// === components/dialog-links.js ===
function _reattachDialogLinks(body) {
    body.querySelectorAll('.dialog-link[data-lic-num]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            // data-lic-mun override permite empenho-dialog em pagina
            // /empresa/<cnpj> (global) — onde _currentMunicipio eh '' —
            // resolver a licitacao com o municipio do proprio empenho.
            const linkMun = link.dataset.licMun || '';
            const mun = linkMun || _currentMunicipio;
            // Forwarding licMod (formato despesa) + licUg (codigo_ug) pra API
            // narrow ao 4-tuple canonico (mun + codigo_ug + canonical-mod + num).
            // Sem ambos, dialog cai em LIMIT 1 e pode escolher errado entre
            // licitacoes que compartilham numero_licitacao no mesmo municipio.
            openLicitacaoDialog(link.dataset.licNum, link.dataset.licAno || '0',
                                mun, link.textContent,
                                link.dataset.licMod || '',
                                link.dataset.licUg || '');
        });
    });
    body.querySelectorAll('.dialog-link[data-forn-cnpj]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            // data-forn-mun override: empenho-dialog em /empresa/<cnpj>
            // (global) precisa repassar o municipio do empenho — sem ele,
            // fornecedor-dialog cai em _currentMunicipio='' e abre vazio.
            const linkMun = link.dataset.fornMun || null;
            openFornecedorDialog(link.dataset.fornCnpj, link.dataset.fornNome || 'Fornecedor', linkMun, false, link.dataset.fornNomeCredor || '', link.dataset.fornCpfCnpj || '');
        });
    });
    body.querySelectorAll('tr.clickable-row[data-empenho-id]').forEach(row => {
        row.addEventListener('click', (e) => {
            if (e.target.closest('a')) return;
            openEmpenhoDialog(row.dataset.empenhoId);
        });
    });
    // Municipality selector in fornecedor dialog
    body.querySelectorAll('.mun-selector').forEach(sel => {
        sel.addEventListener('change', () => {
            const cnpj = sel.dataset.fornCnpj;
            const nome = sel.dataset.fornNome;
            const mun = sel.value;
            const nc = sel.dataset.fornNomeCredor || '';
            const cc = sel.dataset.fornCpfCnpj || '';
            openFornecedorDialog(cnpj, nome, mun, true, nc, cc);
        });
    });
    // Cross-municipality sanction rows
    body.querySelectorAll('tr[data-switch-mun]').forEach(row => {
        row.addEventListener('click', () => {
            const cnpj = row.dataset.fornCnpj;
            const nome = row.dataset.fornNome;
            const mun = row.dataset.switchMun;
            const nc = row.dataset.fornNomeCredor || '';
            const cc = row.dataset.fornCpfCnpj || '';
            openFornecedorDialog(cnpj, nome, mun, true, nc, cc);
        });
    });
    _initDialogTableSort(body);
}

