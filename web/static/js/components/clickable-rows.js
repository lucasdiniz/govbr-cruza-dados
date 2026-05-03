// === components/clickable-rows.js ===
function initClickableRows(root = document) {
    root.querySelectorAll('.clickable-row').forEach((row) => {
        if (row.dataset.clickInit === 'true') return;
        row.dataset.clickInit = 'true';
        row.setAttribute('role', 'button');
        row.tabIndex = 0;
        const titleCell = row.querySelector('.stack-title, td:first-child');
        if (titleCell && !row.getAttribute('aria-label')) {
            row.setAttribute('aria-label', `Abrir detalhes de ${titleCell.textContent.trim()}`);
        }
        const activate = () => {
            // Servidor row
            const cpf6 = row.dataset.cpf6 || '';
            const nomeUpper = row.dataset.nomeUpper || '';
            if (cpf6 && nomeUpper) {
                const cnpjs = JSON.parse(row.dataset.cnpjs || '[]') || [];
                const servidorNome = row.dataset.nome || '';
                const servidorFallback = {
                    cargo: row.querySelector('[data-label="Cargo"]')?.textContent?.trim() || row.dataset.cargo || '',
                    salario: row.querySelector('[data-label="Maior salario"]')?.textContent?.trim() || '',
                };
                openServidorDialog(cpf6, nomeUpper, cnpjs, servidorNome, servidorFallback);
                return;
            }
            // Fornecedor row
            const fornCnpj = row.dataset.fornecedorCnpj || '';
            if (fornCnpj) {
                const fornNome = row.dataset.fornecedorNome || '';
                const fornNomeCredor = row.dataset.fornecedorNomeCredor || '';
                const fornCpfCnpj = row.dataset.fornecedorCpfCnpj || '';
                openFornecedorDialog(fornCnpj, fornNome, null, false, fornNomeCredor, fornCpfCnpj);
                return;
            }
            // Licitacao row
            const licNum = row.dataset.licitacaoNum || '';
            if (licNum) {
                const licAno = row.dataset.licitacaoAno || '0';
                const licMod = row.dataset.licitacaoMod || '';
                openLicitacaoDialog(licNum, licAno, _currentMunicipio, `Licitacao ${licNum}`, licMod);
            }
        };
        row.addEventListener('click', activate);
        row.addEventListener('keydown', (event) => {
            if (event.key !== 'Enter' && event.key !== ' ') return;
            event.preventDefault();
            activate();
        });
    });
}

