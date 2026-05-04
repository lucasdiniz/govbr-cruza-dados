// === components/licitacao-dialog.js ===
function _fetchLicitacaoDetails(numeroLicitacao, anoLicitacao, municipio, modalidade) {
    return _cachedPost('/api/licitacao/detalhes', `lic:${numeroLicitacao}:${anoLicitacao}:${municipio}:${modalidade}`,
        { numero_licitacao: numeroLicitacao, ano_licitacao: parseInt(anoLicitacao) || 0, municipio, modalidade: modalidade || '' });
}

async function openLicitacaoDialog(numeroLicitacao, anoLicitacao, municipio, label, modalidade) {
    const dialog = document.getElementById('empresa-dialog');
    if (!dialog) return;
    if (dialog.open) { _dialogPush(); } else { _dialogReset(); }
    const title = dialog.querySelector('.dialog-title');
    const body = dialog.querySelector('.dialog-body');
    title.textContent = label || `Licitacao ${numeroLicitacao}`;
    body.innerHTML = '<p class="text-sm text-muted">Carregando...</p>';
    if (!dialog.open) dialog.show();
    document.body.classList.add('dialog-open');

    const data = await _fetchLicitacaoDetails(numeroLicitacao, anoLicitacao, municipio, modalidade);

    // Metadata — always render header
    const _licNumLabel = `N. ${_esc(numeroLicitacao)}${anoLicitacao && anoLicitacao !== '0' ? ` / ${anoLicitacao}` : ''}`;
    if (!data.licitacao && !(data.proponentes && data.proponentes.length) && !(data.despesas && data.despesas.length)) {
        body.innerHTML = `<p class="text-sm text-muted">Nenhum detalhe disponivel para esta licitacao (${_licNumLabel}).</p>`;
        return;
    }

    let html = _historyNote('Historico completo da licitacao — este detalhamento nao muda com o filtro de periodo da pagina.');
    html += `<div class="dialog-section"><h4>${dualLabel('Dados desta licitacao','Dados da licitacao')}</h4>`;
    if (data.licitacao) {
        const lic = data.licitacao;
        html += `<div class="empresa-card">
            <div class="empresa-header">
                <strong>${_esc(lic.modalidade || 'Licitacao')}</strong>
                <span class="text-sm text-muted">${_licNumLabel}</span>
            </div>
            <div class="empresa-details">
                ${lic.objeto_licitacao ? `<span>Objeto: ${_esc(lic.objeto_licitacao)}</span>` : ''}
                ${lic.descricao_ug ? `<span>UG: ${_esc(lic.descricao_ug)}</span>` : ''}
                ${lic.data_homologacao ? `<span>Homologacao: ${_fmtDate(lic.data_homologacao)}</span>` : ''}
            </div>
        </div>`;
    } else {
        html += `<div class="empresa-card empresa-missing">
            <div class="empresa-header">
                <strong>Licitacao</strong>
                <span class="text-sm text-muted">${_licNumLabel}</span>
            </div>
            <div class="empresa-details">
                <span>Dados cadastrais indisponiveis no TCE-PB para esta licitacao.</span>
            </div>
        </div>`;
    }
    html += '</div>';

    // Proponentes
    if (data.proponentes && data.proponentes.length) {
        html += `<div class="dialog-section"><h4>${dualLabel('Empresas que participaram','Proponentes')}</h4>`;
        const propRows = data.proponentes.map(p => {
            const cnpjRaw = String(p.cpf_cnpj_proponente || '').replace(/\D/g, '');
            const cnpjB = cnpjRaw.slice(0, 8);
            const isClickable = cnpjB.length === 8 && /^\d{8}$/.test(cnpjB) && cnpjRaw.length >= 14;
            const nome = _esc(p.razao_social || p.nome_proponente || '-');
            const nomeLink = isClickable
                ? `<a href="#" class="dialog-link" data-forn-cnpj="${cnpjB}" data-forn-cpf-cnpj="${cnpjRaw}" data-forn-nome="${nome}" data-forn-nome-credor="${_esc(p.nome_proponente || '')}">${nome}</a>`
                : nome;
            return `<tr>
                <td data-label="Empresa" class="stack-title">${nomeLink}</td>
                <td data-label="CNPJ/CPF" class="auditor-only"><code class="text-sm">${_esc(p.cpf_cnpj_proponente || '-')}</code></td>
                <td data-label="Valor" class="text-right num">${_shortBrl(p.valor_ofertado)}</td>
                <td data-label="Resultado" class="stack-meta">${_esc(p.situacao_proposta || '-')}</td>
            </tr>`;
        }).join('');
        html += `<div class="tbl-wrap"><table class="dialog-table stack-mobile">
            <thead><tr><th>${dualLabel('Empresa','Proponente')}</th><th class="auditor-only">CNPJ/CPF</th><th class="text-right">${dualLabel('Valor proposto','Valor ofertado')}</th><th>${dualLabel('Resultado','Situacao')}</th></tr></thead>
            <tbody>${propRows}</tbody>
        </table></div>`;
        html += '</div>';
    }

    // Despesas vinculadas
    if (data.despesas && data.despesas.length) {
        html += `<div class="dialog-section"><h4>${dualLabel('Pagamentos desta licitacao','Despesas vinculadas')}</h4>`;
        const despRows = data.despesas.map(d => {
            const cnpjRaw = String(d.cpf_cnpj || '').replace(/\D/g, '');
            const cnpjB = cnpjRaw.slice(0, 8);
            const isClickable = cnpjB.length === 8 && /^\d{8}$/.test(cnpjB) && cnpjRaw.length >= 14;
            const nome = _esc(d.nome_credor || '-');
            const nomeCell = isClickable
                ? `<a href="#" class="dialog-link" data-forn-cnpj="${cnpjB}" data-forn-cpf-cnpj="${cnpjRaw}" data-forn-nome="${nome}" data-forn-nome-credor="${nome}">${nome}</a>`
                : nome;
            return `<tr class="clickable-row" data-empenho-id="${d.id}">
                <td data-label="Credor" class="stack-title">${nomeCell}</td>
                <td data-label="Data" class="stack-meta">${_fmtDate(d.data_empenho)}</td>
                <td data-label="Tipo de gasto" class="stack-meta">${_esc(d.elemento_despesa || '-')}</td>
                <td data-label="Reservado" class="text-right num">${_shortBrl(d.valor_empenhado)}</td>
                <td data-label="Pago" class="text-right num">${_shortBrl(d.valor_pago)}</td>
            </tr>`;
        }).join('');
        html += `<div class="tbl-wrap"><table class="dialog-table stack-mobile">
            <thead><tr><th>${dualLabel('Empresa','Credor')}</th><th>Data</th><th>${dualLabel('Tipo de gasto','Elemento')}</th><th class="text-right">${dualLabel('Reservado','Empenhado')}</th><th class="text-right">Pago</th></tr></thead>
            <tbody>${despRows}</tbody>
        </table></div>`;
        if (data.despesas.length >= 50) {
            html += '<p class="text-sm text-muted">Mostrando as 50 despesas mais recentes.</p>';
        }
        html += '</div>';
    }
    body.innerHTML = html;
    _reattachDialogLinks(body);
    _decorateDialogBody(body);
}

