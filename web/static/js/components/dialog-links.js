// === components/dialog-links.js ===
function _reattachDialogLinks(body) {
    body.querySelectorAll('.dialog-link[data-lic-num]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            openLicitacaoDialog(link.dataset.licNum, link.dataset.licAno || '0', _currentMunicipio, link.textContent);
        });
    });
    body.querySelectorAll('.dialog-link[data-forn-cnpj]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            openFornecedorDialog(link.dataset.fornCnpj, link.dataset.fornNome || 'Fornecedor', null, false, link.dataset.fornNomeCredor || '', link.dataset.fornCpfCnpj || '');
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

